"""Customer behavior analysis via Groq: classify emotion, intent, and risk from message text."""

import json
import logging
from typing import Any, Dict

from groq import AsyncGroq

from app.config import settings

logger = logging.getLogger(__name__)

LLAMA_BEHAVIOR_SYSTEM = """
You are a customer behavior analysis engine.

Your task is to analyze a customer support message and classify the behavior.

STRICT RULES:
- Output ONLY valid JSON.
- Do NOT add explanations.
- Do NOT add comments.
- Do NOT add markdown.
- Do NOT add text before or after JSON.
- If information is unclear, use null.
- Keep responses concise.
"""

LLAMA_BEHAVIOR_USER = """
Analyze the following customer message and classify it.

Return JSON in this exact structure:

{{
  "emotion": "angry | frustrated | confused | disappointed | neutral | positive",
  "emotion_intensity": 1-5,
  "expectation_gap": "feature_missing | bug | pricing_confusion | renewal_issue | ux_confusion | compatibility_issue | none",
  "problem_type": "installation | search | payment | booking | forms | ui | performance | integration | subscription | other",
  "revenue_risk": "high | medium | low",
  "blame_target": "product | company | support | third_party | none",
  "effort_level": 1-5,
  "refund_intent": true | false,
  "strategic_signal": "short summary of root cause"
}}

Customer Message:
\"\"\"{text}\"\"\"

JSON:
"""


class CustomerBehaviorService:
    """Analyzes customer message text and returns structured behavior classification."""

    def __init__(self) -> None:
        self.client = AsyncGroq(api_key=settings.groq_api_key)
        self.model = settings.groq_model

    async def analyze(self, text: str) -> Dict[str, Any]:
        """
        Analyze customer message and return behavior classification as a dict.

        Args:
            text: Raw customer message text.

        Returns:
            Dict with emotion, emotion_intensity, expectation_gap, problem_type,
            revenue_risk, blame_target, effort_level, refund_intent, strategic_signal.

        Raises:
            ValueError: If the model response is not valid JSON.
            Exception: On Groq API errors.
        """
        if not text or not text.strip():
            return _empty_behavior_response()

        user_prompt = LLAMA_BEHAVIOR_USER.format(text=text.strip())
        try:
            logger.info("Sending customer behavior analysis request to Groq (model=%s)", self.model)
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": LLAMA_BEHAVIOR_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            logger.error("Groq customer behavior API error: %s", e)
            raise

        content = response.choices[0].message.content
        if not content or not content.strip():
            return _empty_behavior_response()

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON from Groq behavior analysis: %s", e)
            raise ValueError(f"Invalid JSON response from Groq: {e}") from e

        return _normalize_behavior_response(data)


def _empty_behavior_response() -> Dict[str, Any]:
    return {
        "emotion": None,
        "emotion_intensity": None,
        "expectation_gap": None,
        "problem_type": None,
        "revenue_risk": None,
        "blame_target": None,
        "effort_level": None,
        "refund_intent": None,
        "strategic_signal": None,
    }


def _normalize_behavior_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure all expected keys exist and types are consistent."""
    return {
        "emotion": data.get("emotion"),
        "emotion_intensity": data.get("emotion_intensity"),
        "expectation_gap": data.get("expectation_gap"),
        "problem_type": data.get("problem_type"),
        "revenue_risk": data.get("revenue_risk"),
        "blame_target": data.get("blame_target"),
        "effort_level": data.get("effort_level"),
        "refund_intent": data.get("refund_intent"),
        "strategic_signal": data.get("strategic_signal"),
    }


customer_behavior_service = CustomerBehaviorService()
