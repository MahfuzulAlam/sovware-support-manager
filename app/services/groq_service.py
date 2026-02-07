"""Groq API service for AI evaluations."""

import json
import logging
from typing import Dict, Any
from groq import AsyncGroq
from app.config import settings
from app.services.prompts import (
    build_evaluation_prompt,
    validate_and_process_evaluation_response,
    SYSTEM_MESSAGE,
)

logger = logging.getLogger(__name__)


class GroqService:
    """Service for interacting with Groq API."""

    def __init__(self):
        """Initialize Groq service with API credentials."""
        self.client = AsyncGroq(api_key=settings.groq_api_key)
        self.model = settings.groq_model

    async def evaluate_conversation(
        self, conversation_text: str, thread_text: str
    ) -> Dict[str, Any]:
        """
        Evaluate a customer support conversation using Groq.

        Args:
            conversation_text: The full conversation text
            thread_text: The specific agent reply thread text

        Returns:
            Dict containing evaluation_message, improvement, and 10 parameter scores

        Raises:
            Exception: If Groq API call fails or response is invalid
        """
        # Build prompt using shared function
        prompt = build_evaluation_prompt(conversation_text, thread_text)

        try:
            logger.info("Sending evaluation request to Groq")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_MESSAGE,
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            logger.info("Received response from Groq")

            # Parse JSON response
            try:
                evaluation_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Groq JSON response: {e}")
                logger.error(f"Response content: {content}")
                raise ValueError(f"Invalid JSON response from Groq: {e}")

            # Validate and process using shared function
            return validate_and_process_evaluation_response(
                evaluation_data, service_name="Groq"
            )

        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise


# Global service instance
groq_service = GroqService()

