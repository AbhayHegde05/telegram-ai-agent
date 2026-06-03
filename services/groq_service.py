"""
Groq API service for LLM responses
"""

import os
import logging
from groq import Groq

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_BASE_URL = os.getenv('GROQ_BASE_URL', 'https://api.groq.com')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')


class GroqService:
    """Service for interacting with Groq API"""

    def __init__(self):
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        try:
            # Initialize Groq client with minimal parameters
            self.client = Groq(
                api_key=GROQ_API_KEY,
                base_url=GROQ_BASE_URL
            )
            self.model = GROQ_MODEL
            logger.info(f"✅ Groq client initialized successfully (Model: {self.model})")
        except TypeError as e:
            # If base_url causes issues, try without it
            logger.warning(f"Retrying Groq initialization without base_url: {e}")
            try:
                self.client = Groq(api_key=GROQ_API_KEY)
                self.model = GROQ_MODEL
                logger.info(f"✅ Groq client initialized successfully (Model: {self.model})")
            except Exception as retry_error:
                logger.error(f"Failed to initialize Groq client: {retry_error}")
                raise
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")
            raise

    def _safe_api_call(self, messages: list, max_tokens: int = 1000) -> str:
        """
        Make a safe API call to Groq with error handling
        
        Args:
            messages: List of message dictionaries
            max_tokens: Maximum tokens in response
        
        Returns:
            Response text or error message
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            return None

    def get_movie_recommendations(self, preferences: dict, search_results: str) -> str:
        """
        Generate movie recommendations based on user preferences and search results
        
        Args:
            preferences: Dictionary with language, genre, duration, release, mood
            search_results: String containing movie search results
        
        Returns:
            Formatted recommendations string
        """
        prompt = f"""Based on the following user preferences and search results, provide exactly 5 movie recommendations.

User Preferences:
- Language: {preferences.get('language', 'Any')}
- Genre: {preferences.get('genre', 'Any')}
- Duration: {preferences.get('duration', 'Any')}
- Release Preference: {preferences.get('release', 'Any')}
- Mood: {preferences.get('mood', 'Any')}

Search Results:
{search_results}

For each movie, provide:
- 🎬 Movie Name
- ⭐ Rating (out of 10)
- 🎭 Genre
- 🌍 Language
- 📅 Release Year
- ⏱ Duration (in minutes)
- Why it matches your preferences (2-3 lines)

Format each movie clearly with these emojis and information. Only recommend movies that actually match the user's preferences."""

        response = self._safe_api_call(
            [{"role": "user", "content": prompt}],
            max_tokens=2000
        )
        
        if response is None:
            return "Sorry, I couldn't generate recommendations at this time. Please try again."
        
        return response

    def get_movie_brief(self, movie_name: str, search_results: str) -> str:
        """
        Generate a spoiler-controlled movie brief
        
        Args:
            movie_name: Name of the movie
            search_results: Search results containing movie information
        
        Returns:
            Formatted movie brief
        """
        prompt = f"""Based on the following information about "{movie_name}", create a professional movie brief.

Movie Information:
{search_results}

Please provide:
- 🎬 Movie Title
- 📅 Release Year
- 🎭 Genre
- 📖 Story Summary (200-400 words, no major spoilers, mention central theme, setting, and key characters)

Format it clearly and professionally. If the movie information is insufficient or unreliable, respond with: "Sorry, I couldn't find reliable information for that movie."""

        response = self._safe_api_call(
            [{"role": "user", "content": prompt}],
            max_tokens=1500
        )
        
        if response is None:
            return "Sorry, I couldn't generate a brief at this time. Please try again."
        
        return response

    def get_movie_review(self, movie_name: str, search_results: str) -> str:
        """
        Generate a structured movie review
        
        Args:
            movie_name: Name of the movie
            search_results: Search results with reviews and ratings
        
        Returns:
            Formatted structured review
        """
        prompt = f"""Based on the following information about "{movie_name}", create a comprehensive structured review.

Movie Information and Reviews:
{search_results}

Please provide a detailed review with the following sections. For each section, provide a score (X/10) and brief analysis:

1. 📖 Story & Screenplay
2. 🎭 Acting & Characters
3. 🎥 Direction & Cinematography
4. 🎵 Music & Sound Design
5. 🎯 Audience Engagement
6. 💡 Originality & Creativity
7. 🌍 Cultural Impact / Relevance
8. 👍 Strengths (3 bullet points)
9. 👎 Weaknesses (2 bullet points)
10. ⭐ Overall Verdict (short conclusion)
11. 🎯 Final Rating (derived from all sections)

Format with clear separators (━━━━━━━━━━━━━━) between sections. Use the exact emojis provided."""

        response = self._safe_api_call(
            [{"role": "user", "content": prompt}],
            max_tokens=3000
        )
        
        if response is None:
            return "Sorry, I couldn't generate a review at this time. Please try again."
        
        return response

    def generate_search_query(self, preferences: dict) -> str:
        """
        Generate an optimized search query from preferences
        
        Args:
            preferences: Dictionary with language, genre, duration, release, mood
        
        Returns:
            Search query string
        """
        prompt = f"""Create a concise search query to find movies matching these preferences:
- Language: {preferences.get('language', 'Any')}
- Genre: {preferences.get('genre', 'Any')}
- Duration: {preferences.get('duration', 'Any')}
- Release: {preferences.get('release', 'Any')}
- Mood: {preferences.get('mood', 'Any')}

Respond with ONLY the search query, nothing else."""

        response = self._safe_api_call(
            [{"role": "user", "content": prompt}],
            max_tokens=100
        )
        
        if response is None:
            # Fallback to basic query if API fails
            genre = preferences.get('genre', 'movies')
            return f"{genre} movies {preferences.get('language', '').lower()}".strip()
        
        return response.strip()
