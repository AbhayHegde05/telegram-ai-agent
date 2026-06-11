import logging
import os
import sys
from fastapi import FastAPI, Request, Response, HTTPException
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram import Bot


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

# Try to import the main start, endchat and handle_cancel from main
# However, since main has polling logic and locks, we will just copy the handlers here or import them safely.
# Since we are keeping project structure, we will import them from main but main needs to not run polling on import.
# `main.py` has `if __name__ == '__main__': main()` so importing from it is safe.
from main import start, handle_help, endchat, handle_cancel, handle_brief_or_review_input, error_handler

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize DB (Supabase)
init_db()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

if not TELEGRAM_BOT_TOKEN:
    logger.critical("❌ TELEGRAM_BOT_TOKEN not found in environment variables")
    # Don't exit(1) immediately to allow Vercel to show the error page.

# Build PTB Application with updater=None
ptb_app = Application.builder().token(TELEGRAM_BOT_TOKEN).updater(None).build()
ptb_app.bot_data["audit_endpoint"] = "/api/webhook"

# Error handler
ptb_app.add_error_handler(error_handler)

# Command handlers
ptb_app.add_handler(CommandHandler("start", start))
ptb_app.add_handler(CommandHandler("help", handle_help))
ptb_app.add_handler(CommandHandler("endchat", endchat))

# Cancel handler
ptb_app.add_handler(CallbackQueryHandler(handle_cancel, pattern="^cancel$"))

# Callback query handlers for menu
ptb_app.add_handler(CallbackQueryHandler(start_recommendation, pattern="^rec_start$"))
ptb_app.add_handler(CallbackQueryHandler(start_brief, pattern="^brief_start$"))
ptb_app.add_handler(CallbackQueryHandler(start_review, pattern="^review_start$"))

# Recommendation flow handlers
ptb_app.add_handler(CallbackQueryHandler(handle_language_selection, pattern="^rec_lang_"))
ptb_app.add_handler(CallbackQueryHandler(handle_genre_selection, pattern="^rec_genre_"))
ptb_app.add_handler(CallbackQueryHandler(handle_duration_selection, pattern="^rec_duration_"))
ptb_app.add_handler(CallbackQueryHandler(handle_release_preference, pattern="^rec_release_"))
ptb_app.add_handler(CallbackQueryHandler(handle_mood_preference, pattern="^rec_mood_"))

# Brief and Review text input handlers
ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_brief_or_review_input))


app = FastAPI(title="Telegram Movie Bot Webhook")
_is_initialized = False

@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    """Handle incoming webhook updates from Telegram."""
    global _is_initialized

    # 1) WEBHOOK HIT
    logger.info("WEBHOOK HIT")
    logger.info(
        "📨 Webhook request received: method=%s path=%s headers=%s",
        request.method,
        request.url.path,
        dict(request.headers),
    )

    if not _is_initialized:

        # 3) APPLICATION INITIALIZED
        logger.info("APPLICATION INITIALIZED (starting) -> ptb_app.initialize()")
        try:
            await ptb_app.initialize()
            logger.info("APPLICATION INITIALIZED")

            # IMPORTANT: in webhook mode for ptb v21, initialize() is generally enough.
            # But to be safe in serverless environments, also start the internal
            # task/webhook lifecycle if required by the PTB version.
            # 4) APPLICATION STARTED
            try:
                await ptb_app.start()
                logger.info("APPLICATION STARTED (ptb_app.start())")
            except Exception as e:
                logger.warning("⚠️ APPLICATION START FAILED/UNSUPPORTED (continuing): %s", repr(e))


            _is_initialized = True
            logger.info("✅ PTB initialize() completed.")
        except Exception as e:
            logger.critical("❌ APPLICATION INITIALIZATION FAILED: %s", repr(e), exc_info=True)
            raise



    try:
        # 2) UPDATE RECEIVED
        logger.info("UPDATE RECEIVED (about to read request.json())")
        data = await request.json()
        logger.info("UPDATE RECEIVED (payload keys=%s)", list(data.keys()))


        update = Update.de_json(data, ptb_app.bot)

        # 7) DIAGNOSTIC SEND (bypass PTB handlers)
        try:
            chat_id = None
            if update.message and update.message.chat:
                chat_id = update.message.chat.id
            elif update.effective_chat:
                chat_id = update.effective_chat.id

            logger.info("🧪 DIAG: extracted chat_id=%s", chat_id)
            if chat_id is not None and TELEGRAM_BOT_TOKEN:
                diag_bot = Bot(token=TELEGRAM_BOT_TOKEN)
                resp = await diag_bot.send_message(
                    chat_id=chat_id,
                    text="Webhook received successfully",
                )
                logger.info("🧪 DIAG: send_message response=%s", getattr(resp, "to_dict", lambda: str(resp))())
            else:
                logger.warning("🧪 DIAG: chat_id missing or token missing")
        except Exception as e:
            logger.exception("🧪 DIAG: send_message failed: %s", repr(e))

        # 6) START HANDLER ENTERED will be logged from main.py start() handler.



        # Determine update kind for logging / debugging
        update_kind = "unknown"
        try:
            if update.message:
                update_kind = "message"
            elif update.callback_query:
                update_kind = "callback_query"
        except Exception:
            pass

        logger.info(

            "🧭 Update kind=%s has_message=%s has_callback=%s",
            update_kind,
            bool(getattr(update, "message", None)),
            bool(getattr(update, "callback_query", None)),
        )

        logger.info(
            "🧩 Update parsed: update_id=%s effective_user=%s message_text=%s callback_data=%s has_message=%s has_callback=%s",
            getattr(update, "update_id", None),
            (update.effective_user.id if update.effective_user else None),
            (update.message.text[:200] if update.message and update.message.text else None),
            (update.callback_query.data[:200] if update.callback_query and update.callback_query.data else None),
            bool(getattr(update, "message", None)),
            bool(getattr(update, "callback_query", None)),
        )

        # Trace the PTB internal handler matching process (best-effort)
        try:
            matched = ptb_app.update_processor._check_update(update)  # type: ignore[attr-defined]
            logger.info("🎯 Handler matching result (raw)=%s", repr(matched))
        except Exception as e:
            logger.debug("🎯 Handler matching trace not available: %s", repr(e))



        user_id = None
        try:
            user_id = update.effective_user.id if update.effective_user else None
        except Exception:
            user_id = None

        try:
            # Safe payload (avoid dumping entire update)
            payload = {"update_id": update.update_id}
            if update.message:
                if update.message.text:
                    payload["text"] = update.message.text[:500]
                    if update.message.text.startswith("/"):
                        payload["command"] = update.message.text.split(maxsplit=1)[0][:100]
                if update.message.entities:
                    payload["has_entities"] = True
            if update.callback_query:
                payload["callback_data"] = (update.callback_query.data or "")[:500]

            if user_id:
                user = update.effective_user
                chat = update.effective_chat
                command = (
                    update.message.text.split(maxsplit=1)[0].split("@")[0]
                    if update.message and update.message.text
                    else None
                )
                session_id = start_session(
                    user_id,
                    chat_id=chat.id if chat else None,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
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
            logger.exception("❌ FAILED to log webhook event payload (non-fatal)")

        # 5) PROCESSING UPDATE
        logger.info("PROCESSING UPDATE start")
        await ptb_app.process_update(update)
        logger.info("✅ PROCESSING UPDATE end")


        # Reply delivery trace (best-effort): if process_update didn't raise, replies likely already sent.
        try:
            if update.message:
                logger.info(
                    "📤 Reply should be sent for message: text=%s",
                    (update.message.text[:200] if update.message.text else None),
                )
            elif update.callback_query:
                logger.info(
                    "📤 Reply should be sent for callback: data=%s",
                    (update.callback_query.data[:200] if update.callback_query.data else None),
                )
        except Exception:
            logger.exception("❌ REPLY delivery trace failed")

    except Exception as e:
        logger.exception("❌ FULL EXCEPTION TRACEBACK during webhook handler")
        raise

    return Response(status_code=200)




@app.get("/api/set_webhook")
async def set_webhook():
    """Register the webhook URL with Telegram."""
    if not WEBHOOK_URL:
        raise HTTPException(status_code=500, detail="WEBHOOK_URL environment variable is not set")
    
    webhook_endpoint = f"{WEBHOOK_URL.rstrip('/')}/api/webhook"
    
    try:
        success = await ptb_app.bot.set_webhook(url=webhook_endpoint)
        if success:
            return {"status": "success", "message": f"Webhook successfully set to {webhook_endpoint}"}
        else:
            return {"status": "error", "message": "Failed to set webhook"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return {"status": "ok", "message": "Movie Bot Serverless Backend is running"}


@app.get("/api/health/config")
def config_health():
    """Report configuration presence without exposing secret values."""
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
