"""Pydantic schemas for draft_writer (RAG reply generation)."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DraftWriterRequest(BaseModel):
    """Input: user query for RAG-based draft reply."""

    user_query: str = Field(..., min_length=1, description="User support question")
    use_cache: bool = Field(
        True,
        description="If false, bypass in-memory classification and draft caches",
    )


class DraftWriterResponse(BaseModel):
    """Output: generated draft reply with metadata."""

    draft: str = Field(..., description="Generated support reply text")
    tier: int = Field(..., ge=0, le=4, description="Detected query tier (0=error/fallback)")
    model: str = Field(..., description="Model used for generation")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Query classifier confidence (0.0–1.0)",
    )
    chunks_used: int = Field(..., ge=0, description="Number of Pinecone chunks used")
    classification: Dict[str, Any] = Field(
        default_factory=dict,
        description="Full classification metadata from query_classifier",
    )
