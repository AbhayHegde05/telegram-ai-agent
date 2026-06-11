"""
Groq API service for LLM responses
"""

import os
import logging
import asyncio
from groq import AsyncGroq

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_BASE_URL = os.getenv('GROQ_BASE_URL', '')

def _normalize_groq_base_url(url: str) -> str:
    """
    Prevent double-prefix issues by ensuring GROQ_BASE_URL does NOT include
    '/openai' or '/openai/v1' path segments.

    Examples:
      - https://api.groq.com -> OK
      - https://api.groq.com/openai/v1 -> normalized to https://api.groq.com
      - https://api.groq.com/openai -> normalized to https://api.groq.com
    """
    if not url:
        return ""

    url = url.strip().rstrip("/")
    # Strip known suffixes that the groq client will append to internally
    for suffix in ("/openai/v1", "/openai"):
        if url.lower().endswith(suffix):
            url = url[: -len(suffix)]
            url = url.rstrip("/")
    return url
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')

# Module-level singleton instance
_groq_service_instance = None


class GroqService:
    """Service for interacting with Groq API"""

    def __init__(self):
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        try:
            # Only pass base_url if explicitly set (library defaults work fine)
            kwargs = {'api_key': GROQ_API_KEY}
            normalized_base_url = _normalize_groq_base_url(GROQ_BASE_URL) if GROQ_BASE_URL else ""
            if normalized_base_url:
                kwargs['base_url'] = normalized_base_url

            self.client = AsyncGroq(**kwargs)
            self.model = GROQ_MODEL
            self.last_error = None
            logger.info(
                f"✅ Groq client initialized (Model: {self.model}, URL: {getattr(self.client, 'base_url', 'n/a')}, normalized_base_url={normalized_base_url or 'default'})"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")
            raise

    async def _safe_api_call(self, messages: list, max_tokens: int = 1000) -> str:
        """
        Make a safe API call to Groq with retry logic

        Args:
            messages: List of message dictionaries
            max_tokens: Maximum tokens in response

        Returns:
            Response text or None on failure
        """
        max_retries = 3
        base_delay = 1

        for attempt in range(max_retries):
            try:
                self.last_error = None
                logger.info(f"Groq API call attempt {attempt + 1}/{max_retries} (model={self.model})")
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.7
                )
                logger.info(f"Groq API call successful")
                return response.choices[0].message.content
            except Exception as e:
                error_msg = f"{type(e).__name__}: {e}"
                self.last_error = error_msg
                logger.error(f"Groq API error (attempt {attempt + 1}/{max_retries}): {error_msg}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {max_retries} Groq API attempts failed. Last error: {error_msg}")
                    return None

    async def get_movie_recommendations(self, preferences: dict, search_results: str) -> str:
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

        response = await self._safe_api_call(
            [{"role": "user", "content": prompt}],
            max_tokens=2000
        )

        if response is None:
            return "Sorry, I couldn't generate recommendations at this time. Please try again."

        return response

    async def get_movie_brief(self, movie_name: str, search_results: str) -> str:
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

Use reliable general movie knowledge when the search results are unavailable or
incomplete. Do not invent facts. If multiple movies have the same title and the
year or language cannot be determined, respond exactly with:
"AMBIGUOUS_TITLE: Please include the release year or language."

Format it clearly and professionally."""

        response = await self._safe_api_call(
            [{"role": "user", "content": prompt}],
            max_tokens=1500
        )

        if response is None:
            return "Sorry, I couldn't generate a brief at this time. Please try again."

        return response

    async def get_movie_review(self, movie_name: str, search_results: str) -> str:
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

Use reliable general movie knowledge when search results are unavailable or
incomplete. Do not invent ratings or reception. If multiple movies have the
same title and the year or language cannot be determined, respond exactly with:
"AMBIGUOUS_TITLE: Please include the release year or language."

Format with clear separators (━━━━━━━━━━━━━━) between sections. Use the exact emojis provided."""

        response = await self._safe_api_call(
            [{"role": "user", "content": prompt}],
            max_tokens=3000
        )

        if response is None:
            return "Sorry, I couldn't generate a review at this time. Please try again."

        return response

    async def generate_search_query(self, preferences: dict) -> str:
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

        response = await self._safe_api_call(
            [{"role": "user", "content": prompt}],
            max_tokens=100
        )

        if response is None:
            # Fallback to basic query if API fails
            genre = preferences.get('genre', 'movies')
            return f"{genre} movies {preferences.get('language', '').lower()}".strip()

        return response.strip()


def get_groq_service() -> GroqService:
    """Get or create the singleton GroqService instance"""
    global _groq_service_instance
    if _groq_service_instance is None:
        _groq_service_instance = GroqService()
    return _groq_service_instance
