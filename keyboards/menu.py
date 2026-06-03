"""
Telegram inline keyboards for the movie assistant bot
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_start_menu_keyboard():
    """
    Main menu keyboard with three options:
    - Movie Recommendation
    - Movie Brief
    - Movie Review
    """
    keyboard = [
        [InlineKeyboardButton("🎯 Movie Recommendation", callback_data="rec_start")],
        [InlineKeyboardButton("📖 Movie Brief", callback_data="brief_start")],
        [InlineKeyboardButton("⭐ Movie Review", callback_data="review_start")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_language_keyboard():
    """
    Language selection keyboard for recommendations
    """
    keyboard = [
        [InlineKeyboardButton("English", callback_data="rec_lang_english")],
        [InlineKeyboardButton("Hindi", callback_data="rec_lang_hindi")],
        [InlineKeyboardButton("Kannada", callback_data="rec_lang_kannada")],
        [InlineKeyboardButton("Tamil", callback_data="rec_lang_tamil")],
        [InlineKeyboardButton("Telugu", callback_data="rec_lang_telugu")],
        [InlineKeyboardButton("Malayalam", callback_data="rec_lang_malayalam")],
        [InlineKeyboardButton("Any", callback_data="rec_lang_any")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_genre_keyboard():
    """
    Genre selection keyboard for recommendations
    """
    keyboard = [
        [InlineKeyboardButton("Action", callback_data="rec_genre_action")],
        [InlineKeyboardButton("Thriller", callback_data="rec_genre_thriller")],
        [InlineKeyboardButton("Comedy", callback_data="rec_genre_comedy")],
        [InlineKeyboardButton("Drama", callback_data="rec_genre_drama")],
        [InlineKeyboardButton("Sci-Fi", callback_data="rec_genre_scifi")],
        [InlineKeyboardButton("Fantasy", callback_data="rec_genre_fantasy")],
        [InlineKeyboardButton("Romance", callback_data="rec_genre_romance")],
        [InlineKeyboardButton("Horror", callback_data="rec_genre_horror")],
        [InlineKeyboardButton("Adventure", callback_data="rec_genre_adventure")],
        [InlineKeyboardButton("Mystery", callback_data="rec_genre_mystery")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_duration_keyboard():
    """
    Duration selection keyboard for recommendations
    """
    keyboard = [
        [InlineKeyboardButton("Less than 2 hours", callback_data="rec_duration_short")],
        [InlineKeyboardButton("2-3 hours", callback_data="rec_duration_medium")],
        [InlineKeyboardButton("More than 3 hours", callback_data="rec_duration_long")],
        [InlineKeyboardButton("Any", callback_data="rec_duration_any")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_release_preference_keyboard():
    """
    Release preference selection keyboard for recommendations
    """
    keyboard = [
        [InlineKeyboardButton("Latest", callback_data="rec_release_latest")],
        [InlineKeyboardButton("Last 5 Years", callback_data="rec_release_5years")],
        [InlineKeyboardButton("Classic", callback_data="rec_release_classic")],
        [InlineKeyboardButton("Any", callback_data="rec_release_any")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_mood_preference_keyboard():
    """
    Mood preference selection keyboard for recommendations
    """
    keyboard = [
        [InlineKeyboardButton("Mind-Blowing", callback_data="rec_mood_mindblowing")],
        [InlineKeyboardButton("Feel-Good", callback_data="rec_mood_feelgood")],
        [InlineKeyboardButton("Emotional", callback_data="rec_mood_emotional")],
        [InlineKeyboardButton("Inspirational", callback_data="rec_mood_inspirational")],
        [InlineKeyboardButton("Dark", callback_data="rec_mood_dark")],
        [InlineKeyboardButton("Funny", callback_data="rec_mood_funny")],
        [InlineKeyboardButton("Any", callback_data="rec_mood_any")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start_menu(update, context):
    """
    Display the start menu
    """
    message_text = """🎬 Welcome to Movie Assistant

Choose what you would like to do:"""

    await update.message.reply_text(
        message_text,
        reply_markup=get_start_menu_keyboard()
    )
