"""
Persistent user memory using SQLite.
Stores user preferences and recent interactions so they survive bot restarts.
"""

import sqlite3
import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Database path
DB_PATH = os.getenv('BOT_MEMORY_DB', 'bot_memory.db')


def _get_connection() -> sqlite3.Connection:
    """Get a database connection with WAL mode for better concurrency."""
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_data (
                user_id INTEGER PRIMARY KEY,
                preferences TEXT DEFAULT '{}',
                current_feature TEXT DEFAULT NULL,
                last_interaction REAL DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                feature TEXT NOT NULL,
                input_data TEXT DEFAULT '',
                output_summary TEXT DEFAULT '',
                timestamp REAL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES user_data(user_id)
            )
        """)

        # Keep only last 50 history entries per user (simple approach)
        cursor.execute("""
            DELETE FROM user_history
            WHERE id IN (
                SELECT h.id FROM user_history h
                INNER JOIN (
                    SELECT user_id, COUNT(*) as cnt
                    FROM user_history
                    GROUP BY user_id
                    HAVING cnt > 50
                ) sub ON h.user_id = sub.user_id
                ORDER BY h.timestamp ASC
                LIMIT (SELECT MAX(cnt) - 50 FROM (SELECT COUNT(*) as cnt FROM user_history GROUP BY user_id HAVING cnt > 50))
            )
        """)
        # Fallback: just delete entries older than 7 days
        cursor.execute(
            "DELETE FROM user_history WHERE timestamp < ?",
            (time.time() - 7 * 24 * 3600,)
        )

        conn.commit()
        conn.close()
        logger.info("✅ SQLite memory database initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize memory database: {e}")


def load_user_data(user_id: int) -> dict:
    """Load user data from SQLite."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT preferences, current_feature FROM user_data WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            preferences = json.loads(row[0]) if row[0] else {}
            return {
                'preferences': preferences,
                'current_feature': row[1]
            }
        return {}
    except Exception as e:
        logger.error(f"Error loading user data for {user_id}: {e}")
        return {}


def save_user_data(user_id: int, preferences: dict, current_feature: Optional[str] = None) -> None:
    """Save user data to SQLite."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO user_data (user_id, preferences, current_feature, last_interaction)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                preferences = excluded.preferences,
                current_feature = excluded.current_feature,
                last_interaction = excluded.last_interaction
        """, (user_id, json.dumps(preferences), current_feature, time.time()))

        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error saving user data for {user_id}: {e}")


def add_history(user_id: int, feature: str, input_data: str = "", output_summary: str = "") -> None:
    """Add an entry to user history."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO user_history (user_id, feature, input_data, output_summary, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, feature, input_data, output_summary[:500], time.time()))

        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error adding history for {user_id}: {e}")


def get_recent_history(user_id: int, limit: int = 5) -> list:
    """Get recent interaction history for a user."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT feature, input_data, output_summary, timestamp
            FROM user_history
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                'feature': row[0],
                'input': row[1],
                'summary': row[2],
                'timestamp': row[3]
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Error getting history for {user_id}: {e}")
        return []


def clear_user_data(user_id: int) -> None:
    """Clear all data for a user."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM user_data WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM user_history WHERE user_id = ?", (user_id,))

        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error clearing data for {user_id}: {e}")
