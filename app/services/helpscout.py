"""Help Scout API service."""

import httpx
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.config import settings

logger = logging.getLogger(__name__)

# Token storage file (project root)
TOKEN_STORAGE_PATH = Path(__file__).resolve().parent.parent / ".helpscout_token.json"


class HelpScoutService:
    """Service for interacting with Help Scout API."""

    def __init__(self):
        """Initialize Help Scout service with OAuth2 credentials."""
        self.app_id = settings.helpscout_app_id
        self.app_secret = settings.helpscout_app_secret
        self.base_url = settings.helpscout_api_url
        self.oauth_url = "https://api.helpscout.net/v2/oauth2/token"
        
        # In-memory cache (used after loading from storage)
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    def _load_token_from_storage(self) -> bool:
        """
        Load token and expiry from local storage file.
        
        Returns:
            True if a valid (non-expired) token was loaded, False otherwise.
        """
        # On platforms with read-only filesystems (e.g. Vercel serverless),
        # we can disable file-based persistence via HELPSCOUT_TOKEN_PERSISTENCE=memory.
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
            # Consider expired 60 seconds before actual expiry for safety
            if time.time() >= expires_at:
                logger.info("Stored Help Scout token has expired")
                return False
            self._access_token = token
            self._token_expires_at = expires_at
            logger.info("Using Help Scout token from local storage")
            return True
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not load token from storage: {e}")
            return False

    def _save_token_to_storage(self, access_token: str, expires_at: float) -> None:
        """
        Save token and expiry to local storage file.
        """
        if settings.helpscout_token_persistence == "memory":
            # In-memory only: skip file writes (avoids read-only FS issues on Vercel)
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
            logger.warning(f"Could not save token to storage: {e}")

    async def _get_access_token(self) -> str:
        """
        Get OAuth2 access token using client credentials flow.
        
        Uses token from local storage if present and not expired.
        Otherwise requests a new token and saves it to storage.
        
        Returns:
            str: Bearer access token
            
        Raises:
            httpx.HTTPStatusError: If token request fails
        """
        # Check in-memory cache first
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        
        # Try to load from local storage
        if self._load_token_from_storage():
            return self._access_token
        
        # Request new token
        logger.info("Requesting new OAuth2 token from Help Scout")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.oauth_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.app_id,
                        "client_secret": self.app_secret,
                    },
                )
                response.raise_for_status()
                token_data = response.json()
                
                self._access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 172800)  # Default 2 days
                # Set expiration 60 seconds before actual expiration for safety
                self._token_expires_at = time.time() + expires_in - 60
                
                # Save to local storage
                self._save_token_to_storage(self._access_token, self._token_expires_at)
                
                logger.info(f"Successfully obtained OAuth2 token (expires in {expires_in}s)")
                return self._access_token
                
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to get OAuth2 token: {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"OAuth2 token request error: {e}")
            raise

    async def _get_headers(self) -> Dict[str, str]:
        """
        Get headers with valid authorization token.
        
        Returns:
            Dict containing headers with Bearer token
        """
        token = await self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to Help Scout API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments to pass to httpx request

        Returns:
            Dict containing the response data

        Raises:
            httpx.HTTPStatusError: If the API request fails
            httpx.RequestError: If there's a network error
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = await self._get_headers()
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    **kwargs,
                )
                response.raise_for_status()
                if not response.content:
                    return {}
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Help Scout API error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"Help Scout API request error: {e}")
            raise

    async def get_conversation(self, conversation_id: str, embed_threads: bool = True) -> Dict[str, Any]:
        """
        Fetch conversation details from Help Scout.

        Args:
            conversation_id: The Help Scout conversation ID
            embed_threads: Whether to embed threads in the response (default: True)

        Returns:
            Dict containing conversation data with embedded threads if requested

        Raises:
            httpx.HTTPStatusError: If the API request fails
        """
        logger.info(f"Fetching conversation {conversation_id} with embedded threads")
        endpoint = f"conversations/{conversation_id}"
        
        params = {}
        if embed_threads:
            params["embed"] = "threads"
        
        return await self._make_request("GET", endpoint, params=params)

    async def get_thread(
        self, conversation_id: str, thread_id: str
    ) -> Dict[str, Any]:
        """
        Fetch thread details from Help Scout.

        Args:
            conversation_id: The Help Scout conversation ID
            thread_id: The Help Scout thread ID

        Returns:
            Dict containing thread data

        Raises:
            httpx.HTTPStatusError: If the API request fails
        """
        logger.info(f"Fetching thread {thread_id} from conversation {conversation_id}")
        endpoint = f"conversations/{conversation_id}/threads/{thread_id}"
        return await self._make_request("GET", endpoint)

    async def get_conversation_threads(
        self, conversation_id: str
    ) -> Dict[str, Any]:
        """
        Fetch all threads for a conversation.

        Args:
            conversation_id: The Help Scout conversation ID

        Returns:
            Dict containing threads data

        Raises:
            httpx.HTTPStatusError: If the API request fails
        """
        logger.info(f"Fetching threads for conversation {conversation_id}")
        endpoint = f"conversations/{conversation_id}/threads"
        return await self._make_request("GET", endpoint)

    async def create_note(self, conversation_id: str, text: str) -> None:
        """
        Create a note on a Help Scout conversation.

        Args:
            conversation_id: The Help Scout conversation ID
            text: The note body text

        Raises:
            httpx.HTTPStatusError: If the API request fails
        """
        logger.info(f"Creating note on conversation {conversation_id}")
        endpoint = f"conversations/{conversation_id}/notes"
        # Help Scout expects JSON body with "text" field
        await self._make_request("POST", endpoint, json={"text": text})

    async def update_conversation_tags(self, conversation_id: str, tags: List[str]) -> None:
        """
        Set the tags on a conversation (full replacement).
        PUT /v2/conversations/{id}/tags — existing tags not in the list are removed.

        Args:
            conversation_id: The Help Scout conversation ID
            tags: Full list of tag names to set (e.g. ["vip", "high priority"])

        Raises:
            httpx.HTTPStatusError: If the API request fails
        """
        logger.info("Updating tags on conversation %s to %s", conversation_id, tags)
        endpoint = f"conversations/{conversation_id}/tags"
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = await self._get_headers()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.put(url, headers=headers, json={"tags": tags})
            response.raise_for_status()


# Global service instance
helpscout_service = HelpScoutService()

