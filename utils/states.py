"""
State management for the Telegram bot
Defines all conversation states and state-related utilities
"""

from enum import Enum


class UserState(Enum):
    """User states throughout the conversation"""
    START = "start"
    RECOMMENDATION_START = "rec_start"
    RECOMMENDATION_LANGUAGE = "rec_language"
    RECOMMENDATION_GENRE = "rec_genre"
    RECOMMENDATION_DURATION = "rec_duration"
    RECOMMENDATION_RELEASE = "rec_release"
    RECOMMENDATION_MOOD = "rec_mood"
    RECOMMENDATION_PROCESSING = "rec_processing"
    BRIEF_START = "brief_start"
    BRIEF_MOVIE_NAME = "brief_movie_name"
    BRIEF_PROCESSING = "brief_processing"
    REVIEW_START = "review_start"
    REVIEW_MOVIE_NAME = "review_movie_name"
    REVIEW_PROCESSING = "review_processing"


class RecommendationPreferences:
    """Holds user preferences for movie recommendation"""

    def __init__(self):
        self.language = None
        self.genre = None
        self.duration = None
        self.release = None
        self.mood = None

    def is_complete(self):
        """Check if all preferences are collected"""
        return all([
            self.language is not None,
            self.genre is not None,
            self.duration is not None,
            self.release is not None,
            self.mood is not None
        ])

    def to_dict(self):
        """Convert preferences to dictionary"""
        return {
            'language': self.language,
            'genre': self.genre,
            'duration': self.duration,
            'release': self.release,
            'mood': self.mood
        }

    def __str__(self):
        """String representation for logging"""
        return f"Language: {self.language}, Genre: {self.genre}, Duration: {self.duration}, Release: {self.release}, Mood: {self.mood}"


def init_user_data(context):
    """Initialize user data if not already done"""
    if 'preferences' not in context.user_data:
        context.user_data['preferences'] = RecommendationPreferences()
        context.user_data['current_feature'] = None
        context.user_data['current_state'] = UserState.START


def get_preferences(context) -> RecommendationPreferences:
    """Get or create user preferences"""
    if 'preferences' not in context.user_data:
        context.user_data['preferences'] = RecommendationPreferences()
    return context.user_data['preferences']


def set_current_feature(context, feature: str) -> None:
    """Set current feature being used"""
    context.user_data['current_feature'] = feature


def clear_feature_state(context) -> None:
    """Clear feature-specific state"""
    context.user_data['preferences'] = RecommendationPreferences()
    context.user_data['current_feature'] = None
