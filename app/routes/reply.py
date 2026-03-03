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

# Import evaluation services (OpenAI and Groq)
from app.services.openai_service import openai_service
from app.services.evaluation_service import groq_evaluation_service

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
        return groq_evaluation_service
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


# Human-readable labels for evaluation score fields (must match prompts.SCORE_FIELDS + average_score)
EVALUATION_SCORE_LABELS = {
    "response_accuracy": "Response Accuracy",
    "tone_empathy": "Tone & Empathy",
    "clarity_structure": "Clarity & Structure",
    "relevance_to_thread": "Relevance to Thread",
    "completeness": "Completeness",
    "proactive_detail": "Proactive Detail",
    "personalization": "Personalization",
    "policy_process_adherence": "Policy & Process Adherence",
    "action_clarity": "Action Clarity",
    "grammar_professionalism": "Grammar & Professionalism",
    "average_score": "Average Score",
}


def build_evaluation_note_description(evaluation_result: Dict[str, Any]) -> str:
    """
    Build a human-readable description from evaluation result for use as a Help Scout note.
    No AI involved; purely formats the evaluation data into text.

    Args:
        evaluation_result: Dict with evaluation_message, improvement, and score fields

    Returns:
        Formatted string suitable for a conversation note
    """
    lines = [
        "---",
        "AI Agent Reply Evaluation",
        "---",
        "",
        "Evaluation:",
        evaluation_result.get("evaluation_message", "—"),
        "",
        "Improvement:",
        evaluation_result.get("improvement", "—"),
        "",
        "Scores (0-10):",
    ]
    for field, label in EVALUATION_SCORE_LABELS.items():
        score = evaluation_result.get(field)
        if score is not None:
            lines.append(f"• {label}: {score}")
    lines.append("")
    return "\n".join(lines)


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

        logger.info(
            f"Evaluation completed successfully for conversation {request.conversation_id}, "
            f"thread {request.thread_id}"
        )

        # Build description and save as note on the Help Scout conversation
        try:
            note_description = build_evaluation_note_description(evaluation_result)
            await helpscout_service.create_note(request.conversation_id, note_description)
            logger.info(f"Evaluation note saved to conversation {request.conversation_id}")
        except Exception as e:
            logger.warning(
                f"Failed to save evaluation note to Help Scout conversation {request.conversation_id}: {e}"
            )
            # Do not fail the request; evaluation response is still returned

        return EvaluationResponse(
            evaluation_message=evaluation_result["evaluation_message"],
            improvement=evaluation_result["improvement"],
            response_accuracy=evaluation_result["response_accuracy"],
            tone_empathy=evaluation_result["tone_empathy"],
            clarity_structure=evaluation_result["clarity_structure"],
            relevance_to_thread=evaluation_result["relevance_to_thread"],
            completeness=evaluation_result["completeness"],
            proactive_detail=evaluation_result["proactive_detail"],
            personalization=evaluation_result["personalization"],
            policy_process_adherence=evaluation_result["policy_process_adherence"],
            action_clarity=evaluation_result["action_clarity"],
            grammar_professionalism=evaluation_result["grammar_professionalism"],
            average_score=evaluation_result["average_score"],
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

