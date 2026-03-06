"""Help Scout OAuth2 token: storage, load, save, and refresh (file or memory)."""

import json
import logging
import time
from pathlib import Path
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Token storage file (project root: app/services/tokens -> parent.parent.parent)
TOKEN_STORAGE_PATH = Path(__file__).resolve().parent.parent.parent / ".helpscout_token.json"

HELPSCOUT_OAUTH_URL = "https://api.helpscout.net/v2/oauth2/token"


class HelpscoutTokenManager:
    """
    Manages Help Scout OAuth2 access token: in-memory cache, optional file persistence.
    Use HELPSCOUT_TOKEN_PERSISTENCE=memory on read-only filesystems (e.g. Vercel).
    """

    def __init__(self) -> None:
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    def _load_from_storage(self) -> bool:
        """
        Load token and expiry from local storage file.

        Returns:
            True if a valid (non-expired) token was loaded, False otherwise.
        """
        if settings.helpscout_token_persistence == "memory":
            return False
        if not TOKEN_STORAGE_PATH.exists():
            return False
        try:
            with open(TOKEN_STORAGE_PATH, "r") as f:
                data = json.load(f)
            token = data.get("access_token")
            expires_at = data.get("expires_at", 0)
            if not token or not expires_at:
                return False
            if time.time() >= expires_at:
                logger.info("Stored Help Scout token has expired")
                return False
            self._access_token = token
            self._token_expires_at = expires_at
            logger.info("Using Help Scout token from local storage")
            return True
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not load Help Scout token from storage: %s", e)
            return False

    def _save_to_storage(self, access_token: str, expires_at: float) -> None:
        """Save token and expiry to local storage file (no-op when persistence=memory)."""
        if settings.helpscout_token_persistence == "memory":
            logger.debug("HELPSCOUT_TOKEN_PERSISTENCE=memory; skipping token file save")
            return
        try:
            with open(TOKEN_STORAGE_PATH, "w") as f:
                json.dump(
                    {"access_token": access_token, "expires_at": expires_at},
                    f,
                    indent=0,
                )
            logger.info("Saved Help Scout token to local storage")
        except OSError as e:
            logger.warning("Could not save Help Scout token to storage: %s", e)

    async def get_access_token(self, app_id: str, app_secret: str) -> str:
        """
        Return a valid Bearer token: from cache, from storage, or by requesting a new one.

        Returns:
            Bearer access token.

        Raises:
            httpx.HTTPStatusError: If token request fails.
            httpx.RequestError: On network error.
        """
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        if self._load_from_storage():
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
        expires_in = token_data.get("expires_in", 172800)
        self._token_expires_at = time.time() + expires_in - 60
        self._save_to_storage(self._access_token, self._token_expires_at)

        logger.info("Successfully obtained Help Scout OAuth2 token (expires in %ss)", expires_in)
        return self._access_token


helpscout_token_manager = HelpscoutTokenManager()
