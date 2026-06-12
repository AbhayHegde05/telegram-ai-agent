"""
Core PTB handlers for the Telegram bot.
Extracted from main.py so api/index.py can import these without triggering main.py's side effects.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import Conflict, NetworkError

from handlers.help import handle_help as send_help
from handlers.brief import handle_brief_movie_name
from handlers.review import handle_review_movie_name
from keyboards.menu import start_menu, get_start_menu_keyboard
from utils.helpers import rate_limiter
from utils.states import clear_feature_state, RecommendationPreferences
from utils.memory import (
    load_user_data, save_user_data, add_history, log_event, start_session, end_session,
    async_load_user_data, async_save_user_data, async_add_history,
    async_log_event, async_start_session, async_end_session,
)

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command - Display main menu"""
    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None

    logger.info(
        "🚦 START handler entry user_id=%s chat_id=%s has_message=%s",
        user_id,
        chat_id,
        bool(update.message),
    )

    try:
        if user_id:
            user = update.effective_user
            chat = update.effective_chat
            await async_start_session(
                user_id,
                chat_id=chat.id if chat else None,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                force_new=context.bot_data.get("audit_endpoint") != "/api/webhook",
            )
            await async_log_event(
                user_id,
                "handler_start",
                {"command": "start"},
                endpoint=context.bot_data.get("audit_endpoint", "bot.polling"),
                update_kind="message",
                handler="start",
            )
    except Exception:
        logger.exception("❌ Error inside START session/logging")
        # do not return; we still try to send the menu

    if user_id:
        try:
            saved = await async_load_user_data(user_id)
            if saved:
                context.user_data.update(saved)
                if 'preferences' in saved and isinstance(saved['preferences'], dict):
                    context.user_data['preferences'] = RecommendationPreferences.from_dict(saved['preferences'])
        except Exception:
            logger.exception("❌ Error loading user data in START")

    # Primary path (old behavior)
    if update.message is not None:
        logger.info("📨 START sending menu via update.message.reply_text")
        await start_menu(update, context)
        return

    # Fallback for webhook cases where update.message may be missing
    if chat_id is None:
        logger.error("❌ START cannot send menu: chat_id is None")
        return

    logger.info("📨 START fallback sending menu via context.bot.send_message")
    await context.bot.send_message(
        chat_id=chat_id,
        text="🎬 Welcome to Movie Assistant\n\nChoose what you would like to do:",
        reply_markup=get_start_menu_keyboard(),
    )


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log and display the help guide."""
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        await async_log_event(
            user_id,
            "handler_start",
            {"command": "help"},
            endpoint=context.bot_data.get("audit_endpoint", "bot.polling"),
            update_kind="message",
            handler="help",
        )

    await send_help(update, context)


async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel current flow and return to main menu"""
    try:
        user_id = update.effective_user.id if update.effective_user else None
        if user_id:
            await async_log_event(
                user_id,
                "handler_start",
                {"callback": "cancel"},
                endpoint=context.bot_data.get("audit_endpoint", "bot.polling"),
                handler="handle_cancel",
                update_kind="callback_query",
            )
    except Exception:
        logger.exception("❌ error in handle_cancel logging")

    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id if update.effective_user else None
    clear_feature_state(context)

    if user_id:
        await async_save_user_data(user_id, {}, None)

    await query.edit_message_text(
        text="✅ Cancelled.\n\nChoose what you would like to do:",
        reply_markup=get_start_menu_keyboard(),
    )


async def endchat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """End chat flow and clear user state."""
    user_id = update.effective_user.id if update.effective_user else None
    try:
        if user_id:
            await async_log_event(
                user_id,
                "handler_start",
                {"command": "endchat"},
                endpoint=context.bot_data.get("audit_endpoint", "bot.polling"),
                update_kind="message",
                handler="endchat",
            )
    except Exception:
        logger.exception("❌ error in endchat logging")

    clear_feature_state(context)
    if user_id:
        await async_end_session(user_id)

    await update.message.reply_text(
        "👋 Thank you for visiting Movie Assistant! See you again soon—send /start to begin anytime."
    )


async def handle_brief_or_review_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route text input to brief or review handlers based on current state"""
    user_id = update.effective_user.id if update.effective_user else None

    if user_id:
        try:
            if update.message and update.message.text:
                await async_log_event(
                    user_id,
                    "handler_start",
                    {"feature_router_text": update.message.text[:200]},
                    endpoint=context.bot_data.get("audit_endpoint", "bot.polling"),
                    handler="handle_brief_or_review_input",
                    update_kind="message",
                )
        except Exception:
            logger.exception("❌ rate/router logging failed")

    if user_id and not rate_limiter.is_allowed(user_id):
        await update.message.reply_text(
            "⏳ You're sending too many requests. Please wait a moment and try again."
        )
        return

    if user_id and not context.user_data.get('current_feature'):
        saved = await async_load_user_data(user_id)
        if saved:
            context.user_data.update(saved)
            if 'preferences' in saved and isinstance(saved['preferences'], dict):
                context.user_data['preferences'] = RecommendationPreferences.from_dict(saved['preferences'])

    current_feature = context.user_data.get('current_feature')

    if current_feature == 'brief':
        await handle_brief_movie_name(update, context)
        if user_id:
            prefs = context.user_data.get('preferences')
            await async_save_user_data(user_id, prefs.to_dict() if prefs else {}, current_feature)
            await async_add_history(user_id, 'brief', update.message.text, 'brief_generated')
    elif current_feature == 'review':
        await handle_review_movie_name(update, context)
        if user_id:
            prefs = context.user_data.get('preferences')
            await async_save_user_data(user_id, prefs.to_dict() if prefs else {}, current_feature)
            await async_add_history(user_id, 'review', update.message.text, 'review_generated')
    else:
        pass


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors with graceful recovery and user notification"""
    error = context.error

    if isinstance(error, Conflict):
        logger.error(f"⚠️ Conflict error (multiple instances?): {error}")
        raise error

    if isinstance(error, NetworkError):
        logger.warning(f"⚠️ Network error (transient): {error}")
        return

    logger.error(f"❌ Error: {type(error).__name__}: {error}", exc_info=True)

    if update is not None:
        try:
            if getattr(update, "message", None) is not None:
                await update.message.reply_text("❌ An unexpected error occurred. Please try again.")
            elif getattr(update, "callback_query", None) is not None and update.callback_query.message is not None:
                await update.callback_query.message.reply_text("❌ An unexpected error occurred. Please try again.")
        except Exception:
            logger.exception("❌ error_handler notification failed")
