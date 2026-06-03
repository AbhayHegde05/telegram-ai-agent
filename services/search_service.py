"""
Web search service for gathering movie information
Uses DuckDuckGo search and web scraping
"""

import requests
import logging
from typing import List, Dict
import json

logger = logging.getLogger(__name__)


class SearchService:
    """Service for web search and movie information gathering"""

    def __init__(self):
        self.timeout = 15
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    def search_movies(self, query: str, num_results: int = 10) -> str:
        """
        Search for movies using DuckDuckGo API
        
        Args:
            query: Search query for movies
            num_results: Number of results to retrieve
        
        Returns:
            Formatted search results string
        """
        try:
            # Using DuckDuckGo HTML search with more robust headers
            url = "https://html.duckduckgo.com/"
            params = {
                'q': query,
                'kl': 'us-en'
            }
            
            response = requests.get(url, params=params, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse results from DuckDuckGo HTML
            results = self._parse_duckduckgo_results(response.text, num_results)
            
            if results:
                return self._format_results(results, query)
            else:
                return self._fallback_search(query)
                
        except Exception as e:
            logger.error(f"Search error: {e}")
            return self._fallback_search(query)

    def _parse_duckduckgo_results(self, html_content: str, num_results: int) -> List[Dict]:
        """
        Parse DuckDuckGo HTML results
        """
        try:
            from html.parser import HTMLParser
            
            results = []
            
            # Simple extraction of result snippets
            import re
            
            # Extract result divs
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

    def _fallback_search(self, query: str) -> str:
        """
        Fallback search using alternative method
        """
        try:
            # Try using Google search via alternative endpoint
            url = "https://www.google.com/search"
            params = {'q': query}
            
            response = requests.get(url, params=params, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            
            # Extract snippets from Google results
            import re
            snippets = re.findall(r'<span[^>]*>([^<]{20,200})</span>', response.text)
            
            if snippets:
                results = []
                for snippet in snippets[:5]:
                    if len(snippet) > 20:
                        results.append({
                            'title': query,
                            'snippet': snippet.strip()
                        })
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

    def search_movie_info(self, movie_name: str) -> str:
        """
        Search for detailed movie information
        
        Args:
            movie_name: Name of the movie to search
        
        Returns:
            Movie information as formatted string
        """
        query = f"{movie_name} movie plot cast release year genre"
        return self.search_movies(query, num_results=5)

    def search_movie_reviews(self, movie_name: str) -> str:
        """
        Search for movie reviews and ratings
        
        Args:
            movie_name: Name of the movie
        
        Returns:
            Review information as formatted string
        """
        query = f"{movie_name} movie reviews ratings IMDb critics"
        return self.search_movies(query, num_results=5)

    def search_with_context(self, query: str, context: str = "") -> str:
        """
        Search with additional context
        
        Args:
            query: Main search query
            context: Additional context to improve search
        
        Returns:
            Search results string
        """
        full_query = f"{query} {context}".strip()
        return self.search_movies(full_query, num_results=10)
