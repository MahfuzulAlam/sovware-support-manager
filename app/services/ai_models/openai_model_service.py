"""OpenAI model service for Tier 2/3 queries and embeddings."""

import logging
from typing import List, Optional

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class OpenAIModelService:
    """OpenAI models for Tier 2 (gpt-4o-mini) and Tier 3 (gpt-4.1-mini) + embeddings."""

    def __init__(self) -> None:
        self.client: Optional[AsyncOpenAI] = None
        if settings.openai_api_key:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.4,
        max_tokens: int = 800,
    ) -> str:
        """
        Generate a response from OpenAI.

        Args:
            system_prompt: System instruction
            user_prompt: User query with context
            model: Model slug (gpt-4o-mini, gpt-4.1-mini, etc.)
            temperature: Sampling temperature
            max_tokens: Max tokens in response

        Returns:
            Generated text response

        Raises:
            Exception: On OpenAI API errors
        """
        if not self.client:
            raise ValueError("OPENAI_API_KEY is required for OpenAI generate")
        try:
            logger.info("OpenAI generate request (model=%s, max_tokens=%d)", model, max_tokens)
            response = await self.client.chat.completions.create(
                model=model,
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
            logger.error("OpenAI API error (model=%s): %s", model, e)
            raise

    async def embed(self, text: str, model: str = "text-embedding-3-small") -> List[float]:
        """
        Embed text using OpenAI embeddings API.

        Args:
            text: Text to embed
            model: Embedding model (default text-embedding-3-small)

        Returns:
            Embedding vector as list of floats

        Raises:
            Exception: On OpenAI API errors
        """
        if not self.client:
            raise ValueError("OPENAI_API_KEY is required for embeddings")
        try:
            logger.debug("OpenAI embed request (model=%s)", model)
            response = await self.client.embeddings.create(
                model=model,
                input=text.strip(),
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error("OpenAI embed API error: %s", e)
            raise


openai_model_service = OpenAIModelService()
