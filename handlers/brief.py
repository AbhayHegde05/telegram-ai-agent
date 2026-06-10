"""
Movie Brief handler
Manages movie brief feature - asks for movie name and generates summary
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from keyboards.menu import get_start_menu_keyboard
from utils.states import init_user_data, set_current_feature
from utils.helpers import split_message, sanitize_movie_name, is_valid_movie_name
from services.groq_service import get_groq_service
from services.search_service import SearchService

logger = logging.getLogger(__name__)


async def start_brief(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Start the movie brief feature
    Ask user to enter movie name
    """
    try:
        query = update.callback_query
        await query.answer()

        init_user_data(context)
        set_current_feature(context, 'brief')

        await query.edit_message_text(
            text="📖 Movie Brief\n\n"
                 "Please enter the movie name.\n\n"
                 "Example: Interstellar"
        )
    except TelegramError as e:
        logger.error(f"Telegram error in start_brief: {e}")


async def handle_brief_movie_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle movie name input and generate brief
    """
    try:
        movie_name = sanitize_movie_name(update.message.text)

        if not is_valid_movie_name(movie_name):
            await update.message.reply_text(
                "❌ Please enter a valid movie name (at least 2 characters).\n\n"
                "Example: Interstellar"
            )
            return

        # Show processing message
        processing_message = await update.message.reply_text(
            f"🔍 Searching for '{movie_name}'...\n"
            "📖 Generating summary...\n"
            "⏳ Please wait..."
        )

        # Initialize services
        try:
            groq_service = get_groq_service()
            search_service = SearchService()
        except Exception as e:
            logger.error(f"Error initializing services: {e}")
            await processing_message.edit_text(
                "❌ Service initialization error. Please try again."
            )
            return

        # Search for movie information
        try:
            search_results = await search_service.search_movie_info(movie_name)
        except Exception as e:
            logger.error(f"Search error: {e}")
            search_results = f"Movie: {movie_name}\nSearch results unavailable. Please try another movie."

        # Generate brief
        try:
            brief = await groq_service.get_movie_brief(movie_name, search_results)
            
            if brief is None:
                raise Exception("Groq returned None")
        except Exception as e:
            logger.error(f"Error generating brief: {e}")
            brief = f"Sorry, I couldn't find reliable information for '{movie_name}'."

        # Build the full response
        full_response = (
            "📖 MOVIE BRIEF\n\n"
            + brief +
            "\n\n━━━━━━━━━━━━━━\n"
            "Would you like to try another feature?"
        )

        # Split and send in chunks if needed
        chunks = split_message(full_response)
        
        # Edit the processing message with first chunk (Markdown so **bold** renders)
        await processing_message.edit_text(text=chunks[0], parse_mode="Markdown")
        
        # Send remaining chunks as new messages (Markdown so **bold** renders)
        for chunk in chunks[1:]:
            await update.message.reply_text(chunk, parse_mode="Markdown")

        # Add menu options
        await update.message.reply_text(
            "Choose an option:",
            reply_markup=get_start_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Unexpected error in handle_brief_movie_name: {e}")
        try:
            await update.message.reply_text(
                text="❌ Sorry, an unexpected error occurred.\n\n"
                     "Please try another movie name."
            )
        except:
            pass
