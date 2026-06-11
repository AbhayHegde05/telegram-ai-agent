"""
Web search service for gathering movie information.
Uses Tavily Search API (single provider) to avoid brittle HTML scraping.
"""

import httpx
import logging
import os
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Cache settings
CACHE_TTL = 300  # 5 minutes
MAX_CACHE_SIZE = 100

# Simple in-memory cache: {query: (timestamp, result)}
_search_cache: Dict[str, Tuple[float, str]] = {}


class SearchService:
    """Service for web search and movie information gathering (via Tavily)."""

    def __init__(self):
        self.timeout = httpx.Timeout(25.0)
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")
        self.tavily_endpoint = os.getenv("TAVILY_ENDPOINT", "https://api.tavily.com/search")
        self.last_error: Optional[str] = None

        if not self.tavily_api_key:
            logger.warning("TAVILY_API_KEY is not set. Search will fail until configured.")

    def _get_cache(self, query: str) -> Optional[str]:
        """Check if a cached result exists for the query."""
        if query in _search_cache:
            timestamp, result = _search_cache[query]
            if time.time() - timestamp < CACHE_TTL:
                logger.info(f"Cache hit for query: {query}")
                return result
            del _search_cache[query]
        return None

    def _set_cache(self, query: str, result: str) -> None:
        """Cache a search result."""
        if len(_search_cache) >= MAX_CACHE_SIZE:
            oldest_key = min(_search_cache, key=lambda k: _search_cache[k][0])
            del _search_cache[oldest_key]
        _search_cache[query] = (time.time(), result)

    async def search_movies(
        self,
        query: str,
        num_results: int = 10,
        include_domains: Optional[List[str]] = None,
    ) -> str:
        """
        Search for movies using Tavily.

        Args:
            query: Search query for movies
            num_results: Number of results to retrieve (capped to 10)

        Returns:
            Formatted search results string
        """
        cached = self._get_cache(query)
        if cached is not None:
            return cached

        if not self.tavily_api_key:
            msg = "Search unavailable: TAVILY_API_KEY not configured."
            logger.error(msg)
            self.last_error = msg
            return f"Search results for: {query}\n\n{msg}"

        try:
            self.last_error = None
            payload = {
                "api_key": self.tavily_api_key,
                "query": query,
                "max_results": max(1, min(int(num_results), 10)),
                "search_depth": "basic",
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
            }
            if include_domains:
                payload["include_domains"] = include_domains

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.tavily_endpoint, json=payload)
                resp.raise_for_status()
                data = resp.json()

            results = data.get("results") or []
            formatted = self._format_results(results, query)
            self._set_cache(query, formatted)
            return formatted

        except httpx.TimeoutException:
            self.last_error = f"Tavily search timeout for query: {query}"
            logger.warning(self.last_error)
            return f"Search results for: {query}\n\nSearch timed out. Please try again later."
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            logger.error(f"Tavily search error for query '{query}': {e}")
            return f"Search results for: {query}\n\nUnable to retrieve search results right now. Please try again later."

    def _format_results(self, results: List[dict], query: str) -> str:
        """Format Tavily results into readable text for LLM prompts."""
        if not results:
            return f"Search results for: {query}\n\nNo results available."

        formatted = f"Search results for: {query}\n\n"
        for i, r in enumerate(results[:5], 1):
            title = (r.get("title") or "").strip() or "Unknown"
            url = (r.get("url") or "").strip()
            content = (r.get("content") or "").strip()

            formatted += f"{i}. {title}\n"
            if url:
                formatted += f"   Source: {url}\n"
            if content:
                formatted += f"   {content[:220]}...\n\n"
        return formatted

    async def search_movie_info(self, movie_name: str) -> str:
        """Search for detailed movie information."""
        query = f'"{movie_name}" film plot cast release year genre runtime'
        return await self.search_movies(
            query,
            num_results=7,
            include_domains=[
                "wikipedia.org",
                "imdb.com",
                "rottentomatoes.com",
                "themoviedb.org",
            ],
        )

    async def search_movie_reviews(self, movie_name: str) -> str:
        """Search for movie reviews and ratings."""
        query = f'"{movie_name}" film reviews ratings critics audience'
        return await self.search_movies(
            query,
            num_results=7,
            include_domains=[
                "imdb.com",
                "rottentomatoes.com",
                "metacritic.com",
                "rogerebert.com",
                "wikipedia.org",
            ],
        )

    async def search_with_context(self, query: str, context: str = "") -> str:
        """Search with additional context."""
        full_query = f"{query} {context}".strip()
        return await self.search_movies(full_query, num_results=10)
