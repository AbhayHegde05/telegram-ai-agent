import logging
import os
import sys
from fastapi import FastAPI, Request, Response, HTTPException
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from telegram import Update
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
from utils.memory import init_db, log_event

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
    if not _is_initialized:
        await ptb_app.initialize()
        _is_initialized = True

    try:
        data = await request.json()
        update = Update.de_json(data, ptb_app.bot)

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

            log_event(
                user_id or 0,
                "webhook_update",
                payload,
                endpoint="/api/webhook",
                update_kind="message" if update.message else ("callback_query" if update.callback_query else "unknown"),
                handler=None
            )
        except Exception as e:
            logger.error(f"Failed to log webhook event: {e}")

        await ptb_app.process_update(update)
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        # Return 200 anyway so Telegram doesn't keep retrying the failed update
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
