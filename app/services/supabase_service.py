"""Supabase REST client using SUPABASE_URL and SUPABASE_ANON_KEY only."""

import logging
from typing import Any, Dict

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _headers() -> Dict[str, str]:
    """Headers for Supabase REST (anon key only)."""
    return {
        "apikey": settings.supabase_anon_key,
        "Authorization": f"Bearer {settings.supabase_anon_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


async def ai_customer_reply_row_exists(conversation_id: str, thread_id: str) -> bool:
    """
    Return True if ai_customer_reply already has a row with this conversation_id and thread_id.
    Call this before running the analysis to skip the API when we already have the result saved.
    """
    if not settings.supabase_url or not settings.supabase_anon_key:
        return False
    base = settings.supabase_url.rstrip("/")
    # PostgREST: filter by conversation_id and thread_id, select only id, limit 1
    url = f"{base}/rest/v1/ai_customer_reply"
    params = {"conversation_id": f"eq.{conversation_id}", "thread_id": f"eq.{thread_id}", "select": "id", "limit": "1"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=_headers(), params=params)
            resp.raise_for_status()
            data = resp.json()
        return isinstance(data, list) and len(data) > 0
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        logger.warning("Supabase ai_customer_reply check failed: %s", e)
        return False


async def insert_ai_customer_reply_row(data: Dict[str, Any]) -> None:
    """
    Insert into ai_customer_reply only if no row exists with the same conversation_id and thread_id.
    Uses only SUPABASE_URL and SUPABASE_ANON_KEY.
    """
    if not settings.supabase_url or not settings.supabase_anon_key:
        logger.debug("Supabase URL or anon key not set; skipping ai_customer_reply insert")
        return

    conversation_id = data.get("conversation_id")
    thread_id = data.get("thread_id")
    if conversation_id is None or thread_id is None:
        logger.warning("conversation_id or thread_id missing; skipping ai_customer_reply insert")
        return

    if await ai_customer_reply_row_exists(conversation_id, str(thread_id)):
        logger.debug(
            "ai_customer_reply row already exists for conversation_id=%s thread_id=%s; skipping insert",
            conversation_id,
            thread_id,
        )
        return

    base = settings.supabase_url.rstrip("/")
    url = f"{base}/rest/v1/ai_customer_reply"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=_headers(), json=data)
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.warning("Supabase ai_customer_reply insert failed: %s - %s", e.response.status_code, e.response.text)
    except httpx.RequestError as e:
        logger.warning("Supabase ai_customer_reply request error: %s", e)
