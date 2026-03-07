"""Help Scout OAuth2 token: in-memory cache + Supabase (secrets table) persistence."""

import logging
import time
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

HELPSCOUT_OAUTH_URL = "https://api.helpscout.net/v2/oauth2/token"

# Keys used in the Supabase secrets table
_KEY_TOKEN = "helpscout_access_token"
_KEY_EXPIRY = "helpscout_token_expiry"

# Tokens are stored for 40 hours
TOKEN_TTL_SECONDS = 40 * 3600  # 144 000 s


def _supabase_headers() -> dict:
    return {
        "apikey": settings.supabase_anon_key,
        "Authorization": f"Bearer {settings.supabase_anon_key}",
        "Content-Type": "application/json",
    }


def _supabase_available() -> bool:
    return bool(settings.supabase_url and settings.supabase_anon_key)


class HelpscoutTokenManager:
    """
    Manages Help Scout OAuth2 access token.

    Priority:
    1. In-memory cache (no I/O cost).
    2. Supabase secrets table (persists across cold starts / serverless instances).
    3. Request a new token from Help Scout → store in Supabase for 40 hours.

    Works on read-only filesystems (Vercel, etc.) because no local files are used.
    Falls back to memory-only when SUPABASE_URL / SUPABASE_ANON_KEY are not set.
    """

    def __init__(self) -> None:
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    # ------------------------------------------------------------------
    # Supabase helpers
    # ------------------------------------------------------------------

    async def _load_from_supabase(self) -> bool:
        """
        Read helpscout_access_token and helpscout_token_expiry from secrets table.
        Returns True and populates the in-memory cache if a non-expired token is found.
        """
        if not _supabase_available():
            return False

        base = settings.supabase_url.rstrip("/")
        url = f"{base}/rest/v1/secrets"
        params = {
            "key_name": f"in.({_KEY_TOKEN},{_KEY_EXPIRY})",
            "select": "key_name,key_value_encrypted",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=_supabase_headers(), params=params)
                resp.raise_for_status()
                rows = resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.warning("Could not read Help Scout token from Supabase: %s", e)
            return False

        if not isinstance(rows, list) or len(rows) < 2:
            logger.debug("Help Scout token not yet stored in Supabase")
            return False

        by_key = {r["key_name"]: r["key_value_encrypted"] for r in rows if "key_name" in r}
        token = by_key.get(_KEY_TOKEN)
        expiry_raw = by_key.get(_KEY_EXPIRY)

        if not token or expiry_raw is None:
            return False

        try:
            expires_at = float(expiry_raw)
        except (TypeError, ValueError):
            return False

        if time.time() >= expires_at:
            logger.info("Help Scout token from Supabase has expired — will refresh")
            return False

        self._access_token = token
        self._token_expires_at = expires_at
        logger.info("Using Help Scout token from Supabase (expires in %.0fs)", expires_at - time.time())
        return True

    async def _save_to_supabase(self, access_token: str, expires_at: float) -> None:
        """
        Upsert helpscout_access_token and helpscout_token_expiry in the secrets table.
        The on_conflict=key_name param ensures a merge instead of a duplicate insert.
        """
        if not _supabase_available():
            logger.debug("Supabase not configured; Help Scout token not persisted")
            return

        base = settings.supabase_url.rstrip("/")
        url = f"{base}/rest/v1/secrets?on_conflict=key_name"
        headers = {**_supabase_headers(), "Prefer": "resolution=merge-duplicates"}

        payloads = [
            {"key_name": _KEY_TOKEN, "key_value_encrypted": access_token},
            {"key_name": _KEY_EXPIRY, "key_value_encrypted": str(expires_at)},
        ]
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for payload in payloads:
                    resp = await client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
            logger.info("Saved Help Scout token to Supabase (TTL 40 h)")
        except httpx.HTTPStatusError as e:
            logger.warning(
                "Supabase secrets upsert failed: %s — %s",
                e.response.status_code,
                e.response.text,
            )
        except httpx.RequestError as e:
            logger.warning("Supabase secrets request error: %s", e)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_access_token(self, app_id: str, app_secret: str) -> str:
        """
        Return a valid Help Scout Bearer token.

        1. Serve from in-memory cache if not expired.
        2. Load from Supabase if available and not expired → warm the cache.
        3. Request a new token from Help Scout → persist to Supabase for 40 hours.
        """
        if self._access_token and time.time() < self._token_expires_at:
            logger.info("Using cached Help Scout token (expires in %.0fs)", self._token_expires_at - time.time())
            return self._access_token

        if await self._load_from_supabase():
            logger.info("Using Help Scout token from Supabase (expires in %.0fs)", self._token_expires_at - time.time())
            return self._access_token  # type: ignore[return-value]

        logger.info("Requesting new OAuth2 token from Help Scout")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                HELPSCOUT_OAUTH_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": app_id,
                    "client_secret": app_secret,
                },
            )
            response.raise_for_status()
            token_data = response.json()

        self._access_token = token_data["access_token"]
        # Always store for exactly 40 hours regardless of what Help Scout says
        self._token_expires_at = time.time() + TOKEN_TTL_SECONDS

        await self._save_to_supabase(self._access_token, self._token_expires_at)

        logger.info(
            "Obtained new Help Scout OAuth2 token (stored for %d hours)",
            TOKEN_TTL_SECONDS // 3600,
        )
        return self._access_token


helpscout_token_manager = HelpscoutTokenManager()
