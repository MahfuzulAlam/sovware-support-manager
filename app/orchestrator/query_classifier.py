"""HTTP API for Directorist query tier classification (internal routing; optional for integrations)."""

import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.query_classifier import QueryClassifierRequest, QueryClassifierResponse
from app.sub_agents.query_classifier import query_classifier_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["query_classifier"])


@router.post(
    "/classify",
    response_model=QueryClassifierResponse,
    status_code=status.HTTP_200_OK,
    summary="Classify user query into routing tier",
    description="Directorist RAG routing: returns tier (1–4), recommended model slug, and metadata. "
    "Intended for internal use before the main answer model; cache may be used for identical queries.",
)
async def classify_query(body: QueryClassifierRequest) -> QueryClassifierResponse:
    try:
        result = await query_classifier_service.classify(
            body.user_query,
            use_cache=body.use_cache,
        )
        return QueryClassifierResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("query_classifier failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Classification failed: {0!s}".format(e),
        ) from e
