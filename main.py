"""
Telegram Movie Assistant Bot - Main Entry Point
Handles /start command and routes to appropriate handlers
"""

import logging
import sys
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import Conflict, NetworkError

# Import handlers
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
from keyboards.menu import start_menu

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get bot token
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    logger.critical("❌ TELEGRAM_BOT_TOKEN not found in environment variables")
    sys.exit(1)

logger.info(f"✅ Bot token loaded: {TELEGRAM_BOT_TOKEN[:20]}...")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Start command - Display main menu
    """
    await start_menu(update, context)


async def handle_brief_or_review_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Route text input to brief or review handlers based on current state
    """
    # Initialize user data if needed
    if context.user_data is None:
        return

    current_feature = context.user_data.get('current_feature')

    # Only handle input if we're in brief or review mode
    if current_feature == 'brief':
        await handle_brief_movie_name(update, context)
    elif current_feature == 'review':
        await handle_review_movie_name(update, context)
    else:
        # Ignore text that's not part of a feature flow
        pass


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle errors with graceful recovery
    """
    error = context.error
    
    if isinstance(error, Conflict):
        logger.error(f"⚠️ Conflict error (multiple instances?): {error}")
        return
    
    if isinstance(error, NetworkError):
        logger.warning(f"⚠️ Network error (transient): {error}")
        return
    
    logger.error(f"❌ Error: {type(error).__name__}: {error}")


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running!")

    def log_message(self, format, *args):
        pass  # Suppress HTTP logging

def start_health_check_server():
    """Starts a dummy HTTP server to satisfy Render web service health checks"""
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"🌐 Starting health check server on port {port}")
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

def main():
    """Start the bot"""
    # Start the dummy web server for Render
    start_health_check_server()

    try:
        logger.info("🚀 Starting Telegram Movie Assistant Bot...")
        
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Error handler
        application.add_error_handler(error_handler)

        # Command handlers
        application.add_handler(CommandHandler("start", start))

        # Callback query handlers for menu
        application.add_handler(CallbackQueryHandler(start_recommendation, pattern="^rec_start$"))
        application.add_handler(CallbackQueryHandler(start_brief, pattern="^brief_start$"))
        application.add_handler(CallbackQueryHandler(start_review, pattern="^review_start$"))

        # Recommendation flow handlers
        application.add_handler(CallbackQueryHandler(handle_language_selection, pattern="^rec_lang_"))
        application.add_handler(CallbackQueryHandler(handle_genre_selection, pattern="^rec_genre_"))
        application.add_handler(CallbackQueryHandler(handle_duration_selection, pattern="^rec_duration_"))
        application.add_handler(CallbackQueryHandler(handle_release_preference, pattern="^rec_release_"))
        application.add_handler(CallbackQueryHandler(handle_mood_preference, pattern="^rec_mood_"))

        # Brief and Review text input handlers
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_brief_or_review_input))

        logger.info("🤖 Bot started successfully!")
        
        # Run the bot
        application.run_polling()
        
    except Conflict as e:
        logger.error(f"⚠️ Conflict: {e}")
        logger.info("Another bot instance is running with this token.")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"❌ Fatal error: {type(e).__name__}: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
