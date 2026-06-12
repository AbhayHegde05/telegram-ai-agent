import logging
import os
import sys
import traceback

from dotenv import load_dotenv
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, HTTPException

# Load environment variables FIRST
load_dotenv()

# ---- Vercel debug hook: wrap ALL startup code so traceback shows in function logs ----
try:
    # Logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    logger = logging.getLogger(__name__)

    # Telegram imports (safe)
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        CallbackQueryHandler,
        MessageHandler,
        filters,
    )

    # Handlers imports - never let module import fail
    try:
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
    except Exception:
        traceback.print_exc()
        logger.exception("❌ Failed importing telegram handlers (routes must still register).")
        start_recommendation = None  # type: ignore[assignment]
        handle_language_selection = None  # type: ignore[assignment]
        handle_genre_selection = None  # type: ignore[assignment]
        handle_duration_selection = None  # type: ignore[assignment]
        handle_release_preference = None  # type: ignore[assignment]
        handle_mood_preference = None  # type: ignore[assignment]
        start_brief = None  # type: ignore[assignment]
        handle_brief_movie_name = None  # type: ignore[assignment]
        start_review = None  # type: ignore[assignment]
        handle_review_movie_name = None  # type: ignore[assignment]

    # Utils imports - never let module import fail
    try:
        from utils.memory import get_storage_status, init_db, log_event, start_session
    except Exception:
        traceback.print_exc()
        logger.exception("❌ Failed importing utils.memory (routes must still register).")
        get_storage_status = lambda: {"ok": False, "error": "utils.memory unavailable"}  # type: ignore
        init_db = None  # type: ignore
        log_event = None  # type: ignore
        start_session = None  # type: ignore

    # main imports
    try:
        from main import (
            start,
            handle_help,
            endchat,
            handle_cancel,
            handle_brief_or_review_input,
            error_handler,
        )
    except Exception:
        traceback.print_exc()
        logger.exception("❌ Failed importing main handlers (routes must still register).")
        start = None  # type: ignore
        handle_help = None  # type: ignore
        endchat = None  # type: ignore
        handle_cancel = None  # type: ignore
        handle_brief_or_review_input = None  # type: ignore
        error_handler = None  # type: ignore

    app = FastAPI(title="Telegram Movie Bot Webhook", lifespan=lifespan)

    ptb_app = None

    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")

    if not TELEGRAM_BOT_TOKEN:
        logger.critical("❌ TELEGRAM_BOT_TOKEN not found; app will still expose FastAPI routes.")
    else:
        try:
            ptb_app = Application.builder().token(TELEGRAM_BOT_TOKEN).updater(None).build()
            ptb_app.bot_data["audit_endpoint"] = "/api/webhook"

            if error_handler:
                ptb_app.add_error_handler(error_handler)

            # Register only if handlers exist
            if start:
                ptb_app.add_handler(CommandHandler("start", start))
            if handle_help:
                ptb_app.add_handler(CommandHandler("help", handle_help))
            if endchat:
                ptb_app.add_handler(CommandHandler("endchat", endchat))

            if handle_cancel:
                ptb_app.add_handler(CallbackQueryHandler(handle_cancel, pattern="^cancel$"))

            if start_recommendation:
                ptb_app.add_handler(CallbackQueryHandler(start_recommendation, pattern="^rec_start$"))
            if start_brief:
                ptb_app.add_handler(CallbackQueryHandler(start_brief, pattern="^brief_start$"))
            if start_review:
                ptb_app.add_handler(CallbackQueryHandler(start_review, pattern="^review_start$"))

            if handle_language_selection:
                ptb_app.add_handler(CallbackQueryHandler(handle_language_selection, pattern="^rec_lang_"))
            if handle_genre_selection:
                ptb_app.add_handler(CallbackQueryHandler(handle_genre_selection, pattern="^rec_genre_"))
            if handle_duration_selection:
                ptb_app.add_handler(CallbackQueryHandler(handle_duration_selection, pattern="^rec_duration_"))
            if handle_release_preference:
                ptb_app.add_handler(CallbackQueryHandler(handle_release_preference, pattern="^rec_release_"))
            if handle_mood_preference:
                ptb_app.add_handler(CallbackQueryHandler(handle_mood_preference, pattern="^rec_mood_"))

            if handle_brief_or_review_input:
                ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_brief_or_review_input))

        except Exception:
            logger.critical("❌ PTB Application.builder().build() failed", exc_info=True)
            traceback.print_exc()
            ptb_app = None

    # ====== Lifespan: runs AFTER all routes are registered ======

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Initialize services after routes are registered (cold start only)."""
        # init_db() — deferred from module level, never crashes startup
        try:
            if init_db:
                await asyncio.to_thread(init_db)
        except Exception:
            logger.critical("❌ init_db() failed during lifespan startup", exc_info=True)
            traceback.print_exc()

        # ptb_app.initialize() — deferred from module level
        if ptb_app is not None:
            try:
                await ptb_app.initialize()
                try:
                    await ptb_app.start()
                except Exception as e:
                    logger.warning("PTB start() unsupported/failed (continuing): %s", repr(e))
                logger.info("✅ PTB initialized and started in lifespan")
            except Exception:
                logger.critical("❌ PTB initialize() failed in lifespan", exc_info=True)
                traceback.print_exc()

        yield

        # Shutdown
        if ptb_app is not None:
            try:
                await ptb_app.stop()
                await ptb_app.shutdown()
            except Exception:
                pass

    # ====== Route Handlers ======

    @app.post("/api/webhook")
    async def telegram_webhook(request: Request):
        logger.info("WEBHOOK HIT")

        if ptb_app is None:
            logger.error("❌ Webhook ignored: ptb_app is None (missing TELEGRAM_BOT_TOKEN or build failed)")
            return Response(status_code=200)

        try:
            data = await request.json()
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

        except Exception:
            logger.exception("❌ FULL EXCEPTION TRACEBACK during webhook handler")
            raise

        return Response(status_code=200)

    @app.get("/api/set_webhook")
    async def set_webhook():
        if ptb_app is None:
            raise HTTPException(status_code=500, detail="ptb_app is not available (TELEGRAM_BOT_TOKEN missing or build failed)")
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
            "status": "ok" if all(required.values()) and storage.get("ok") else "not_ready",
            "configured": required,
            "storage": storage,
        }

except Exception:
    traceback.print_exc()
    # If we crash during module import, still try to create the FastAPI app
    # so Vercel doesn't return a 404 for everything.
    # Create fallback FastAPI app so Vercel doesn't return 404 for all routes
    app = FastAPI(title="Telegram Movie Bot Webhook (Fallback)")

    @app.get("/")
    def root():
        return {
            "status": "error",
            "message": "Module startup failed. Check Vercel function logs for traceback.",
        }

    @app.get("/api/health/config")
    def config_health():
        return {
            "status": "error",
            "message": "Module startup failed. Check Vercel function logs for traceback.",
        }

    @app.get("/api/set_webhook")
    def set_webhook():
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": "Module startup failed; unable to configure webhook."},
        )

    @app.post("/api/webhook")
    async def telegram_webhook():
        return Response(status_code=200)
