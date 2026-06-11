"""
Telegram Movie Assistant Bot - Main Entry Point
Handles /start command and routes to appropriate handlers
"""

import logging
import sys
import os
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv

# Load environment variables FIRST, before importing anything that reads env vars
load_dotenv()

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import Conflict, NetworkError, TimedOut

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
from handlers.help import handle_help as send_help
from keyboards.menu import start_menu, get_start_menu_keyboard
from utils.helpers import rate_limiter
from utils.states import clear_feature_state, RecommendationPreferences
from utils.memory import (
    init_db,
    load_user_data,
    save_user_data,
    add_history,
    log_event,
    start_session,
    end_session,
)

# Initialize SQLite memory database
init_db()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def run_dummy_server(port):
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"Dummy HTTP server started on port {port} for health checks.")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Failed to start dummy server: {e}")


# Get bot token
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    logger.critical("❌ TELEGRAM_BOT_TOKEN not found in environment variables")
    sys.exit(1)

logger.info("✅ Bot token loaded successfully")

# Local lock to reduce accidental duplicate polling starts (best-effort on a single host)
LOCK_FILE = os.path.join(os.path.dirname(__file__), ".bot_lock")
LOCK_STALE_SECONDS = 300  # treat locks older than 5 minutes as stale


def _is_pid_running(pid: int) -> bool:
    """
    Best-effort PID liveness check on Windows.
    """
    try:
        import subprocess
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        return str(pid) in out
    except Exception:
        return False


def _acquire_lock() -> None:
    """
    Create a PID lock file so only one instance runs on the same machine.
    Stale locks are automatically overwritten to avoid startup deadlocks after crashes.
    """
    try:
        if os.path.exists(LOCK_FILE):
            existing_pid = None
            try:
                with open(LOCK_FILE, "r", encoding="utf-8") as f:
                    existing_pid = (f.read() or "").strip()
            except Exception:
                existing_pid = None

            lock_age = time.time() - os.path.getmtime(LOCK_FILE)

            if lock_age > LOCK_STALE_SECONDS:
                logger.warning(f"⚠️ Stale bot lock detected (age={int(lock_age)}s). Overwriting {LOCK_FILE}.")
            else:
                if existing_pid and existing_pid.isdigit():
                    pid_int = int(existing_pid)
                    if _is_pid_running(pid_int):
                        raise RuntimeError(f"Bot lock exists (pid={existing_pid}) at {LOCK_FILE}")
                logger.warning(f"⚠️ Bot lock exists but pid is not running. Overwriting {LOCK_FILE}.")

        with open(LOCK_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.critical(f"❌ Unable to acquire bot lock: {e}")
        raise


def _release_lock() -> None:
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass


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
            start_session(
                user_id,
                chat_id=chat.id if chat else None,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                force_new=context.bot_data.get("audit_endpoint") != "/api/webhook",
            )
            log_event(
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
            saved = load_user_data(user_id)
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
        log_event(
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
            log_event(
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
        save_user_data(user_id, {}, None)

    await query.edit_message_text(
        text="✅ Cancelled.\n\nChoose what you would like to do:",
        reply_markup=get_start_menu_keyboard(),
    )


async def endchat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """End chat flow and clear user state."""
    user_id = update.effective_user.id if update.effective_user else None
    try:
        if user_id:
            log_event(
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
        end_session(user_id)

    await update.message.reply_text(
        "👋 Thank you for visiting Movie Assistant! See you again soon—send /start to begin anytime."
    )


async def handle_brief_or_review_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route text input to brief or review handlers based on current state"""
    user_id = update.effective_user.id if update.effective_user else None

    if user_id:
        try:
            if update.message and update.message.text:
                log_event(
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
        saved = load_user_data(user_id)
        if saved:
            context.user_data.update(saved)
            if 'preferences' in saved and isinstance(saved['preferences'], dict):
                context.user_data['preferences'] = RecommendationPreferences.from_dict(saved['preferences'])

    current_feature = context.user_data.get('current_feature')

    if current_feature == 'brief':
        await handle_brief_movie_name(update, context)
        if user_id:
            prefs = context.user_data.get('preferences')
            save_user_data(user_id, prefs.to_dict() if prefs else {}, current_feature)
            add_history(user_id, 'brief', update.message.text, 'brief_generated')
    elif current_feature == 'review':
        await handle_review_movie_name(update, context)
        if user_id:
            prefs = context.user_data.get('preferences')
            save_user_data(user_id, prefs.to_dict() if prefs else {}, current_feature)
            add_history(user_id, 'review', update.message.text, 'review_generated')
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


def main():
    """Start the bot"""
    port = os.environ.get("PORT")
    if port:
        try:
            port = int(port)
            server_thread = threading.Thread(target=run_dummy_server, args=(port,), daemon=True)
            server_thread.start()
        except ValueError:
            pass

    try:
        _acquire_lock()

        logger.info("🚀 Starting Telegram Movie Assistant Bot...")

        max_retries = 5
        retry_delay_seconds = 3
        max_consecutive_conflicts = 5
        consecutive_conflicts = 0

        logger.info("🤖 Bot will start polling (with retries if startup times out)...")

        for attempt in range(1, max_retries + 1):
            try:
                application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
                application.bot_data["audit_endpoint"] = "bot.polling"

                application.add_error_handler(error_handler)

                application.add_handler(CommandHandler("start", start))
                application.add_handler(CommandHandler("help", handle_help))
                application.add_handler(CommandHandler("endchat", endchat))

                application.add_handler(CallbackQueryHandler(handle_cancel, pattern="^cancel$"))

                application.add_handler(CallbackQueryHandler(start_recommendation, pattern="^rec_start$"))
                application.add_handler(CallbackQueryHandler(start_brief, pattern="^brief_start$"))
                application.add_handler(CallbackQueryHandler(start_review, pattern="^review_start$"))

                application.add_handler(CallbackQueryHandler(handle_language_selection, pattern="^rec_lang_"))
                application.add_handler(CallbackQueryHandler(handle_genre_selection, pattern="^rec_genre_"))
                application.add_handler(CallbackQueryHandler(handle_duration_selection, pattern="^rec_duration_"))
                application.add_handler(CallbackQueryHandler(handle_release_preference, pattern="^rec_release_"))
                application.add_handler(CallbackQueryHandler(handle_mood_preference, pattern="^rec_mood_"))

                application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_brief_or_review_input))

                logger.info(f"🤖 Bot started successfully (attempt {attempt}/{max_retries})!")
                application.run_polling()
                break

            except TimedOut as e:
                consecutive_conflicts = 0
                if attempt >= max_retries:
                    raise
                logger.warning(
                    f"⚠️ Polling startup timed out (attempt {attempt}/{max_retries}): {e}. Retrying in {retry_delay_seconds}s..."
                )
                time.sleep(retry_delay_seconds)

            except Conflict as e:
                consecutive_conflicts += 1
                logger.error(
                    f"⚠️ Conflict (getUpdates): {e} (consecutive={consecutive_conflicts}/{max_consecutive_conflicts})"
                )
                if consecutive_conflicts >= max_consecutive_conflicts:
                    logger.error("Too many consecutive Telegram polling conflicts. Exiting to allow clean restart.")
                    sys.exit(1)

                logger.info(f"Backoff before retrying polling: {retry_delay_seconds}s")
                time.sleep(retry_delay_seconds)

    except Conflict as e:
        logger.error(f"⚠️ Conflict: {e}")
        logger.info("Another bot instance is running with this token.")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"❌ Fatal error: {type(e).__name__}: {e}", exc_info=True)
        sys.exit(1)
    finally:
        _release_lock()


if __name__ == '__main__':
    main()

