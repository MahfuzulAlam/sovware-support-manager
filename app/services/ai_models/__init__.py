"""AI model services package."""

from app.services.ai_models.llama_service import llama_service
from app.services.ai_models.openai_model_service import openai_model_service

__all__ = [
    "llama_service",
    "openai_model_service",
    "get_model",
    "embed_query",
]


def get_model(tier: int, model_slug: str):
    """
    Get the appropriate AI model service for a tier and model slug.

    Lazily imports Claude/Gemini only when needed.
    """
    from app.services.ai_models.model_router import get_model as _get_model
    return _get_model(tier, model_slug)


async def embed_query(text: str):
    """Embed a query using OpenAI embeddings."""
    from app.services.ai_models.model_router import embed_query as _embed_query
    return await _embed_query(text)
