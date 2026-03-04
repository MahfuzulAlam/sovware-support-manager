"""API routes for reply evaluation and customer behavior analysis."""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any
import logging
import re

from app.schemas.evaluation import EvaluationRequest, EvaluationResponse
from app.schemas.customer_behavior import CustomerBehaviorResponse
from app.config import settings
from app.services.helpscout_service import helpscout_service
from app.sub_agents.customer_behavior import customer_behavior_service
from app.services.supabase_service import ai_customer_reply_row_exists, insert_ai_customer_reply_row

# Import evaluation services (OpenAI and Groq)
from app.services.openai_service import openai_service
from app.sub_agents.evaluator import groq_evaluation_service

logger = logging.getLogger(__name__)


def _extract_thread_body(thread_data: Dict[str, Any]) -> str:
    """Extract plain text from a Help Scout thread (strip HTML). Avoids importing webhook_handlers (circular import)."""
    body = thread_data.get("body") or ""
    if isinstance(body, str):
        body = re.sub(r"<[^>]+>", "", body)
    return (body or "").strip()

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


async def run_agent_evaluation(conversation_id: str, thread_id: str) -> Dict[str, Any]:
    """
    Run agent reply evaluation for a conversation and thread (shared by route and webhook).

    Fetches conversation and thread from Help Scout, runs AI evaluation, and creates a
    Help Scout note only when average_score < 6.

    Returns:
        Evaluation result dict with evaluation_message, improvement, and score fields.

    Raises:
        HTTPException: On fetch failure, thread not found, or AI service failure.
    """
    conversation_data = await helpscout_service.get_conversation(
        conversation_id, embed_threads=True
    )
    thread_data = None
    if "_embedded" in conversation_data and "threads" in conversation_data["_embedded"]:
        threads = conversation_data["_embedded"]["threads"]
        try:
            thread_id_int = int(thread_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid thread_id format: {thread_id}. Must be a number.",
            )
        for thread in threads:
            if thread.get("id") == thread_id_int:
                thread_data = thread
                break
    if not thread_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread {thread_id} not found in conversation {conversation_id}",
        )
    conversation_text = extract_text_from_helpscout_data(conversation_data)
    thread_text = extract_text_from_helpscout_data(thread_data)
    ai_service = get_ai_service()
    evaluation_result = await ai_service.evaluate_conversation(
        conversation_text, thread_text
    )
    average_score = evaluation_result.get("average_score")
    if average_score is not None and average_score < 6:
        try:
            note_description = build_evaluation_note_description(
                evaluation_result, thread_id
            )
            await helpscout_service.create_note(conversation_id, note_description)
            logger.info(
                "Evaluation note saved to conversation %s (average_score=%s < 6)",
                conversation_id,
                average_score,
            )
        except Exception as e:
            logger.warning(
                "Failed to save evaluation note to Help Scout conversation %s: %s",
                conversation_id,
                e,
            )
    else:
        logger.info(
            "Skipping evaluation note for conversation %s (average_score=%s >= 6)",
            conversation_id,
            average_score,
        )
    return evaluation_result


def build_evaluation_note_description(evaluation_result: Dict[str, Any], thread_id: int) -> str:
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
        "AI Agent Reply Evaluation: "+ str(thread_id),
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

        try:
            evaluation_result = await run_agent_evaluation(
                request.conversation_id, request.thread_id
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to evaluate agent reply: %s", e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to evaluate: {str(e)}",
            ) from e

        logger.info(
            "Evaluation completed for conversation %s thread %s",
            request.conversation_id,
            request.thread_id,
        )

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
        logger.error("Unexpected error in evaluate_agent_reply: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


async def run_customer_reply_evaluation(conversation_id: str, thread_id: str) -> Dict[str, Any]:
    """
    Run customer behavior analysis for a thread: fetch conversation/thread, check if already
    saved, run Groq analysis, apply high-priority tag if needed, insert into ai_customer_reply.
    Returns the result dict for the response. Raises ValueError("thread_not_found") or
    ValueError("no_text") for the endpoint to map to 404/400; other exceptions propagate.
    """
    thread_id_str = str(thread_id)
    conversation_data = await helpscout_service.get_conversation(
        conversation_id, embed_threads=True
    )
    thread_data = None
    if "_embedded" in conversation_data and "threads" in conversation_data["_embedded"]:
        threads = conversation_data["_embedded"]["threads"]
        try:
            thread_id_int = int(thread_id_str)
        except ValueError:
            raise ValueError("thread_not_found")
        for thread in threads:
            if thread.get("id") == thread_id_int:
                thread_data = thread
                break
    if not thread_data:
        raise ValueError("thread_not_found")
    text = _extract_thread_body(thread_data)
    if not text:
        raise ValueError("no_text")
    if await ai_customer_reply_row_exists(conversation_id, thread_id_str):
        logger.info(
            "ai_customer_reply already has analysis for conversation_id=%s thread_id=%s; skipping API call",
            conversation_id,
            thread_id_str,
        )
        return {"strategic_signal": "Already analyzed; no new evaluation performed."}
    result = await customer_behavior_service.analyze(text)
    revenue_risk = (result.get("revenue_risk") or "").strip().lower()
    emotion = (result.get("emotion") or "").strip().lower()
    intensity_val = result.get("emotion_intensity")
    try:
        emotion_intensity = int(intensity_val) if intensity_val is not None else None
    except (TypeError, ValueError):
        emotion_intensity = None
    high_priority = (
        revenue_risk in ("high", "medium")
        or emotion == "angry"
        or (emotion == "frustrated" and emotion_intensity is not None and emotion_intensity > 3)
    )
    if high_priority:
        existing_tags = []
        for t in conversation_data.get("tags") or []:
            if isinstance(t, dict) and "tag" in t:
                existing_tags.append(str(t["tag"]).strip())
            elif isinstance(t, str):
                existing_tags.append(t.strip())
        if "high priority" not in existing_tags:
            existing_tags.append("high priority")
            try:
                await helpscout_service.update_conversation_tags(conversation_id, existing_tags)
                logger.info(
                    "Added 'high priority' tag to conversation %s (revenue_risk=%s, emotion=%s, emotion_intensity=%s)",
                    conversation_id,
                    revenue_risk,
                    emotion,
                    emotion_intensity,
                )
            except Exception as e:
                logger.warning("Failed to add high priority tag to conversation %s: %s", conversation_id, e)
    summary = result.get("strategic_signal") or "Customer behavior analysis"
    row = {
        "conversation_id": conversation_id,
        "thread_id": thread_id_str,
        "summary": summary,
        "urgency": None,
        "category": None,
        "next_action": None,
        "model": "groq",
        "cost": None,
        "emotion": result.get("emotion"),
        "emotion_intensity": result.get("emotion_intensity"),
        "expectation_gap": result.get("expectation_gap"),
        "revenue_risk": result.get("revenue_risk"),
        "blame_target": result.get("blame_target"),
        "strategic_signal": result.get("strategic_signal"),
        "effort_level": result.get("effort_level"),
        "refund_intent": result.get("refund_intent"),
    }
    try:
        await insert_ai_customer_reply_row(row)
    except Exception as e:
        logger.warning(
            "Failed to persist ai_customer_reply for conversation %s thread %s: %s",
            conversation_id,
            thread_id_str,
            e,
        )
    return result


@router.post(
    "/customer",
    response_model=CustomerBehaviorResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze customer message behavior",
    description="Get the specified thread from a Help Scout conversation, extract the customer message text, and analyze behavior (emotion, intent, risk) using Groq.",
)
async def evaluate_customer_reply(request: EvaluationRequest) -> CustomerBehaviorResponse:
    """
    Analyze a customer message thread using Groq (customer behavior engine).

    1. Fetches the conversation with embedded threads from Help Scout.
    2. Finds the thread by thread_id and extracts plain text from the body.
    3. Sends the text to Groq with the behavior analysis prompt and returns the classification.
    """
    logger.info(
        "Analyzing customer thread %s in conversation %s",
        request.thread_id,
        request.conversation_id,
    )
    try:
        result = await run_customer_reply_evaluation(request.conversation_id, request.thread_id)
        return CustomerBehaviorResponse(**result)
    except ValueError as e:
        msg = str(e)
        if msg == "thread_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread {0} not found in conversation {1}".format(
                    request.thread_id, request.conversation_id
                ),
            ) from e
        if msg == "no_text":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thread has no body text to analyze.",
            ) from e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        ) from e
    except Exception as e:
        logger.error("Customer reply evaluation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch or analyze: {0!s}".format(e),
        ) from e
