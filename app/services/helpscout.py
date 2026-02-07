"""Help Scout API service."""

import httpx
import logging
import time
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)


class HelpScoutService:
    """Service for interacting with Help Scout API."""

    def __init__(self):
        """Initialize Help Scout service with OAuth2 credentials."""
        self.app_id = settings.helpscout_app_id
        self.app_secret = settings.helpscout_app_secret
        self.base_url = settings.helpscout_api_url
        self.oauth_url = "https://api.helpscout.net/v2/oauth2/token"
        
        # Token cache
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    async def _get_access_token(self) -> str:
        """
        Get OAuth2 access token using client credentials flow.
        
        Caches the token and refreshes it when expired.
        
        Returns:
            str: Bearer access token
            
        Raises:
            httpx.HTTPStatusError: If token request fails
        """
        # Check if we have a valid cached token
        if self._access_token and time.time() < self._token_expires_at:
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
        #token = await self._get_access_token()
        token = "c9NeiJxGU7hhCkVsY5VJBn30AMpqNCCZ"
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


# Global service instance
helpscout_service = HelpScoutService()

