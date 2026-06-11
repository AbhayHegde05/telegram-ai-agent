"""Session-oriented persistence using Supabase."""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from supabase import Client, create_client

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
)


def _create_supabase_client() -> Optional[Client]:
    if not (SUPABASE_URL and SUPABASE_KEY):
        return None

    # Vercel serverless + HTTP/2 connections can be reset (StreamReset).
    # Force HTTP/1.1 for the underlying httpx transport.
    httpx_client = httpx.Client(http2=False)

    # supabase-py v2 uses httpx under the hood via this option.
    # If the option is not supported, it will raise; we catch at call sites.
    return create_client(
        SUPABASE_URL,
        SUPABASE_KEY,
        options={"http_client": httpx_client},
    )


# Create client lazily per invocation to avoid reusing defunct connections.
_supabase_singleton: Optional[Client] = None
_supabase_singleton_ready = False


def _get_supabase() -> Optional[Client]:
    global _supabase_singleton, _supabase_singleton_ready
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None

    # In most serverless environments, module-level objects are reused across warm invocations,
    # which can make HTTP/2 resets more likely. We still keep a singleton, but recreate it
    # on-demand if it fails.
    if _supabase_singleton_ready and _supabase_singleton is not None:
        return _supabase_singleton

    try:
        _supabase_singleton = _create_supabase_client()
        _supabase_singleton_ready = True
        return _supabase_singleton
    except Exception:
        logger.exception("❌ Failed to create Supabase client")
        _supabase_singleton = None
        _supabase_singleton_ready = False
        return None


async def _to_thread(fn, *args, **kwargs):
    return await asyncio.to_thread(fn, *args, **kwargs)


def init_db() -> None:
    """Report whether the remote Supabase client is available."""
    if _get_supabase():
        logger.info("Supabase session storage initialized")
    else:
        logger.warning("Supabase session storage is unavailable")


def get_storage_status() -> dict:
    """Check that both session tables are reachable."""
    supa = _get_supabase()
    if not supa:
        return {"ok": False, "error": "Supabase client is not configured"}

    try:
        supa.table("bot_sessions").select("id").limit(1).execute()
        supa.table("session_events").select("id").limit(1).execute()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:500]}


def _active_session_sync(user_id: int) -> Optional[dict]:
    supa = _get_supabase()
    if not supa:
        return None

    response = (
        supa.table("bot_sessions")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "active")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def start_session(
    user_id: int,
    *,
    chat_id: Optional[int] = None,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    force_new: bool = False,
) -> Optional[str]:
    """Open or reuse the user's active session and return its UUID."""
    supa = _get_supabase()
    if not supa:
        return None

    try:
        active = _active_session_sync(user_id)
        if active and force_new:
            log_event(
                user_id,
                "session_end",
                {"reason": "restarted"},
                handler="start",
                session_id=active["id"],
            )
            supa.table("bot_sessions").update(
                {
                    "status": "ended",
                    "last_activity_at": _now(),
                    "ended_at": _now(),
                }
            ).eq("id", active["id"]).execute()
            active = None

        identity = {
            "chat_id": chat_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "last_activity_at": _now(),
        }
        identity = {key: value for key, value in identity.items() if value is not None}

        if active:
            if identity:
                supa.table("bot_sessions").update(identity).eq("id", active["id"]).execute()
            return active["id"]

        data = {"user_id": user_id, **identity}
        response = supa.table("bot_sessions").insert(data).execute()
        if response.data:
            return response.data[0]["id"]

        created = _active_session_sync(user_id)
        return created["id"] if created else None
    except Exception as exc:
        logger.error("Error starting session for %s: %s", user_id, exc)
        return None


def end_session(user_id: int) -> None:
    """Close the user's active session."""
    supa = _get_supabase()
    if not supa:
        return

    try:
        active = _active_session_sync(user_id)
        if active:
            log_event(
                user_id,
                "session_end",
                {"reason": "endchat"},
                handler="endchat",
                session_id=active["id"],
            )
            supa.table("bot_sessions").update(
                {
                    "status": "ended",
                    "current_feature": None,
                    "last_activity_at": _now(),
                    "ended_at": _now(),
                }
            ).eq("id", active["id"]).execute()
    except Exception as exc:
        logger.error("Error ending session for %s: %s", user_id, exc)


def load_user_data(user_id: int) -> dict:
    """Load state from the user's active session."""
    supa = _get_supabase()
    if not supa:
        return {}

    try:
        session = _active_session_sync(user_id)
        if not session:
            return {}
        return {
            "preferences": session.get("preferences") or {},
            "current_feature": session.get("current_feature"),
            "session_id": session.get("id"),
        }
    except Exception as exc:
        logger.error("Error loading session for %s: %s", user_id, exc)
        return {}


def save_user_data(
    user_id: int,
    preferences: dict,
    current_feature: Optional[str] = None,
) -> None:
    """Persist feature state in the user's active session."""
    supa = _get_supabase()
    if not supa:
        return

    try:
        session_id = start_session(user_id)
        if session_id:
            supa.table("bot_sessions").update(
                {
                    "preferences": preferences or {},
                    "current_feature": current_feature,
                    "last_activity_at": _now(),
                }
            ).eq("id", session_id).execute()
    except Exception as exc:
        logger.error("Error saving session state for %s: %s", user_id, exc)


def log_event(
    user_id: int,
    event_type: str,
    payload: Optional[dict] = None,
    *,
    endpoint: Optional[str] = None,
    update_kind: Optional[str] = None,
    handler: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """Append an event to the user's active session."""
    supa = _get_supabase()
    if not supa:
        return

    try:
        session_id = session_id or start_session(user_id)
        if not session_id:
            return

        supa.table("session_events").insert(
            {
                "session_id": session_id,
                "user_id": user_id,
                "event_type": event_type,
                "endpoint": endpoint,
                "update_kind": update_kind,
                "handler": handler,
                "payload": payload or {},
            }
        ).execute()
    except Exception as exc:
        logger.error("Error logging session event for %s: %s", user_id, exc)


def add_history(
    user_id: int,
    feature: str,
    input_data: str = "",
    output_summary: str = "",
) -> None:
    """Compatibility wrapper that stores history as a session event."""
    log_event(
        user_id,
        "feature_history",
        {
            "feature": feature,
            "input": input_data[:500],
            "output_summary": output_summary[:500],
        },
        handler=feature,
    )


def get_recent_history(user_id: int, limit: int = 5) -> list:
    """Return recent feature-history events for the active session."""
    supa = _get_supabase()
    if not supa:
        return []

    try:
        session = _active_session_sync(user_id)
        if not session:
            return []

        response = (
            supa.table("session_events")
            .select("payload, created_at")
            .eq("session_id", session["id"])
            .eq("event_type", "feature_history")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        return [
            {
                "feature": row["payload"].get("feature"),
                "input": row["payload"].get("input"),
                "summary": row["payload"].get("output_summary"),
                "timestamp": row["created_at"],
            }
            for row in response.data
        ]
    except Exception as exc:
        logger.error("Error loading history for %s: %s", user_id, exc)
        return []


def clear_user_data(user_id: int) -> None:
    """Compatibility alias for closing the active session."""
    end_session(user_id)

