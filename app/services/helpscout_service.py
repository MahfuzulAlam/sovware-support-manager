"""Help Scout API service."""

import httpx
import logging
from typing import Dict, Any, List, Optional

from app.config import settings
from app.services.tokens.helpscout_token import helpscout_token_manager

logger = logging.getLogger(__name__)


class HelpScoutService:
    """Service for interacting with Help Scout API."""

    def __init__(self):
        """Initialize Help Scout service with OAuth2 credentials."""
        self.app_id = settings.helpscout_app_id
        self.app_secret = settings.helpscout_app_secret
        self.base_url = settings.helpscout_api_url

    async def _get_headers(self) -> Dict[str, str]:
        """
        Get headers with valid authorization token.
        
        Returns:
            Dict containing headers with Bearer token
        """
        token = await helpscout_token_manager.get_access_token(
            self.app_id, self.app_secret
        )
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

