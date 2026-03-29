"""Query classifier sub-agent: Directorist RAG routing — tier 1–4 via lightweight Groq model."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from groq import AsyncGroq

from app.config import settings

logger = logging.getLogger(__name__)

# Answer model per query type (tier). Edit this list only — the classifier LLM does not choose models.
# Each row: tier (1–4), type (label), model (slug passed to your RAG / answer layer).
QUERY_TIER_MODELS: List[Dict[str, Any]] = [
    {"tier": 1, "type": "Basic / Lookup", "model": "llama-3.1-8b"},
    {"tier": 2, "type": "Configuration/How-to", "model": "gpt-4o-mini"},
    {"tier": 3, "type": "Troubleshooting / Multi-step Reasoning", "model": "gpt-4.1-mini"},
    {"tier": 4, "type": "Custom Code / Development", "model": "claude-sonnet-4-5"},
]


def _tier_row(tier: int) -> Dict[str, Any]:
    """Look up type + model for a tier from QUERY_TIER_MODELS (fallback: tier 3 row or default)."""
    for row in QUERY_TIER_MODELS:
        if int(row.get("tier", 0)) == tier:
            return row
    if QUERY_TIER_MODELS:
        for row in QUERY_TIER_MODELS:
            if int(row.get("tier", 0)) == 3:
                return row
        return QUERY_TIER_MODELS[-1]
    return {"tier": 3, "type": "Troubleshooting / Multi-step Reasoning", "model": "gpt-4.1-mini"}

CODE_WORDS = [
    "write",
    "build",
    "create",
    "code",
    "hook",
    "filter",
    "template",
    "php",
    "function",
    "script",
    "endpoint",
    "rest",
    "api",
    "extend",
]

ERROR_PHRASES = [
    "not working",
    "doesn't show",
    "does not show",
    "dont show",
    "do not show",
]

ERROR_WORDS = [
    "broken",
    "error",
    "conflict",
    "slow",
    "missing",
    "fails",
    "404",
    "blank",
]

QUERY_CLASSIFIER_SYSTEM = """
You are a query routing agent for a Directorist WordPress plugin RAG support application.
Your ONLY job is to read the user's question and return a structured JSON classification.
You do not answer the question. You do not add commentary. You classify and return JSON.

STRICT RULES:
- Output ONLY valid JSON. No markdown, no code fences, no text before or after JSON.
- Apply ALL classification rules from the user message before choosing tier and confidence.
- One tier only (1–4). Never hedge or return multiple tiers.
"""

QUERY_CLASSIFIER_USER = """
## Tiers

### TIER 1 — Basic / Lookup
Covers: installation steps, definitions, feature existence ("does X support Y?"),
navigation ("where do I find X in admin?"), single-fact retrieval. One doc chunk is enough.

### TIER 2 — Configuration / How-to
Covers: multi-step setup, extension configuration (Stripe, PayPal, WPML, Mailchimp, BuddyBoss, Elementor),
monetisation, custom fields, multi-directory, search filters, map configuration. 3–6 steps, no custom code.

### TIER 3 — Troubleshooting / Multi-step Reasoning
Covers: debugging conflicts, broken layouts, map failures, 404, cache, theme/page-builder issues,
performance, SEO problems. Multiple possible causes.

### TIER 4 — Custom Code / Development
Covers: PHP hooks/filters, template overrides, child themes, REST API, custom extensions, OOP PHP,
migration scripts, bulk import/export, database queries.

## Classification Rules

1. When in doubt, choose the higher (more capable) tier.
2. Output a realistic confidence in 0.0–1.0. If confidence is below 0.60, the server will bump the tier up by one (after applying rules 3–4).
3. Code keywords → Tier 4 minimum: write, build, create, code, hook, filter, template, PHP, function, script, endpoint, REST, API, extend, custom plugin.
4. Error/conflict keywords → Tier 3 minimum: not working, broken, error, conflict, slow, missing, fails, doesn't show, 404, blank.

## Output JSON (exact keys)

Do NOT output a model name. The server maps the final tier to an answer model.

{{
  "tier": <int 1-4>,
  "type": "<exact tier label string>",
  "confidence": <float 0.0-1.0>,
  "reason": "<one sentence, max 15 words>",
  "keywords_matched": ["<1-5 tokens or short phrases from the query>"]
}}

type must be EXACTLY one of:
- "Basic / Lookup"
- "Configuration/How-to"
- "Troubleshooting / Multi-step Reasoning"
- "Custom Code / Development"

User query:
\"\"\"{user_query}\"\"\"

JSON:
"""

_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_CACHE_MAX = 256


def _cache_key(user_query: str) -> str:
    return hashlib.sha256(user_query.strip().encode("utf-8")).hexdigest()


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


def _has_code_keywords(text: str) -> bool:
    t = text.lower()
    if "custom plugin" in t:
        return True
    for w in CODE_WORDS:
        if re.search(rf"\b{re.escape(w)}\b", t, re.IGNORECASE):
            return True
    return False


def _has_error_keywords(text: str) -> bool:
    t = text.lower()
    for phrase in ERROR_PHRASES:
        if phrase in t:
            return True
    for w in ERROR_WORDS:
        if re.search(rf"\b{re.escape(w)}\b", t, re.IGNORECASE):
            return True
    return False


def _keyword_floor_tier(text: str) -> int:
    floor = 1
    if _has_error_keywords(text):
        floor = max(floor, 3)
    if _has_code_keywords(text):
        floor = max(floor, 4)
    return floor


def _clamp_tier(tier: Any) -> int:
    try:
        t = int(tier)
    except (TypeError, ValueError):
        return 2
    return max(1, min(4, t))


def _coerce_float(v: Any) -> float:
    if v is None:
        return 0.5
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, f))


def _coerce_keywords(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v.strip()] if v.strip() else []
    if isinstance(v, list):
        out: List[str] = []
        for x in v[:8]:
            if isinstance(x, str) and x.strip():
                out.append(x.strip())
        return out[:5]
    return []


def _apply_routing_rules(user_query: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Enforce keyword floors and confidence tier bump; sync type/model to final tier."""
    tier = _clamp_tier(data.get("tier"))
    confidence = _coerce_float(data.get("confidence"))
    reason = (data.get("reason") or "").strip() or "Classified by routing rules."
    keywords = _coerce_keywords(data.get("keywords_matched"))

    floor = _keyword_floor_tier(user_query)
    tier = max(tier, floor)

    if confidence < 0.60:
        tier = min(4, tier + 1)

    tier = _clamp_tier(tier)
    row = _tier_row(tier)
    out = {
        "tier": tier,
        "type": str(row.get("type") or ""),
        "model": str(row.get("model") or ""),
        "confidence": confidence,
        "reason": reason[:500],
        "keywords_matched": keywords or [],
    }
    if len(out["reason"].split()) > 20:
        out["reason"] = " ".join(out["reason"].split()[:15])
    return out


def _empty_classification() -> Dict[str, Any]:
    row = _tier_row(3)
    return {
        "tier": 3,
        "type": str(row.get("type") or ""),
        "model": str(row.get("model") or ""),
        "confidence": 0.0,
        "reason": "Empty query; defaulting to troubleshooting-capable tier.",
        "keywords_matched": [],
    }


def _normalize_classifier_response(raw: Dict[str, Any], user_query: str) -> Dict[str, Any]:
    merged = {
        "tier": raw.get("tier"),
        "confidence": raw.get("confidence"),
        "reason": raw.get("reason"),
        "keywords_matched": raw.get("keywords_matched"),
    }
    return _apply_routing_rules(user_query, merged)


class QueryClassifierService:
    """Classifies user queries into tiers 1–4 for Directorist RAG model routing."""

    def __init__(self) -> None:
        self.client = AsyncGroq(api_key=settings.groq_api_key)
        self.model = settings.groq_query_classifier_model

    async def classify(self, user_query: str, *, use_cache: bool = True) -> Dict[str, Any]:
        """
        Classify a user query for downstream RAG/answer model selection.

        Returns:
            Dict with tier, type, model (from QUERY_TIER_MODELS), confidence, reason, keywords_matched.
        """
        if not user_query or not user_query.strip():
            return _empty_classification()

        q = user_query.strip()
        key = _cache_key(q)
        if use_cache:
            cached = _cache_get(key)
            if cached is not None:
                logger.debug("query_classifier cache hit")
                return cached

        user_prompt = QUERY_CLASSIFIER_USER.format(user_query=q)
        try:
            logger.info("query_classifier request (model=%s)", self.model)
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": QUERY_CLASSIFIER_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            logger.error("Groq query_classifier API error: %s", e)
            raise

        content = response.choices[0].message.content
        if not content or not content.strip():
            result = _empty_classification()
        else:
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error("Invalid JSON from query_classifier: %s", e)
                raise ValueError(f"Invalid JSON response from Groq: {e}") from e
            result = _normalize_classifier_response(data, q)

        if use_cache:
            _cache_set(key, dict(result))
        return result


query_classifier_service = QueryClassifierService()
