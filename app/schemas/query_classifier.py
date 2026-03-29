"""Pydantic schemas for Directorist query tier classification (query_classifier sub-agent)."""

from typing import List

from pydantic import BaseModel, Field


class QueryClassifierRequest(BaseModel):
    """Input: raw user query for routing (RAG)."""

    user_query: str = Field(..., min_length=1, description="User message as-is")
    use_cache: bool = Field(
        True,
        description="If false, bypass in-memory classification cache for this request",
    )


class QueryClassifierResponse(BaseModel):
    """Structured tier classification for internal routing only (not shown to end users)."""

    tier: int = Field(..., ge=1, le=4, description="Routing tier 1–4")
    type: str = Field(
        ...,
        description="Tier label (e.g. Basic / Lookup, Configuration/How-to)",
    )
    model: str = Field(
        ...,
        description="Answer model slug for this tier (from QUERY_TIER_MODELS in query_classifier.py; not chosen by the LLM)",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classifier confidence 0.0–1.0")
    reason: str = Field(..., description="Short rationale for the classification")
    keywords_matched: List[str] = Field(
        default_factory=list,
        description="1–5 words or phrases from the query that drove the decision",
    )
