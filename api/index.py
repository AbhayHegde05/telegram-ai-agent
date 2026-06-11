import logging
import os
import sys
from fastapi import FastAPI, Request, Response, HTTPException
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Import handlers (using absolute imports based on project root)
from handlers.recommendation import (
    start_recommendation,
    handle_language_selection,
    handle_genre_selection,
    handle_duration_selection,
    handle_release_preference,
    handle_mood_preference,
)
from handlers.brief import start_brief, handle_brief_movie_name
from handlers.review import start_review, handle_review_movie_name
from utils.memory import get_storage_status, init_db, log_event, start_session

from main import (
    start,
    handle_help,
    endchat,
    handle_cancel,
    handle_brief_or_review_input,
    error_handler,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Initialize DB (Supabase)
init_db()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

if not TELEGRAM_BOT_TOKEN:
    logger.critical("❌ TELEGRAM_BOT_TOKEN not found in environment variables")

# Build PTB Application with updater=None (webhook mode)
ptb_app = Application.builder().token(TELEGRAM_BOT_TOKEN).updater(None).build()
ptb_app.bot_data["audit_endpoint"] = "/api/webhook"

ptb_app.add_error_handler(error_handler)

ptb_app.add_handler(CommandHandler("start", start))
ptb_app.add_handler(CommandHandler("help", handle_help))
ptb_app.add_handler(CommandHandler("endchat", endchat))

ptb_app.add_handler(CallbackQueryHandler(handle_cancel, pattern="^cancel$"))

ptb_app.add_handler(CallbackQueryHandler(start_recommendation, pattern="^rec_start$"))
ptb_app.add_handler(CallbackQueryHandler(start_brief, pattern="^brief_start$"))
ptb_app.add_handler(CallbackQueryHandler(start_review, pattern="^review_start$"))

ptb_app.add_handler(CallbackQueryHandler(handle_language_selection, pattern="^rec_lang_"))
ptb_app.add_handler(CallbackQueryHandler(handle_genre_selection, pattern="^rec_genre_"))
ptb_app.add_handler(CallbackQueryHandler(handle_duration_selection, pattern="^rec_duration_"))
ptb_app.add_handler(CallbackQueryHandler(handle_release_preference, pattern="^rec_release_"))
ptb_app.add_handler(CallbackQueryHandler(handle_mood_preference, pattern="^rec_mood_"))

ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_brief_or_review_input))

app = FastAPI(title="Telegram Movie Bot Webhook")
_is_initialized = False


@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    global _is_initialized

    logger.info("WEBHOOK HIT")
    logger.info(
        "📨 Webhook request received: method=%s path=%s headers=%s",
        request.method,
        request.url.path,
        dict(request.headers),
    )

    if not _is_initialized:
        logger.info("APPLICATION INITIALIZED (starting) -> ptb_app.initialize()")
        try:
            await ptb_app.initialize()
            logger.info("APPLICATION INITIALIZED")

            # start() may not be supported in all PTB webhook/serverless setups; try best-effort
            try:
                await ptb_app.start()
                logger.info("APPLICATION STARTED (ptb_app.start())")
            except Exception as e:
                logger.warning("⚠️ APPLICATION START FAILED/UNSUPPORTED (continuing): %s", repr(e))

            _is_initialized = True
            logger.info("✅ PTB initialize() completed.")
        except Exception:
            logger.critical("❌ APPLICATION INITIALIZATION FAILED", exc_info=True)
            raise

    try:
        logger.info("UPDATE RECEIVED (about to read request.json())")
        data = await request.json()
        logger.info("UPDATE RECEIVED (payload keys=%s)", list(data.keys()))

        update = Update.de_json(data, ptb_app.bot)

        # Extract chat_id for diagnostics
        chat_id = None
        try:
            if update.message and update.message.chat:
                chat_id = update.message.chat.id
            elif update.effective_chat:
                chat_id = update.effective_chat.id
        except Exception:
            logger.exception("DIAG: failed extracting chat_id")

        logger.info(
            "🧭 Update kind=%s has_message=%s has_callback=%s",
            "message" if update.message else ("callback_query" if update.callback_query else "unknown"),
            bool(getattr(update, "message", None)),
            bool(getattr(update, "callback_query", None)),
        )

        # Always log update text/command if present
        try:
            msg_text = update.message.text if update.message and update.message.text else None
            cb_data = update.callback_query.data if update.callback_query and update.callback_query.data else None
            logger.info(
                "🧩 Parsed: update_id=%s effective_user=%s message_text=%s callback_data=%s",
                getattr(update, "update_id", None),
                (update.effective_user.id if update.effective_user else None),
                (msg_text[:200] if msg_text else None),
                (cb_data[:200] if cb_data else None),
            )
        except Exception:
            logger.exception("DIAG: failed logging parsed update")

        # Log handler matching (best-effort)
        try:
            matched = ptb_app.update_processor._check_update(update)  # type: ignore[attr-defined]
            logger.info("🎯 Handler matching result (raw)=%s", repr(matched))
        except Exception as e:
            logger.debug("🎯 Handler matching trace not available: %s", repr(e))

        # Log session payload
        user_id = None
        try:
            user_id = update.effective_user.id if update.effective_user else None
        except Exception:
            user_id = None

        try:
            if user_id:
                payload = {"update_id": update.update_id}
                if update.message and update.message.text:
                    payload["text"] = update.message.text[:500]
                if update.callback_query and update.callback_query.data:
                    payload["callback_data"] = update.callback_query.data[:500]

                chat = update.effective_chat
                command = (
                    update.message.text.split(maxsplit=1)[0].split("@")[0]
                    if update.message and update.message.text
                    else None
                )

                session_id = start_session(
                    user_id,
                    chat_id=chat.id if chat else None,
                    username=update.effective_user.username if update.effective_user else None,
                    first_name=update.effective_user.first_name if update.effective_user else None,
                    last_name=update.effective_user.last_name if update.effective_user else None,
                    force_new=command == "/start",
                )

                log_event(
                    user_id,
                    "webhook_update",
                    payload,
                    endpoint="/api/webhook",
                    update_kind="message" if update.message else ("callback_query" if update.callback_query else "unknown"),
                    handler=None,
                    session_id=session_id,
                )
        except Exception:
            logger.exception("❌ FAILED to log webhook event payload")

        logger.info("PROCESSING UPDATE start")
        await ptb_app.process_update(update)
        logger.info("✅ PROCESSING UPDATE end")

        # If nothing else replied, we still want to see that at least webhook handler is alive.
        # (Do not block response if this fails.)
        if chat_id is not None and TELEGRAM_BOT_TOKEN:
            try:
                diag_bot = Bot(token=TELEGRAM_BOT_TOKEN)
                await diag_bot.send_message(chat_id=chat_id, text="Webhook received successfully")
                logger.info("🧪 DIAG: send_message succeeded")
            except Exception:
                logger.exception("🧪 DIAG: send_message failed")

    except Exception:
        logger.exception("❌ FULL EXCEPTION TRACEBACK during webhook handler")
        raise

    return Response(status_code=200)


@app.get("/api/set_webhook")
async def set_webhook():
    if not WEBHOOK_URL:
        raise HTTPException(status_code=500, detail="WEBHOOK_URL environment variable is not set")

    webhook_endpoint = f"{WEBHOOK_URL.rstrip('/')}/api/webhook"

    try:
        success = await ptb_app.bot.set_webhook(url=webhook_endpoint)
        if success:
            return {"status": "success", "message": f"Webhook successfully set to {webhook_endpoint}"}
        return {"status": "error", "message": "Failed to set webhook"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def root():
    return {"status": "ok", "message": "Movie Bot Serverless Backend is running"}


@app.get("/api/health/config")
def config_health():
    required = {
        "telegram": bool(TELEGRAM_BOT_TOKEN),
        "groq": bool(os.getenv("GROQ_API_KEY")),
        "tavily": bool(os.getenv("TAVILY_API_KEY")),
        "supabase_url": bool(os.getenv("SUPABASE_URL")),
        "supabase_service_role": bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY")),
    }
    storage = get_storage_status()
    return {
        "status": "ok" if all(required.values()) and storage["ok"] else "not_ready",
        "configured": required,
        "storage": storage,
    }

