"""
Movie Recommendation handler
Manages the multi-step preference collection and recommendation flow
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from keyboards.menu import (
    get_language_keyboard,
    get_genre_keyboard,
    get_duration_keyboard,
    get_release_preference_keyboard,
    get_mood_preference_keyboard,
    get_start_menu_keyboard
)
from utils.states import init_user_data, get_preferences, set_current_feature
from services.groq_service import GroqService
from services.search_service import SearchService

logger = logging.getLogger(__name__)


async def start_recommendation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Start the movie recommendation flow
    Ask for preferred language as first question
    """
    try:
        query = update.callback_query
        await query.answer()

        init_user_data(context)
        set_current_feature(context, 'recommendation')

        # Start with language question
        await query.edit_message_text(
            text="🎯 Movie Recommendation\n\n"
                 "Step 1 of 5\n\n"
                 "Which language do you prefer?",
            reply_markup=get_language_keyboard()
        )
    except TelegramError as e:
        logger.error(f"Telegram error in start_recommendation: {e}")


async def handle_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle language selection and move to genre selection
    """
    try:
        query = update.callback_query
        await query.answer()

        # Extract language from callback data
        language = query.data.replace("rec_lang_", "").capitalize()

        # Store preference
        preferences = get_preferences(context)
        preferences.language = language

        # Move to genre question
        await query.edit_message_text(
            text="✅ Language selected: " + language + "\n\n"
                 "Step 2 of 5\n\n"
                 "Which genre are you interested in?",
            reply_markup=get_genre_keyboard()
        )
    except TelegramError as e:
        logger.error(f"Telegram error in handle_language_selection: {e}")


async def handle_genre_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle genre selection and move to duration selection
    """
    try:
        query = update.callback_query
        await query.answer()

        # Extract genre from callback data
        genre = query.data.replace("rec_genre_", "").capitalize()

        # Store preference
        preferences = get_preferences(context)
        preferences.genre = genre

        # Move to duration question
        await query.edit_message_text(
            text="✅ Genre selected: " + genre + "\n\n"
                 "Step 3 of 5\n\n"
                 "Preferred duration?",
            reply_markup=get_duration_keyboard()
        )
    except TelegramError as e:
        logger.error(f"Telegram error in handle_genre_selection: {e}")


async def handle_duration_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle duration selection and move to release preference
    """
    try:
        query = update.callback_query
        await query.answer()

        # Extract duration from callback data
        duration_map = {
            "rec_duration_short": "Less than 2 hours",
            "rec_duration_medium": "2-3 hours",
            "rec_duration_long": "More than 3 hours",
            "rec_duration_any": "Any"
        }
        duration = duration_map.get(query.data, "Any")

        # Store preference
        preferences = get_preferences(context)
        preferences.duration = duration

        # Move to release preference question
        await query.edit_message_text(
            text="✅ Duration selected: " + duration + "\n\n"
                 "Step 4 of 5\n\n"
                 "Release preference?",
            reply_markup=get_release_preference_keyboard()
        )
    except TelegramError as e:
        logger.error(f"Telegram error in handle_duration_selection: {e}")


async def handle_release_preference(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle release preference and move to mood preference
    """
    try:
        query = update.callback_query
        await query.answer()

        # Extract release preference from callback data
        release_map = {
            "rec_release_latest": "Latest",
            "rec_release_5years": "Last 5 Years",
            "rec_release_classic": "Classic",
            "rec_release_any": "Any"
        }
        release = release_map.get(query.data, "Any")

        # Store preference
        preferences = get_preferences(context)
        preferences.release = release

        # Move to mood preference question
        await query.edit_message_text(
            text="✅ Release preference selected: " + release + "\n\n"
                 "Step 5 of 5\n\n"
                 "Mood preference?",
            reply_markup=get_mood_preference_keyboard()
        )
    except TelegramError as e:
        logger.error(f"Telegram error in handle_release_preference: {e}")


async def handle_mood_preference(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle mood preference - final step
    Then process and generate recommendations
    """
    try:
        query = update.callback_query
        await query.answer()

        # Extract mood from callback data
        mood_map = {
            "rec_mood_mindblowing": "Mind-Blowing",
            "rec_mood_feelgood": "Feel-Good",
            "rec_mood_emotional": "Emotional",
            "rec_mood_inspirational": "Inspirational",
            "rec_mood_dark": "Dark",
            "rec_mood_funny": "Funny",
            "rec_mood_any": "Any"
        }
        mood = mood_map.get(query.data, "Any")

        # Store preference
        preferences = get_preferences(context)
        preferences.mood = mood

        # Show processing message
        await query.edit_message_text(
            text="✅ Mood preference selected: " + mood + "\n\n"
                 "🔍 Searching movies...\n"
                 "⏳ Analyzing options...\n"
                 "✨ Generating recommendations..."
        )

        # Now process and generate recommendations
        await generate_recommendations(query, context)

    except TelegramError as e:
        logger.error(f"Telegram error in handle_mood_preference: {e}")


async def generate_recommendations(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Generate movie recommendations based on collected preferences
    """
    try:
        preferences = get_preferences(context)

        # Initialize services
        try:
            groq_service = GroqService()
            search_service = SearchService()
        except Exception as e:
            logger.error(f"Error initializing services: {e}")
            await query.edit_message_text(
                text="❌ Service initialization error. Please try again later."
            )
            return

        # Generate search query
        try:
            search_query = groq_service.generate_search_query(preferences.to_dict())
        except Exception as e:
            logger.error(f"Error generating search query: {e}")
            search_query = f"{preferences.genre} movies"

        # Search for movies
        try:
            search_results = search_service.search_movies(search_query, num_results=10)
        except Exception as e:
            logger.error(f"Search error: {e}")
            search_results = "Unable to search movies. Using general information."

        # Get recommendations from Groq
        try:
            recommendations = groq_service.get_movie_recommendations(
                preferences.to_dict(),
                search_results
            )
            
            if recommendations is None:
                raise Exception("Groq returned None")
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            recommendations = "Sorry, I couldn't generate recommendations at this time. Please try again."

        # Send recommendations
        await query.edit_message_text(
            text="🎬 TOP 5 MOVIE RECOMMENDATIONS\n\n"
                 + recommendations +
                 "\n\n━━━━━━━━━━━━━━\n"
                 "Would you like another recommendation or try a different feature?"
        )

        # Add option to start again
        from keyboards.menu import get_start_menu_keyboard
        await query.message.reply_text(
            "Choose an option:",
            reply_markup=get_start_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Unexpected error in generate_recommendations: {e}")
        await query.edit_message_text(
            text="❌ Sorry, an unexpected error occurred.\n\n"
                 "Please try again."
        )
        try:
            from keyboards.menu import get_start_menu_keyboard
            await query.message.reply_text(
                "Choose an option:",
                reply_markup=get_start_menu_keyboard()
            )
        except:
            pass
