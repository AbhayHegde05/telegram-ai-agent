"""
Telegram Movie Assistant Bot - Main Entry Point
Handles /start command and routes to appropriate handlers
"""

import logging
import asyncio
import signal
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import Conflict, NetworkError, BadRequest
import os
from dotenv import load_dotenv

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
    raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")


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
    if not context.user_data:
        context.user_data = {}

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
        logger.error(f"⚠️ Conflict error (another instance running?): {error}")
        logger.info("Shutting down gracefully to resolve conflict...")
        # Don't crash - let container restart
        return
    
    if isinstance(error, (NetworkError, BadRequest)):
        logger.warning(f"Network error (will retry): {error}")
        # These are transient - just log and continue
        return
    
    logger.error(f"Unhandled error: {error}")


async def main_with_retry(max_retries: int = 5, retry_delay: int = 5) -> None:
    """
    Run the bot with automatic retry on conflict
    """
    retry_count = 0
    
    while retry_count < max_retries:
        try:
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
            
            # Run with polling
            await application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                timeout=30,
                read_latency=60.0
            )
            
            # If we get here, polling stopped normally
            break
            
        except Conflict as e:
            retry_count += 1
            logger.error(f"❌ Conflict error (attempt {retry_count}/{max_retries}): {e}")
            
            if retry_count < max_retries:
                logger.info(f"⏳ Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                # Increase delay for next retry
                retry_delay = min(retry_delay * 2, 60)
            else:
                logger.critical("Max retries reached. Exiting.")
                sys.exit(1)
                
        except (NetworkError, BadRequest) as e:
            logger.warning(f"Network error: {e}. Retrying in 10 seconds...")
            await asyncio.sleep(10)
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            sys.exit(1)


if __name__ == '__main__':
    try:
        asyncio.run(main_with_retry())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(1)
