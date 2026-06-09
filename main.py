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
from handlers.help import handle_help
from keyboards.menu import start_menu, get_start_menu_keyboard
from utils.helpers import rate_limiter
from utils.states import clear_feature_state, RecommendationPreferences
from utils.memory import init_db, load_user_data, save_user_data, add_history

# Load environment variables
load_dotenv()

# Initialize SQLite memory database
init_db()

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

logger.info("✅ Bot token loaded successfully")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Start command - Display main menu
    """
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        saved = load_user_data(user_id)
        if saved:
            context.user_data.update(saved)
            if 'preferences' in saved and isinstance(saved['preferences'], dict):
                context.user_data['preferences'] = RecommendationPreferences.from_dict(saved['preferences'])
    await start_menu(update, context)


async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Cancel current flow and return to main menu
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id if update.effective_user else None
    clear_feature_state(context)

    # Save cleared state
    if user_id:
        save_user_data(user_id, {}, None)

    await query.edit_message_text(
        text="✅ Cancelled.\n\n"
             "Choose what you would like to do:",
        reply_markup=get_start_menu_keyboard()
    )


async def handle_brief_or_review_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Route text input to brief or review handlers based on current state
    """
    # Rate limiting check
    user_id = update.effective_user.id if update.effective_user else None
    if user_id and not rate_limiter.is_allowed(user_id):
        await update.message.reply_text(
            "⏳ You're sending too many requests. Please wait a moment and try again."
        )
        return

    # Load saved data if user_data is empty
    if user_id and not context.user_data.get('current_feature'):
        saved = load_user_data(user_id)
        if saved:
            context.user_data.update(saved)
            if 'preferences' in saved and isinstance(saved['preferences'], dict):
                context.user_data['preferences'] = RecommendationPreferences.from_dict(saved['preferences'])

    current_feature = context.user_data.get('current_feature')

    # Only handle input if we're in brief or review mode
    if current_feature == 'brief':
        await handle_brief_movie_name(update, context)
        # Save state after handling
        if user_id:
            prefs = context.user_data.get('preferences')
            save_user_data(user_id, prefs.to_dict() if prefs else {}, current_feature)
            add_history(user_id, 'brief', update.message.text, 'brief_generated')
    elif current_feature == 'review':
        await handle_review_movie_name(update, context)
        # Save state after handling
        if user_id:
            prefs = context.user_data.get('preferences')
            save_user_data(user_id, prefs.to_dict() if prefs else {}, current_feature)
            add_history(user_id, 'review', update.message.text, 'review_generated')
    else:
        # Ignore text that's not part of a feature flow
        pass


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle errors with graceful recovery and user notification
    """
    error = context.error

    if isinstance(error, Conflict):
        logger.error(f"⚠️ Conflict error (multiple instances?): {error}")
        return

    if isinstance(error, NetworkError):
        logger.warning(f"⚠️ Network error (transient): {error}")
        return

    logger.error(f"❌ Error: {type(error).__name__}: {error}")

    # Notify user if an update object is available
    if update is not None:
        try:
            if update.message is not None:
                await update.message.reply_text(
                    "❌ An unexpected error occurred. Please try again."
                )
            elif update.callback_query is not None and update.callback_query.message is not None:
                await update.callback_query.message.reply_text(
                    "❌ An unexpected error occurred. Please try again."
                )
        except Exception:
            pass


def main():
    """Start the bot"""
    try:
        logger.info("🚀 Starting Telegram Movie Assistant Bot...")

        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Error handler
        application.add_error_handler(error_handler)

        # Command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", handle_help))

        # Cancel handler
        application.add_handler(CallbackQueryHandler(handle_cancel, pattern="^cancel$"))

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
