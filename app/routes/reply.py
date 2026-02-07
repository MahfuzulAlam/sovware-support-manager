"""API routes for reply evaluation."""

from fastapi import APIRouter, HTTPException, status
# Database disabled for now
# from sqlalchemy.ext.asyncio import AsyncSession
# from app.database import get_db
# from app.models.evaluation import Evaluation
from typing import Dict, Any
import logging
import re

from app.schemas.evaluation import EvaluationRequest, EvaluationResponse
from app.config import settings
from app.services.helpscout import helpscout_service

# Import both services
from app.services.openai_service import openai_service
from app.services.groq_service import groq_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reply", tags=["reply"])


def get_ai_service():
    """
    Get the appropriate AI service based on configuration.
    
    Returns:
        The configured AI service instance
        
    Raises:
        ValueError: If ai_api_type is invalid
    """
    if settings.ai_api_type == "openai":
        return openai_service
    elif settings.ai_api_type == "groq":
        return groq_service
    else:
        raise ValueError(
            f"Invalid ai_api_type: {settings.ai_api_type}. Must be 'openai' or 'groq'"
        )


def extract_text_from_helpscout_data(data: Dict[str, Any], max_length: int = 2000) -> str:
    """
    Extract readable text from Help Scout API response.
    Optimized to extract only essential information to reduce token usage.

    Args:
        data: Help Scout API response data
        max_length: Maximum length of extracted text (default: 2000 chars)

    Returns:
        String representation of the data (truncated if needed)
    """
    if isinstance(data, dict):
        text_parts = []
        
        # Extract subject (important context)
        if "subject" in data:
            text_parts.append(f"Subject: {data['subject']}")
        
        # Extract preview (usually most recent message summary)
        if "preview" in data:
            text_parts.append(f"Preview: {data['preview']}")
        
        # For threads, extract only the most recent/relevant ones
        # Limit to last 3 threads to reduce size
        if "_embedded" in data and "threads" in data["_embedded"]:
            threads = data["_embedded"]["threads"]
            # Get last 3 threads (most recent)
            recent_threads = threads[-3:] if len(threads) > 3 else threads
            for thread in recent_threads:
                if "body" in thread:
                    # Extract body text, remove HTML tags if present
                    body = str(thread.get("body", ""))
                    # Simple HTML tag removal (basic)
                    body = re.sub(r'<[^>]+>', '', body)
                    if body.strip():
                        text_parts.append(f"Thread: {body.strip()}")
        elif "body" in data:
            # If no embedded threads, use body directly
            body = str(data["body"])
            body = re.sub(r'<[^>]+>', '', body)
            if body.strip():
                text_parts.append(f"Body: {body.strip()}")
        
        result = "\n".join(text_parts) if text_parts else str(data)
        
        # Truncate if too long (keep the end which is usually more relevant)
        if len(result) > max_length:
            result = "..." + result[-(max_length - 3):]
        
        return result
    
    return str(data)[:max_length] if len(str(data)) > max_length else str(data)


@router.post(
    "/agent",
    response_model=EvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Evaluate agent reply",
    description="Evaluate an agent's reply in a Help Scout conversation using AI",
)
async def evaluate_agent_reply(
    request: EvaluationRequest,
    # Database disabled for now
    # db: AsyncSession = Depends(get_db),
) -> EvaluationResponse:
    """
    Evaluate an agent's reply using AI.

    This endpoint:
    1. Fetches conversation and thread data from Help Scout
    2. Sends the data to AI service (OpenAI or Groq) for evaluation
    3. Returns the evaluation result (database storage disabled)

    Args:
        request: Evaluation request containing conversation_id and thread_id

    Returns:
        EvaluationResponse with evaluation details

    Raises:
        HTTPException: If Help Scout API fails or AI service fails
    """
    try:
        logger.info(
            f"Evaluating agent reply for conversation {request.conversation_id}, "
            f"thread {request.thread_id} using {settings.ai_api_type.upper()}"
        )

        # Fetch conversation with embedded threads from Help Scout
        try:
            conversation_data = await helpscout_service.get_conversation(
                request.conversation_id, embed_threads=True
            )
            
            # Extract the specific thread from embedded threads
            thread_data = None
            if "_embedded" in conversation_data and "threads" in conversation_data["_embedded"]:
                threads = conversation_data["_embedded"]["threads"]
                # Find thread by ID (convert thread_id to int for comparison)
                try:
                    thread_id_int = int(request.thread_id)
                except ValueError:
                    logger.error(f"Invalid thread_id format: {request.thread_id}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid thread_id format: {request.thread_id}. Must be a number.",
                    )
                
                for thread in threads:
                    if thread.get("id") == thread_id_int:
                        thread_data = thread
                        break
            
            if not thread_data:
                logger.error(
                    f"Thread {request.thread_id} not found in conversation {request.conversation_id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Thread {request.thread_id} not found in conversation {request.conversation_id}",
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch data from Help Scout: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch data from Help Scout: {str(e)}",
            )

        # Extract text from Help Scout data
        conversation_text = extract_text_from_helpscout_data(conversation_data)
        thread_text = extract_text_from_helpscout_data(thread_data)

        # Get the appropriate AI service based on configuration
        ai_service = get_ai_service()
        
        # Evaluate using the configured AI service
        try:
            evaluation_result = await ai_service.evaluate_conversation(
                conversation_text, thread_text
            )
        except Exception as e:
            logger.error(f"Failed to evaluate with {settings.ai_api_type.upper()}: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to evaluate with {settings.ai_api_type.upper()}: {str(e)}",
            )

        # Database storage disabled - return evaluation directly
        logger.info(
            f"Evaluation completed successfully for conversation {request.conversation_id}, "
            f"thread {request.thread_id}"
        )

        return EvaluationResponse(
            evaluation_message=evaluation_result["evaluation_message"],
            improvement=evaluation_result["improvement"],
            empathy_understanding=evaluation_result["empathy_understanding"],
            tone_warmth=evaluation_result["tone_warmth"],
            professionalism=evaluation_result["professionalism"],
            personalization=evaluation_result["personalization"],
            clarity=evaluation_result["clarity"],
            completeness=evaluation_result["completeness"],
            proactiveness=evaluation_result["proactiveness"],
            helpfulness_problem_solving=evaluation_result["helpfulness_problem_solving"],
            patience_respect=evaluation_result["patience_respect"],
            structure_closing=evaluation_result["structure_closing"],
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in evaluate_agent_reply: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )

