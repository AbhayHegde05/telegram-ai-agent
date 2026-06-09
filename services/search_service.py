"""
Web search service for gathering movie information
Uses DuckDuckGo search with async httpx
"""

import httpx
import logging
import re
import time
from typing import List, Dict

logger = logging.getLogger(__name__)

# Cache settings
CACHE_TTL = 300  # 5 minutes
MAX_CACHE_SIZE = 100

# Simple in-memory cache: {query: (timestamp, result)}
_search_cache: Dict[str, tuple] = {}


class SearchService:
    """Service for web search and movie information gathering"""

    def __init__(self):
        self.timeout = httpx.Timeout(15.0)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    def _get_cache(self, query: str) -> str | None:
        """Check if a cached result exists for the query."""
        if query in _search_cache:
            timestamp, result = _search_cache[query]
            if time.time() - timestamp < CACHE_TTL:
                logger.info(f"Cache hit for query: {query}")
                return result
            else:
                del _search_cache[query]
        return None

    def _set_cache(self, query: str, result: str) -> None:
        """Cache a search result."""
        # Evict oldest entries if cache is full
        if len(_search_cache) >= MAX_CACHE_SIZE:
            oldest_key = min(_search_cache, key=lambda k: _search_cache[k][0])
            del _search_cache[oldest_key]
        _search_cache[query] = (time.time(), result)

    async def search_movies(self, query: str, num_results: int = 10) -> str:
        """
        Search for movies using DuckDuckGo API

        Args:
            query: Search query for movies
            num_results: Number of results to retrieve

        Returns:
            Formatted search results string
        """
        # Check cache first
        cached = self._get_cache(query)
        if cached is not None:
            return cached

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                url = "https://html.duckduckgo.com/"
                params = {
                    'q': query,
                    'kl': 'us-en'
                }

                response = await client.get(url, params=params, headers=self.headers)
                response.raise_for_status()

                results = self._parse_duckduckgo_results(response.text, num_results)

                if results:
                    formatted = self._format_results(results, query)
                    self._set_cache(query, formatted)
                    return formatted
                else:
                    fallback = await self._fallback_search(query, client)
                    self._set_cache(query, fallback)
                    return fallback

        except httpx.TimeoutException:
            logger.warning(f"Search timeout for query: {query}")
            return await self._fallback_search(query)
        except httpx.HTTPStatusError as e:
            logger.error(f"Search HTTP error: {e}")
            return await self._fallback_search(query)
        except Exception as e:
            logger.error(f"Search error: {e}")
            return await self._fallback_search(query)

    def _parse_duckduckgo_results(self, html_content: str, num_results: int) -> List[Dict]:
        """
        Parse DuckDuckGo HTML results
        """
        try:
            results = []

            # Extract result divs - more robust pattern
            result_pattern = r'<div class="result[^"]*">.*?<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>.*?<a class="result__snippet"[^>]*>([^<]*)</a>'
            matches = re.findall(result_pattern, html_content, re.DOTALL)

            for url, title, snippet in matches[:num_results]:
                results.append({
                    'title': title.strip(),
                    'snippet': snippet.strip(),
                    'url': url
                })

            return results
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return []

    async def _fallback_search(self, query: str, client: httpx.AsyncClient = None) -> str:
        """
        Fallback search using alternative method
        """
        try:
            if client is None:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                    return await self._do_fallback_search(query, client)
            else:
                return await self._do_fallback_search(query, client)
        except Exception as e:
            logger.error(f"Fallback search error: {e}")
            return f"Unable to retrieve search results for: {query}\n\nPlease provide a valid movie name."

    async def _do_fallback_search(self, query: str, client: httpx.AsyncClient) -> str:
        """Internal fallback search implementation"""
        try:
            url = "https://www.google.com/search"
            params = {'q': query}

            response = await client.get(url, params=params, headers=self.headers)
            response.raise_for_status()

            snippets = re.findall(r'<span[^>]*>([^<]{20,200})</span>', response.text)

            if snippets:
                results = []
                for snippet in snippets[:5]:
                    if len(snippet) > 20:
                        results.append({
                            'title': query,
                            'snippet': snippet.strip()
                        })
                if results:
                    return self._format_results(results, query)

            return f"Search results for: {query}\n\nNo detailed results available. Please provide the movie name for more specific information."

        except Exception as e:
            logger.error(f"Fallback search error: {e}")
            return f"Unable to retrieve search results for: {query}\n\nPlease provide a valid movie name."

    def _format_results(self, results: List[Dict], query: str) -> str:
        """
        Format search results into a readable string
        """
        if not results:
            return f"No results found for: {query}"

        formatted = f"Search results for: {query}\n\n"
        for i, result in enumerate(results[:5], 1):
            formatted += f"{i}. {result.get('title', 'Unknown')}\n"
            if 'snippet' in result:
                snippet = result['snippet'][:200]
                formatted += f"   {snippet}...\n\n"

        return formatted

    async def search_movie_info(self, movie_name: str) -> str:
        """
        Search for detailed movie information

        Args:
            movie_name: Name of the movie to search

        Returns:
            Movie information as formatted string
        """
        query = f"{movie_name} movie plot cast release year genre"
        return await self.search_movies(query, num_results=5)

    async def search_movie_reviews(self, movie_name: str) -> str:
        """
        Search for movie reviews and ratings

        Args:
            movie_name: Name of the movie

        Returns:
            Review information as formatted string
        """
        query = f"{movie_name} movie reviews ratings IMDb critics"
        return await self.search_movies(query, num_results=5)

    async def search_with_context(self, query: str, context: str = "") -> str:
        """
        Search with additional context

        Args:
            query: Main search query
            context: Additional context to improve search

        Returns:
            Search results string
        """
        full_query = f"{query} {context}".strip()
        return await self.search_movies(full_query, num_results=10)
