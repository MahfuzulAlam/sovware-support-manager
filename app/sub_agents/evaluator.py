"""Evaluator sub-agent: Groq-backed evaluation service for agent reply scoring."""

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


class GroqEvaluationService:
    """Service for evaluating customer support conversations using Groq."""

    def __init__(self):
        """Initialize with Groq API credentials."""
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
        prompt = build_evaluation_prompt(conversation_text, thread_text)

        try:
            logger.info("Sending evaluation request to Groq")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_MESSAGE},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            logger.info("Received response from Groq")

            try:
                evaluation_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error("Failed to parse Groq JSON response: %s", e)
                logger.error("Response content: %s", content)
                raise ValueError(f"Invalid JSON response from Groq: {e}") from e

            return validate_and_process_evaluation_response(
                evaluation_data, service_name="Groq"
            )

        except Exception as e:
            logger.error("Groq API error: %s", e)
            raise


# Global instance used when ai_api_type is "groq"
groq_evaluation_service = GroqEvaluationService()
