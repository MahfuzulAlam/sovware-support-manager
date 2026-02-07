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
    "empathy_understanding",
    "tone_warmth",
    "professionalism",
    "personalization",
    "clarity",
    "completeness",
    "proactiveness",
    "helpfulness_problem_solving",
    "patience_respect",
    "structure_closing",
]

# Score fields that need validation
SCORE_FIELDS = [
    "empathy_understanding",
    "tone_warmth",
    "professionalism",
    "personalization",
    "clarity",
    "completeness",
    "proactiveness",
    "helpfulness_problem_solving",
    "patience_respect",
    "structure_closing",
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
1. Empathy: Acknowledges customer's situation, shows care, empathetic language
2. Tone: Friendly, warm, human (not robotic/cold)
3. Professionalism: Grammar, spelling, boundaries, brand representation
4. Personalization: Uses name, references situation, tailored (not generic)
5. Clarity: Easy to understand, no jargon, no ambiguity
6. Completeness: All questions answered, sufficient detail
7. Proactiveness: Anticipates questions, offers resources, preventive measures
8. Helpfulness: Offers solutions, can-do attitude, action-oriented
9. Patience: No condescension, handles frustration, treats with dignity
10. Structure: Well-organized, clear next steps, proper closing

Return JSON:
{{
  "evaluation_message": "30-50 words",
  "improvement": "30-50 words",
  "empathy_understanding": 0-10,
  "tone_warmth": 0-10,
  "professionalism": 0-10,
  "personalization": 0-10,
  "clarity": 0-10,
  "completeness": 0-10,
  "proactiveness": 0-10,
  "helpfulness_problem_solving": 0-10,
  "patience_respect": 0-10,
  "structure_closing": 0-10
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

    return {
        "evaluation_message": evaluation_message,
        "improvement": improvement,
        **scores,
    }

