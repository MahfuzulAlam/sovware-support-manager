"""Forensic evaluation service: analyze full conversation with OpenAI and add a note."""

import json
import logging
import re
from typing import Any, Dict, List

from openai import AsyncOpenAI

from app.config import settings
from app.services.helpscout_service import helpscout_service

logger = logging.getLogger(__name__)

FORENSIC_SYSTEM = """You are a customer support forensic analyst. Your task is to review an entire support conversation and identify what went wrong and why the customer may be dissatisfied.

STRICT RULES:
- Output ONLY valid JSON.
- Do NOT add markdown, explanations, or text outside the JSON.
- Use the exact keys specified below.
- For list fields, provide concise items. Use empty arrays if none apply.
"""

FORENSIC_USER_TEMPLATE = """Analyze this support conversation and return a JSON object with these exact keys:

{{
  "issues": ["list of what went wrong in the conversation (e.g. slow response, wrong tone, missing information)"],
  "dissatisfaction_reasons": ["reasons the customer is or may be dissatisfied, based on evidence in the thread"],
  "suggestions_for_agent": ["concrete suggestions for the agent on what to do to make things right (e.g. apologize for X, offer Y, clarify Z)"]
}}

Conversation (subject and threads in order):

{conversation_text}

JSON:"""

# Max characters sent to the model to avoid token limits
FORENSIC_MAX_INPUT_LENGTH = 12000


def _strip_html(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def _build_conversation_text(conversation_data: Dict[str, Any]) -> str:
    """Build a single text from conversation subject and all threads for forensic analysis."""
    parts: List[str] = []
    subject = (conversation_data.get("subject") or "").strip()
    if subject:
        parts.append(f"Subject: {subject}")
    embedded = conversation_data.get("_embedded") or {}
    threads = embedded.get("threads") or []
    # Help Scout thread types: customer, message (agent), note, etc.
    type_label = {"customer": "Customer", "message": "Agent", "note": "Note"}
    for i, thread in enumerate(threads, 1):
        thread_type = thread.get("type") or "unknown"
        label = type_label.get(thread_type, thread_type.capitalize())
        body = _strip_html(thread.get("body") or "")
        if body:
            parts.append(f"[{label}]: {body}")
    result = "\n\n".join(parts) if parts else ""
    if len(result) > FORENSIC_MAX_INPUT_LENGTH:
        result = result[: FORENSIC_MAX_INPUT_LENGTH - 3] + "..."
    return result


def _response_to_note(data: Dict[str, Any]) -> str:
    """Turn forensic JSON response into a readable note body."""
    lines = [
        "---",
        "Forensic Evaluation",
        "---",
        "",
    ]
    issues = data.get("issues") or []
    if issues:
        lines.append("What went wrong:")
        for item in issues:
            lines.append(f"• {item}")
        lines.append("")
    reasons = data.get("dissatisfaction_reasons") or []
    if reasons:
        lines.append("Reasons for customer dissatisfaction:")
        for item in reasons:
            lines.append(f"• {item}")
        lines.append("")
    suggestions = data.get("suggestions_for_agent") or []
    if suggestions:
        lines.append("Suggestions for the agent:")
        for item in suggestions:
            lines.append(f"• {item}")
    if not (issues or reasons or suggestions):
        lines.append("No structured issues or suggestions returned.")
    return "\n".join(lines).strip()


class ForensicEvaluationService:
    """Evaluate a full Help Scout conversation with OpenAI and add a note."""

    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for forensic evaluation")
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    async def evaluate_and_add_note(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get all threads for the conversation, run OpenAI forensic evaluation,
        then add a note to the conversation with the processed result.

        Returns:
            The parsed JSON result from OpenAI (issues, dissatisfaction_reasons, suggestions_for_agent).

        Raises:
            ValueError: If OpenAI key is missing or response is not valid JSON.
            Exception: On Help Scout or OpenAI API errors.
        """
        # 1. Get conversation with all threads
        conversation_data = await helpscout_service.get_conversation(
            conversation_id, embed_threads=True
        )
        conversation_text = _build_conversation_text(conversation_data)
        if not conversation_text.strip():
            logger.warning("No thread content for conversation %s", conversation_id)
            empty_result = {
                "issues": [],
                "dissatisfaction_reasons": [],
                "suggestions_for_agent": [],
            }
            note_body = _response_to_note(empty_result)
            await helpscout_service.create_note(conversation_id, note_body)
            return empty_result

        # 2. Call OpenAI for forensic analysis
        user_prompt = FORENSIC_USER_TEMPLATE.format(conversation_text=conversation_text)
        logger.info("Sending forensic evaluation request to OpenAI for conversation %s", conversation_id)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": FORENSIC_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content or not content.strip():
            raise ValueError("Empty forensic evaluation response from OpenAI")

        try:
            result = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON from forensic evaluation: %s", e)
            raise ValueError(f"Invalid JSON from OpenAI forensic evaluation: {e}") from e

        # Normalize to expected keys
        result.setdefault("issues", [])
        result.setdefault("dissatisfaction_reasons", [])
        result.setdefault("suggestions_for_agent", [])

        # 3. Add note to conversation
        note_body = _response_to_note(result)
        await helpscout_service.create_note(conversation_id, note_body)
        logger.info("Forensic evaluation note added to conversation %s", conversation_id)

        return result


# Lazy singleton: avoid requiring OpenAI key at import time if not used
_forensic_evaluation_service: "ForensicEvaluationService | None" = None


def get_forensic_evaluation_service() -> ForensicEvaluationService:
    """Return the forensic evaluation service instance (lazy init)."""
    global _forensic_evaluation_service
    if _forensic_evaluation_service is None:
        _forensic_evaluation_service = ForensicEvaluationService()
    return _forensic_evaluation_service
