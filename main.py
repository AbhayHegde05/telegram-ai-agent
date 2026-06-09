"""
Telegram Movie Assistant Bot - Main Entry Point
Handles /start command and routes to appropriate handlers
"""

import logging
import sys
import os
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


def main():
    """Start the bot"""
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
