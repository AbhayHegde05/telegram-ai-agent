"""
Help handler
Provides users with information about all available features
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

HELP_TEXT = """🎬 **Movie Assistant - Help Guide**

Here's what I can do:

🎯 **Movie Recommendation**
Tell me your preferences (language, genre, duration, release year, mood) and I'll suggest 5 movies tailored to you.
• Click "Movie Recommendation" from the menu
• Answer 5 quick questions
• Get personalized suggestions!

📖 **Movie Brief**
Want to know what a movie is about without spoilers?
• Click "Movie Brief" from the menu
• Enter a movie name
• Get a spoiler-free summary

⭐ **Movie Review**
Need a detailed breakdown before watching?
• Click "Movie Review" from the menu
• Enter a movie name
• Get a comprehensive review with ratings

🛑 **End Chat**
Finish your session and clear the current flow.
• Send `/endchat`
• (Also clears any in-progress feature state)

❌ **Cancel**
Want to stop what you're doing?
• Click the "Cancel" button on any screen
• Return to the main menu

💡 **Tips**
• Use `/start` to return to the main menu at any time
• Use `/help` to see this guide again
• Type movie names clearly (e.g., "Interstellar", "The Dark Knight")
"""


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Display help information
    """
    try:
        await update.message.reply_text(
            text=HELP_TEXT,
            parse_mode='Markdown'
        )
    except TelegramError as e:
        logger.error(f"Error sending help message: {e}")
        # Fallback without markdown
        try:
            await update.message.reply_text(
                text="🎬 Movie Assistant - Help Guide\n\n"
                     "Here's what I can do:\n\n"
                     "🎯 Movie Recommendation - Get personalized movie suggestions\n"
                     "📖 Movie Brief - Spoiler-free movie summaries\n"
                     "⭐ Movie Review - Detailed movie reviews with ratings\n"
                     "❌ Cancel - Return to main menu\n\n"
                     "Use /start to begin or /help to see this guide."
            )
        except Exception:
            pass
