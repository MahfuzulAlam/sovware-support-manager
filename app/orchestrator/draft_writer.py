"""HTTP API for draft_writer (RAG reply generation)."""

import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.draft_writer import DraftWriterRequest, DraftWriterResponse
from app.sub_agents.draft_writer import draft_writer_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/draft", tags=["draft_writer"])


@router.post(
    "/generate",
    response_model=DraftWriterResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate RAG-based draft reply",
    description="Classifies the user query, retrieves relevant Directorist documentation chunks from Pinecone, "
    "and generates a professional support reply using the appropriate AI model (tier 1–4). "
    "Returns the draft text with tier/model metadata.",
)
async def generate_draft(body: DraftWriterRequest) -> DraftWriterResponse:
    """
    Generate a draft support reply using the RAG pipeline.

    1. Classify query tier (1–4) using query_classifier
    2. Retrieve documentation chunks from Pinecone
    3. Generate reply with the appropriate model
    """
    try:
        result = await draft_writer_service.generate_draft(
            user_query=body.user_query,
            use_cache=body.use_cache,
        )
        return DraftWriterResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("draft_writer generate failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Draft generation failed: {0!s}".format(e),
        ) from e
