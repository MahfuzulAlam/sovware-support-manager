"""Shared prompts and validation for AI evaluation services."""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# System message for AI evaluation (optimized for token efficiency)
SYSTEM_MESSAGE = (
    "Expert at evaluating customer support. Respond with valid JSON only. "
    "Keep messages 30-50 words."
)

# Required fields in the evaluation response
REQUIRED_FIELDS = [
    "evaluation_message",
    "improvement",
    "response_accuracy",
    "tone_empathy",
    "clarity_structure",
    "relevance_to_thread",
    "completeness",
    "proactive_detail",
    "personalization",
    "policy_process_adherence",
    "action_clarity",
    "grammar_professionalism",
    "average_score"
]

# Score fields that need validation
SCORE_FIELDS = [
    "response_accuracy",
    "tone_empathy",
    "clarity_structure",
    "relevance_to_thread",
    "completeness",
    "proactive_detail",
    "personalization",
    "policy_process_adherence",
    "action_clarity",
    "grammar_professionalism"
]


def truncate_text(text: str, max_chars: int = 2000) -> str:
    """
    Truncate text to a maximum character limit to reduce token usage.
    
    Args:
        text: Text to truncate
        max_chars: Maximum characters allowed (default: 2000)
        
    Returns:
        Truncated text with ellipsis if needed
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."


def build_evaluation_prompt(conversation_text: str, thread_text: str) -> str:
    """
    Build the evaluation prompt for AI services.
    Optimized for smaller models with token limits.

    Args:
        conversation_text: The full conversation text from Help Scout
        thread_text: The specific agent reply thread text from Help Scout

    Returns:
        Formatted prompt string
    """
    # Truncate input texts to reduce token usage (keep last 1500 chars for context)
    conversation_text = truncate_text(conversation_text, max_chars=1500)
    thread_text = truncate_text(thread_text, max_chars=1000)
    
    return f"""Evaluate this customer support interaction. Score 0-10 for each parameter.

Conversation: {conversation_text}
Agent Reply: {thread_text}

Parameters:
1. Response Accuracy: Information is factually correct, technically sound, no misleading guidance
2. Tone & Empathy: Acknowledges customer's situation, shows care, empathetic language, not transactional or robotic
3. Clarity & Structure: Easy to understand, no jargon, well-organized reply, logical flow, proper and professional closing
4. Relevance to the Thread: Directly addresses what was raised in this specific thread, no generic or off-topic response
5. Completeness: All questions in the thread answered, sufficient detail, no gaps left unaddressed
6. Proactive Detail: Anticipates follow-up questions, offers resources, addresses likely next pain points before customer asks
7. Personalization: Uses customer name, references their specific situation, tailored response (not generic or copy-paste)
8. Policy & Process Adherence: Follows company guidelines, escalation procedures, and approved messaging where required
9. Action Clarity: Next steps clearly defined, customer knows exactly what to do, no vague instructions
10. Grammar & Professionalism: Free of spelling/grammar errors, polished, brand-appropriate presentation throughout the reply

Return JSON:
{{
  "evaluation_message": "30-50 words",
  "improvement": "30-50 words",
  "response_accuracy": 0-10,
  "tone_empathy": 0-10,
  "clarity_structure": 0-10,
  "relevance_to_thread": 0-10,
  "completeness": 0-10,
  "proactive_detail": 0-10,
  "personalization": 0-10,
  "policy_process_adherence": 0-10,
  "action_clarity": 0-10,
  "grammar_professionalism": 0-10,
  "average_score": 0-10
}}
"""


def validate_and_process_evaluation_response(
    evaluation_data: Dict[str, Any], service_name: str = "AI"
) -> Dict[str, Any]:
    """
    Validate and process the evaluation response from AI service.

    Args:
        evaluation_data: Raw evaluation data from AI service
        service_name: Name of the AI service (for logging)

    Returns:
        Processed evaluation data with validated scores and truncated messages

    Raises:
        ValueError: If required fields are missing or validation fails
    """
    # Validate response structure
    for field in REQUIRED_FIELDS:
        if field not in evaluation_data:
            raise ValueError(f"Missing '{field}' in {service_name} response")

    # Process evaluation message
    evaluation_message = str(evaluation_data["evaluation_message"])
    words = evaluation_message.split()
    if len(words) > 50:
        logger.warning(
            f"Evaluation message has {len(words)} words, truncating to 50 words"
        )
        evaluation_message = " ".join(words[:50])

    # Process improvement
    improvement = str(evaluation_data["improvement"])
    improvement_words = improvement.split()
    if len(improvement_words) > 50:
        logger.warning(
            f"Improvement has {len(improvement_words)} words, truncating to 50 words"
        )
        improvement = " ".join(improvement_words[:50])

    # Validate and clamp all scores to 0-10 range
    scores = {}
    for field in SCORE_FIELDS:
        score = float(evaluation_data[field])
        if not (0.0 <= score <= 10.0):
            logger.warning(
                f"Score {field} ({score}) is outside 0-10 range, clamping"
            )
            score = max(0.0, min(10.0, score))
        scores[field] = score

    # Process average_score (required but not in SCORE_FIELDS)
    average_score = float(evaluation_data["average_score"])
    if not (0.0 <= average_score <= 10.0):
        logger.warning(
            f"average_score ({average_score}) is outside 0-10 range, clamping"
        )
        average_score = max(0.0, min(10.0, average_score))
    scores["average_score"] = average_score

    return {
        "evaluation_message": evaluation_message,
        "improvement": improvement,
        **scores,
    }

