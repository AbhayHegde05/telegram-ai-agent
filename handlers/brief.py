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
from utils.memory import (
    log_event, save_user_data,
    async_log_event, async_save_user_data, async_log_interaction,
)
from utils.helpers import split_message, sanitize_movie_name, is_valid_movie_name
from services.groq_service import get_groq_service
from services.search_service import SearchService

logger = logging.getLogger(__name__)


def _is_ambiguous_title_response(text: str) -> bool:
    return (text or "").strip().startswith("AMBIGUOUS_TITLE:")


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
        user_id = update.effective_user.id if update.effective_user else None
        username = update.effective_user.username if update.effective_user else None
        if user_id:
            await async_save_user_data(user_id, {}, 'brief')
            await async_log_interaction(user_id, username, "brief_start",
                                         input_text="brief_flow",
                                         metadata={"action": "flow_started"})

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
    user_id = update.effective_user.id if update.effective_user else None
    movie_name_for_log = None
    try:
        movie_name = sanitize_movie_name(update.message.text)
        movie_name_for_log = movie_name if movie_name else None

        if user_id:
            try:
                await async_log_event(
                    user_id,
                    "brief_input",
                    {"movie_name": (movie_name_for_log or "")[:200]},
                    endpoint=context.bot_data.get("audit_endpoint", "bot.polling"),
                    update_kind="message",
                    handler="handle_brief_movie_name"
                )
            except Exception:
                pass

        if not is_valid_movie_name(movie_name):
            await update.message.reply_text(
                "❌ Please enter a valid movie name.\n\n"
                "Example: Interstellar"
            )
            return

        if len(movie_name.strip()) == 1:
            await update.message.reply_text(
                f"I found multiple movies that could match '{movie_name}'. "
                "Please include the release year or language.\n\n"
                "Example: A 1998 Kannada"
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
            if search_service.last_error and user_id:
                await async_log_event(
                    user_id,
                    "service_error",
                    {
                        "service": "tavily",
                        "error": search_service.last_error[:500],
                        "movie_name": movie_name[:200],
                    },
                    endpoint=context.bot_data.get("audit_endpoint", "bot.polling"),
                    update_kind="message",
                    handler="handle_brief_movie_name"
                )
        except Exception as e:
            logger.error(f"Search error: {e}")
            search_results = f"Movie: {movie_name}\nSearch results unavailable. Please try another movie."
            if user_id:
                await async_log_event(
                    user_id,
                    "service_error",
                    {"service": "tavily", "error": str(e)[:500], "movie_name": movie_name[:200]},
                    endpoint=context.bot_data.get("audit_endpoint", "bot.polling"),
                    update_kind="message",
                    handler="handle_brief_movie_name"
                )

        # Generate brief
        try:
            brief = await groq_service.get_movie_brief(movie_name, search_results)

            if brief is None:
                raise Exception("Groq returned None")
            if groq_service.last_error and user_id:
                await async_log_event(
                    user_id,
                    "service_error",
                    {
                        "service": "groq",
                        "error": groq_service.last_error[:500],
                        "movie_name": movie_name[:200],
                    },
                    endpoint=context.bot_data.get("audit_endpoint", "bot.polling"),
                    update_kind="message",
                    handler="handle_brief_movie_name"
                )
        except Exception as e:
            logger.error(f"Error generating brief: {e}")
            brief = "Sorry, I couldn't generate a brief right now. Please try again shortly."
            if user_id:
                await async_log_event(
                    user_id,
                    "service_error",
                    {"service": "groq", "error": str(e)[:500], "movie_name": movie_name[:200]},
                    endpoint=context.bot_data.get("audit_endpoint", "bot.polling"),
                    update_kind="message",
                    handler="handle_brief_movie_name"
                )

        if _is_ambiguous_title_response(brief):
            await processing_message.edit_text(
                f"I found multiple movies named '{movie_name}'. "
                "Please send the title again with its release year or language.\n\n"
                "Example: A 1998 Kannada"
            )
            return

        if user_id:
            try:
                await async_log_event(
                    user_id,
                    "brief_output",
                    {"movie_name": (movie_name_for_log or "")[:200], "brief": (brief or "")[:1500]},
                    endpoint=context.bot_data.get("audit_endpoint", "bot.polling"),
                    update_kind="message",
                    handler="handle_brief_movie_name"
                )
                await async_log_interaction(
                    user_id,
                    update.effective_user.username if update.effective_user else None,
                    "brief_complete",
                    input_text=movie_name_for_log or "",
                    response_text=(brief or "")[:500],
                    metadata={"action": "brief_generated", "movie_name": movie_name_for_log or ""},
                )
            except Exception:
                pass

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
        try:
            await processing_message.edit_text(text=chunks[0], parse_mode="Markdown")
        except TelegramError:
            await processing_message.edit_text(text=chunks[0])
        
        # Send remaining chunks as new messages (Markdown so **bold** renders)
        for chunk in chunks[1:]:
            try:
                await update.message.reply_text(chunk, parse_mode="Markdown")
            except TelegramError:
                await update.message.reply_text(chunk)

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
