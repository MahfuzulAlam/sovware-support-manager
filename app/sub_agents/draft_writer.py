"""Draft writer sub-agent: orchestrates RAG pipeline (classify → retrieve → generate)."""

import hashlib
import json
import logging
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.ai_models import get_model
from app.services.pinecone_service import pinecone_service
from app.sub_agents.query_classifier import query_classifier_service

logger = logging.getLogger(__name__)

_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_CACHE_MAX = 128


def _cache_key(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    if key not in _CACHE:
        return None
    _CACHE.move_to_end(key)
    return dict(_CACHE[key])


def _cache_set(key: str, value: Dict[str, Any]) -> None:
    _CACHE[key] = value
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)


DRAFT_SYSTEM_TIER_1 = """
You are a friendly senior support engineer at a WordPress plugin company (Directorist).

Your task is to answer a basic user question using ONLY the documentation chunks provided.

STRICT RULES:
- Be concise. Keep the response between 80–150 words.
- Use only information from the documentation context. Never fabricate plugin features, settings names, or steps.
- Structure: short greeting → direct answer → offer further help.
- If the documentation includes a URL, include it as a link.
- Do not mention tier, model name, or Pinecone scores.
"""

DRAFT_SYSTEM_TIER_2 = """
You are a friendly senior support engineer at a WordPress plugin company (Directorist).

Your task is to provide a detailed, step-by-step guide using ONLY the documentation chunks provided.

STRICT RULES:
- Keep the response between 150–250 words.
- Use only information from the documentation context. Never fabricate plugin features, settings names, or steps.
- Structure: brief greeting → numbered or bulleted steps → closing offer to help.
- If the documentation includes URLs, include them as links.
- Format code snippets with backticks when showing settings, shortcodes, or CSS class names.
- Do not mention tier, model name, or Pinecone scores.
"""

DRAFT_SYSTEM_TIER_3 = """
You are a friendly senior support engineer at a WordPress plugin company (Directorist).

Your task is to troubleshoot a problem by reasoning through possible causes using ONLY the documentation chunks provided.

STRICT RULES:
- Keep the response between 200–300 words.
- Use only information from the documentation context. Never fabricate plugin features, settings names, or steps.
- Structure: acknowledge the issue → list 2–4 possible causes or checks → provide resolution steps → offer further help.
- If the documentation includes URLs, include them as links.
- Format any settings paths, code snippets, or command lines with backticks.
- Do not mention tier, model name, or Pinecone scores.
"""

DRAFT_SYSTEM_TIER_4 = """
You are a friendly senior WordPress developer helping with custom Directorist plugin code.

Your task is to provide technical implementation details, code snippets, or development guidance using ONLY the documentation chunks provided.

STRICT RULES:
- Keep the response between 200–400 words depending on complexity.
- Use only information from the documentation context. Never fabricate hooks, functions, or API endpoints.
- Structure: acknowledge the request → show code example or approach → explain key points → offer further help.
- Format all PHP code, hooks, filters, and function names with proper markdown code blocks.
- Include inline comments in code blocks for clarity.
- If the documentation includes URLs, include them as links.
- Do not mention tier, model name, or Pinecone scores.
"""

DRAFT_USER_TEMPLATE = """
User Query:
\"\"\"{user_query}\"\"\"

Retrieved Documentation Context:
{context}

Generate a professional support reply based on the documentation context above.
"""

FALLBACK_REPLY = """
Thank you for reaching out. I'd be happy to help, but I need a bit more detail to provide an accurate answer. Could you please clarify your question or let me know which specific Directorist feature you're working with?

If this is urgent, feel free to contact our support team directly and we'll assist you right away.
"""


def _system_prompt_for_tier(tier: int) -> str:
    if tier == 1:
        return DRAFT_SYSTEM_TIER_1
    if tier == 2:
        return DRAFT_SYSTEM_TIER_2
    if tier == 3:
        return DRAFT_SYSTEM_TIER_3
    if tier == 4:
        return DRAFT_SYSTEM_TIER_4
    return DRAFT_SYSTEM_TIER_2


def _max_tokens_for_tier(tier: int) -> int:
    if tier == 1:
        return 400
    if tier == 2:
        return 600
    if tier == 3:
        return 800
    if tier == 4:
        return 2048
    return 600


def _temperature_for_tier(tier: int) -> float:
    if tier == 1:
        return 0.3
    if tier == 2:
        return 0.4
    if tier == 3:
        return 0.4
    if tier == 4:
        return 0.5
    return 0.4


def _format_chunks(chunks: List[Dict[str, Any]]) -> str:
    if not chunks:
        return "(No documentation chunks found)"

    lines: List[str] = []
    for i, chunk in enumerate(chunks, 1):
        text = chunk.get("text", "").strip()
        source = chunk.get("source", "")
        section = chunk.get("section", "")
        url = chunk.get("url", "")

        lines.append(f"--- Chunk {i} ---")
        if source:
            lines.append(f"Source: {source}")
        if section:
            lines.append(f"Section: {section}")
        if url:
            lines.append(f"URL: {url}")
        lines.append("")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)


class DraftWriterService:
    """Orchestrates RAG pipeline: classify query → retrieve chunks → generate draft reply."""

    def __init__(self) -> None:
        pass

    async def generate_draft(
        self,
        user_query: str,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a draft reply for a user support query.

        Pipeline:
        1. Classify query tier using query_classifier
        2. Retrieve relevant chunks from Pinecone
        3. Select model based on tier
        4. Generate draft reply

        Args:
            user_query: Raw user question
            use_cache: Whether to use cached classifications and drafts

        Returns:
            Dict with: draft, tier, model, confidence, chunks_used, classification

        Raises:
            Exception: On classifier, retrieval, or generation errors
        """
        if not user_query or not user_query.strip():
            return {
                "draft": FALLBACK_REPLY,
                "tier": 0,
                "model": "",
                "confidence": 0.0,
                "chunks_used": 0,
                "classification": {},
            }

        q = user_query.strip()
        cache_key = _cache_key(q)

        if use_cache:
            cached = _cache_get(cache_key)
            if cached is not None:
                logger.info("draft_writer cache hit")
                return cached

        try:
            classification = await query_classifier_service.classify(q, use_cache=use_cache)
        except Exception as e:
            logger.warning("query_classifier failed; defaulting to tier 3: %s", e)
            classification = {
                "tier": 3,
                "type": "Troubleshooting / Multi-step Reasoning",
                "model": "gpt-4.1-mini",
                "confidence": 0.0,
                "reason": "Classifier timeout; defaulted to tier 3.",
                "keywords_matched": [],
            }

        tier = int(classification.get("tier", 3))
        model_slug = classification.get("model", "gpt-4o-mini")
        confidence = float(classification.get("confidence", 0.5))

        try:
            chunks = await pinecone_service.search(query_text=q, tier=tier)
        except Exception as e:
            logger.error("Pinecone search failed: %s", e)
            chunks = []

        if not chunks:
            logger.warning("No chunks retrieved from Pinecone; returning fallback reply")
            result = {
                "draft": FALLBACK_REPLY,
                "tier": tier,
                "model": model_slug,
                "confidence": confidence,
                "chunks_used": 0,
                "classification": classification,
            }
            if use_cache:
                _cache_set(cache_key, result)
            return result

        context = _format_chunks(chunks)
        system_prompt = _system_prompt_for_tier(tier)
        user_prompt = DRAFT_USER_TEMPLATE.format(user_query=q, context=context)

        try:
            model_service = get_model(tier, model_slug)
        except Exception as e:
            logger.error("Failed to load model service for tier=%d model=%s: %s", tier, model_slug, e)
            result = {
                "draft": FALLBACK_REPLY,
                "tier": tier,
                "model": model_slug,
                "confidence": confidence,
                "chunks_used": len(chunks),
                "classification": classification,
            }
            if use_cache:
                _cache_set(cache_key, result)
            return result

        try:
            draft = await model_service.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=_temperature_for_tier(tier),
                max_tokens=_max_tokens_for_tier(tier),
            )
        except Exception as e:
            logger.error("Model generation failed (tier=%d, model=%s): %s", tier, model_slug, e)
            result = {
                "draft": FALLBACK_REPLY,
                "tier": tier,
                "model": model_slug,
                "confidence": confidence,
                "chunks_used": len(chunks),
                "classification": classification,
            }
            if use_cache:
                _cache_set(cache_key, result)
            return result

        if not draft or not draft.strip():
            logger.warning("Model returned empty draft; using fallback")
            draft = FALLBACK_REPLY

        result = {
            "draft": draft.strip(),
            "tier": tier,
            "model": model_slug,
            "confidence": confidence,
            "chunks_used": len(chunks),
            "classification": classification,
        }

        if use_cache:
            _cache_set(cache_key, result)
        return result


draft_writer_service = DraftWriterService()
