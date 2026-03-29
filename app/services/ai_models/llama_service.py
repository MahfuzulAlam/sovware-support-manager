"""Llama model service via Groq for Tier 1 (basic/lookup) queries."""

import logging
from typing import Dict, Any, Optional

from groq import AsyncGroq

from app.config import settings

logger = logging.getLogger(__name__)


class LlamaService:
    """Lightweight Llama model via Groq for fast basic lookups (Tier 1)."""

    def __init__(self) -> None:
        self.client = AsyncGroq(api_key=settings.groq_api_key)
        self.model = "llama-3.1-8b-instant"

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "llama-3.1-8b-instant",
        temperature: float = 0.3,
        max_tokens: int = 500,
    ) -> str:
        """
        Generate a response from Llama via Groq.

        Args:
            system_prompt: System instruction
            user_prompt: User query with context
            temperature: Sampling temperature (default 0.3 for factual)
            max_tokens: Max tokens in response

        Returns:
            Generated text response

        Raises:
            Exception: On Groq API errors
        """
        try:
            logger.info("Llama generate request (model=%s, max_tokens=%d)", self.model, max_tokens)
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content or ""
            return content.strip()
        except Exception as e:
            logger.error("Groq Llama API error: %s", e)
            raise


llama_service = LlamaService()
