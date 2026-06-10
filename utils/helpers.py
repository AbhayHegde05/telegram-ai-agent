"""
Shared utility functions for the Telegram bot
"""

import re
import time
from collections import defaultdict

MAX_MESSAGE_LENGTH = 4000
MAX_MOVIE_NAME_LENGTH = 100


# --- Rate Limiting ---

class RateLimiter:
    """Simple in-memory per-user rate limiter."""

    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[int, list[float]] = defaultdict(list)

    def is_allowed(self, user_id: int) -> bool:
        """Check if a user is allowed to make a request."""
        now = time.time()
        cutoff = now - self.window_seconds

        # Remove old timestamps
        self._requests[user_id] = [
            t for t in self._requests[user_id] if t > cutoff
        ]

        if len(self._requests[user_id]) >= self.max_requests:
            return False

        self._requests[user_id].append(now)
        return True


# Global rate limiter instance (5 requests per 60 seconds)
rate_limiter = RateLimiter(max_requests=5, window_seconds=60)


# --- Input Sanitization ---

def sanitize_movie_name(name: str) -> str:
    """
    Sanitize movie name input.
    
    - Strips whitespace
    - Removes control characters
    - Truncates to MAX_MOVIE_NAME_LENGTH
    
    Args:
        name: Raw movie name from user input
    
    Returns:
        Sanitized movie name
    """
    if not name:
        return ""

    # Strip whitespace
    name = name.strip()

    # Remove control characters (keep normal text, spaces, hyphens, apostrophes, etc.)
    name = re.sub(r'[\x00-\x1f\x7f]', '', name)

    # Truncate
    if len(name) > MAX_MOVIE_NAME_LENGTH:
        name = name[:MAX_MOVIE_NAME_LENGTH]

    return name


def is_valid_movie_name(name: str) -> bool:
    """
    Validate that a movie name is usable.
    
    Args:
        name: Sanitized movie name
    
    Returns:
        True if valid
    """
    return bool(name) and len(name) >= 1


# --- Message Splitting ---

def split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list:
    """
    Split long text into chunks that fit Telegram's message limit.
    
    Splits intelligently at newlines to preserve formatting.
    
    Args:
        text: The text to split
        max_length: Maximum characters per chunk (default 4000, under Telegram's 4096 limit)
    
    Returns:
        List of text chunks
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        # Try to split at a newline near the limit
        split_pos = text.rfind('\n', 0, max_length)
        if split_pos == -1:
            # No newline found, split at max_length
            split_pos = max_length

        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip('\n')

    return chunks
