"""
Persistent user memory using Supabase.
Stores user preferences and recent interactions so they survive serverless webhook instances.
"""

import logging
import os
import time
from typing import Optional

from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Initialize Supabase Client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
)

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None
    logger.warning(
        "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY/SUPABASE_ANON_KEY "
        "not set. Memory will not be persisted."
    )

def init_db() -> None:
    """Supabase is managed via remote migrations. Local initialization is skipped."""
    if not supabase:
        logger.warning("Database client not initialized. Ensure Supabase credentials are provided.")
    else:
        logger.info("✅ Supabase client initialized")

def load_user_data(user_id: int) -> dict:
    """Load user data from Supabase."""
    if not supabase:
        return {}

    try:
        response = supabase.table("user_data").select("*").eq("user_id", user_id).execute()
        if response.data and len(response.data) > 0:
            row = response.data[0]
            return {
                'preferences': row.get('preferences', {}),
                'current_feature': row.get('current_feature')
            }
        return {}
    except Exception as e:
        logger.error(f"Error loading user data for {user_id}: {e}")
        return {}

def save_user_data(user_id: int, preferences: dict, current_feature: Optional[str] = None) -> None:
    """Save user data to Supabase."""
    if not supabase:
        return

    try:
        data = {
            "user_id": user_id,
            "preferences": preferences,
            "current_feature": current_feature,
            "last_interaction": time.time()
        }
        supabase.table("user_data").upsert(data).execute()
    except Exception as e:
        logger.error(f"Error saving user data for {user_id}: {e}")

def add_history(user_id: int, feature: str, input_data: str = "", output_summary: str = "") -> None:
    """Add an entry to user history."""
    if not supabase:
        return

    try:
        # First ensure the user_data row exists to satisfy the foreign key constraint
        # Even if they just started, they need a row.
        supabase.table("user_data").upsert({
            "user_id": user_id,
            "last_interaction": time.time()
        }, on_conflict="user_id").execute()

        data = {
            "user_id": user_id,
            "feature": feature,
            "input_data": input_data,
            "output_summary": output_summary[:500] if output_summary else "",
            "timestamp": time.time()
        }
        supabase.table("user_history").insert(data).execute()
    except Exception as e:
        logger.error(f"Error adding history for {user_id}: {e}")

def get_recent_history(user_id: int, limit: int = 5) -> list:
    """Get recent interaction history for a user."""
    if not supabase:
        return []

    try:
        response = supabase.table("user_history")\
            .select("feature, input_data, output_summary, timestamp")\
            .eq("user_id", user_id)\
            .order("timestamp", desc=True)\
            .limit(limit)\
            .execute()
        
        return [
            {
                'feature': row['feature'],
                'input': row['input_data'],
                'summary': row['output_summary'],
                'timestamp': row['timestamp']
            }
            for row in response.data
        ]
    except Exception as e:
        logger.error(f"Error getting history for {user_id}: {e}")
        return []

def log_event(
    user_id: int,
    event_type: str,
    payload: Optional[dict] = None,
    *,
    endpoint: Optional[str] = None,
    update_kind: Optional[str] = None,
    handler: Optional[str] = None
) -> None:
    """
    Append an audit event to public.user_events.

    This is best-effort and never interrupts bot handling. The deployed backend
    should use SUPABASE_SERVICE_ROLE_KEY because user_events only permits
    service-role inserts.
    """
    if not supabase:
        return

    try:
        data = {
            "user_id": user_id,
            "event_type": event_type,
            "endpoint": endpoint,
            "update_kind": update_kind,
            "handler": handler,
            "payload": payload or {},
            "timestamp": time.time()
        }
        supabase.table("user_events").insert(data).execute()
    except Exception as e:
        logger.error(f"Error logging event for {user_id}: {e}")


def clear_user_data(user_id: int) -> None:
    """Clear all data for a user."""
    if not supabase:
        return

    try:
        # Due to ON DELETE CASCADE on user_history, deleting user_data removes history too
        supabase.table("user_data").delete().eq("user_id", user_id).execute()
    except Exception as e:
        logger.error(f"Error clearing data for {user_id}: {e}")
