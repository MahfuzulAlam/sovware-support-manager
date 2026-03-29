"""AI model router: maps tier to the appropriate model service and provides embedQuery."""

import logging
from typing import Any, List, Protocol

from app.config import settings

logger = logging.getLogger(__name__)


class ModelService(Protocol):
    """Protocol for all AI model services."""

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "",
        temperature: float = 0.4,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a text response."""
        ...


def get_model(tier: int, model_slug: str) -> Any:
    """
    Get the appropriate AI model service for a tier and model slug.

    Args:
        tier: Routing tier (1–4)
        model_slug: Model identifier (e.g. llama-3.1-8b, gpt-4o-mini, claude-sonnet-4-5)

    Returns:
        Model service instance with a generate() method

    Raises:
        ValueError: If required API key is missing for the selected model
        ImportError: If the model service module cannot be loaded
    """
    slug_lower = model_slug.lower()

    if "llama" in slug_lower or "mistral" in slug_lower:
        from app.services.ai_models.llama_service import llama_service
        return llama_service

    if "gpt" in slug_lower or "openai" in slug_lower:
        from app.services.ai_models.openai_model_service import openai_model_service
        return openai_model_service

    if "claude" in slug_lower or "anthropic" in slug_lower:
        from app.services.ai_models.claude_service import claude_service
        return claude_service

    if "gemini" in slug_lower or "google" in slug_lower:
        from app.services.ai_models.gemini_service import gemini_service
        return gemini_service

    logger.warning("Unknown model slug '%s'; defaulting to OpenAI gpt-4o-mini", model_slug)
    from app.services.ai_models.openai_model_service import openai_model_service
    return openai_model_service


async def embed_query(text: str) -> List[float]:
    """
    Embed a query using OpenAI text-embedding-3-small.

    Args:
        text: Text to embed

    Returns:
        Embedding vector as list of floats

    Raises:
        ValueError: If OPENAI_API_KEY is not set
        Exception: On OpenAI API errors
    """
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for embeddings")

    from app.services.ai_models.openai_model_service import openai_model_service
    return await openai_model_service.embed(text)
