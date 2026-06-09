"""
Movie Review handler
Manages movie review feature - asks for movie name and generates comprehensive review
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


async def start_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Start the movie review feature
    Ask user to enter movie name
    """
    try:
        query = update.callback_query
        await query.answer()

        init_user_data(context)
        set_current_feature(context, 'review')

        await query.edit_message_text(
            text="⭐ Movie Review\n\n"
                 "Please enter the movie name.\n\n"
                 "Example: The Dark Knight"
        )
    except TelegramError as e:
        logger.error(f"Telegram error in start_review: {e}")


async def handle_review_movie_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle movie name input and generate comprehensive review
    """
    try:
        movie_name = sanitize_movie_name(update.message.text)

        if not is_valid_movie_name(movie_name):
            await update.message.reply_text(
                "❌ Please enter a valid movie name (at least 2 characters).\n\n"
                "Example: The Dark Knight"
            )
            return

        # Show processing message
        processing_message = await update.message.reply_text(
            f"🔍 Searching reviews for '{movie_name}'...\n"
            "📊 Analyzing ratings...\n"
            "✍️ Generating comprehensive review...\n"
            "⏳ This may take a moment..."
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

        # Search for movie reviews and ratings
        try:
            search_results = await search_service.search_movie_reviews(movie_name)
        except Exception as e:
            logger.error(f"Search error: {e}")
            search_results = f"Movie: {movie_name}\nSearch results unavailable. Please try another movie."

        # Generate comprehensive review
        try:
            review = await groq_service.get_movie_review(movie_name, search_results)
            
            if review is None:
                raise Exception("Groq returned None")
        except Exception as e:
            logger.error(f"Error generating review: {e}")
            review = f"Sorry, I couldn't find reliable review information for '{movie_name}'."

        # Build the full response
        full_response = (
            "⭐ MOVIE REVIEW\n\n"
            + review +
            "\n\n━━━━━━━━━━━━━━\n"
            "Would you like to review another movie or try a different feature?"
        )

        # Split and send in chunks
        chunks = split_message(full_response)
        
        # Edit the processing message with first chunk
        await processing_message.edit_text(text=chunks[0])
        
        # Send remaining chunks as new messages
        for chunk in chunks[1:]:
            await update.message.reply_text(chunk)

        # Add menu options
        await update.message.reply_text(
            "Choose an option:",
            reply_markup=get_start_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Unexpected error in handle_review_movie_name: {e}")
        try:
            await update.message.reply_text(
                text="❌ Sorry, an unexpected error occurred.\n\n"
                     "Please try another movie name."
            )
        except:
            pass
