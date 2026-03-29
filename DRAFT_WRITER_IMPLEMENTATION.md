# Draft Writer Implementation Summary

## Overview

Complete RAG-based draft reply system for Directorist WordPress plugin support queries. Classifies queries into 4 tiers, retrieves relevant documentation from Pinecone, and generates professional support replies using the appropriate AI model.

---

## Files Created

### Core Sub-Agent
- **`app/sub_agents/draft_writer.py`** (327 lines)
  - Main orchestration: classify → retrieve → generate
  - LRU cache (128 entries) by query hash
  - Tier-specific system prompts and generation parameters
  - Fallback handling for all failure modes

### AI Model Services
- **`app/services/ai_models/__init__.py`** — Package exports: `get_model()`, `embed_query()`
- **`app/services/ai_models/model_router.py`** — Maps tier/model-slug to service instance
- **`app/services/ai_models/llama_service.py`** — Tier 1: Groq llama-3.1-8b-instant
- **`app/services/ai_models/openai_model_service.py`** — Tier 2/3: gpt-4o-mini, gpt-4.1-mini + embeddings
- **`app/services/ai_models/claude_service.py`** — Tier 4: claude-sonnet-4-5
- **`app/services/ai_models/gemini_service.py`** — Tier 2/3 fallbacks: gemini-1.5-flash, gemini-1.5-pro

### Pinecone Service
- **`app/services/pinecone_service.py`** (118 lines)
  - Embeds query via OpenAI text-embedding-3-small
  - Tier-based top_k: 3 (tier 1) → 10 (tier 4)
  - Filters by min_score=0.70
  - Returns chunks with: id, score, text, source, section, url

### API & Schemas
- **`app/orchestrator/draft_writer.py`** — FastAPI route: `POST /draft/generate`
- **`app/schemas/draft_writer.py`** — Request/response schemas
- **`app/services/draft_writer_service.py`** — Re-export for backward compatibility

### Configuration & Documentation
- **`app/config.py`** — Added: `anthropic_api_key`, `gemini_api_key`, `pinecone_api_key`, `pinecone_index_name`, `pinecone_namespace`, `groq_query_classifier_model`
- **`.env.example`** — Updated with all new keys
- **`requirements.txt`** — Added: anthropic, google-generativeai, pinecone-client
- **`app/sub_agents/DRAFT_WRITER_README.md`** — Complete usage documentation
- **`examples/draft_writer_example.py`** — Programmatic usage example

### Integration
- **`app/main.py`** — Router registered: `app.include_router(draft_writer_routes.router)`
- **`app/sub_agents/__init__.py`** — Updated docstring

---

## Model Routing Configuration

Edit **`QUERY_TIER_MODELS`** in `app/sub_agents/query_classifier.py` to change tier → model mappings:

```python
QUERY_TIER_MODELS: List[Dict[str, Any]] = [
    {"tier": 1, "type": "Basic / Lookup", "model": "llama-3.1-8b"},
    {"tier": 2, "type": "Configuration/How-to", "model": "gpt-4o-mini"},
    {"tier": 3, "type": "Troubleshooting / Multi-step Reasoning", "model": "gpt-4.1-mini"},
    {"tier": 4, "type": "Custom Code / Development", "model": "claude-sonnet-4-5"},
]
```

The classifier LLM **only** chooses the tier number. `type` and `model` are resolved server-side from this array.

---

## API Usage

### Endpoint

```http
POST http://localhost:8000/draft/generate
Content-Type: application/json

{
  "user_query": "How do I add custom fields to listings?",
  "use_cache": true
}
```

### Response

```json
{
  "draft": "Hi there! To add custom fields to your Directorist listings:\n\n1. Navigate to...",
  "tier": 2,
  "model": "gpt-4o-mini",
  "confidence": 0.88,
  "chunks_used": 5,
  "classification": {
    "tier": 2,
    "type": "Configuration/How-to",
    "model": "gpt-4o-mini",
    "confidence": 0.88,
    "reason": "Multi-step custom field configuration.",
    "keywords_matched": ["add", "custom fields", "listings"]
  }
}
```

---

## Programmatic Usage

```python
from app.sub_agents.draft_writer import draft_writer_service

result = await draft_writer_service.generate_draft(
    user_query="Does Directorist support WooCommerce?",
    use_cache=True,
)

print(f"Generated draft ({result['tier']}, {result['model']}):")
print(result['draft'])
```

---

## Environment Variables (Required)

```bash
# Existing (already in your .env)
GROQ_API_KEY=gsk_...
OPENAI_API_KEY=sk-...

# New (add these)
ANTHROPIC_API_KEY=sk-ant-...          # For Tier 4 (optional)
GEMINI_API_KEY=...                    # For Tier 2/3 fallbacks (optional)
PINECONE_API_KEY=...                  # Required for retrieval
PINECONE_INDEX_NAME=directorist-docs  # Required
PINECONE_NAMESPACE=directorist-docs   # Optional (default)
GROQ_QUERY_CLASSIFIER_MODEL=llama-3.2-3b-preview  # Optional override
```

---

## Installation

```bash
pip install -r requirements.txt
```

New dependencies:
- `anthropic==0.39.0`
- `google-generativeai==0.8.3`
- `pinecone-client==5.0.1`

---

## Architecture

```
User Query
    ↓
query_classifier (Groq llama-3.2-3b-preview)
    ↓
tier + model recommendation
    ↓
Pinecone (embed with OpenAI → vector search → filter by score ≥ 0.70)
    ↓
chunks + tier
    ↓
model_router (tier → llama | openai | claude | gemini)
    ↓
AI model (system prompt + user query + chunks)
    ↓
Draft Reply
```

---

## Tier System

| Tier | Type | Covers | Model | top_k |
|------|------|--------|-------|-------|
| 1 | Basic / Lookup | Installation, definitions, feature existence | llama-3.1-8b | 3 |
| 2 | Configuration/How-to | Multi-step setup, extensions, monetisation | gpt-4o-mini | 5 |
| 3 | Troubleshooting | Debugging, conflicts, performance | gpt-4.1-mini | 8 |
| 4 | Custom Code | PHP hooks, templates, REST API, dev | claude-sonnet-4-5 | 10 |

---

## Classification Rules (Enforced Server-Side)

1. **When in doubt, go higher** — between tiers, always choose the more capable one
2. **Low confidence (<0.60) → bump tier +1** — automatic safety net
3. **Code keywords → Tier 4 minimum** — write, build, hook, filter, template, PHP, endpoint, REST, API
4. **Error keywords → Tier 3 minimum** — not working, broken, error, conflict, slow, missing, fails, 404

---

## System Prompt Strategy

Each tier has a dedicated system prompt in `draft_writer.py`:

- **Tier 1** — Concise (80–150 words), direct answer
- **Tier 2** — Detailed (150–250 words), numbered steps
- **Tier 3** — Diagnostic (200–300 words), possible causes + resolution
- **Tier 4** — Technical (200–400 words), code examples with comments

All prompts enforce:
- Use **only** documentation context (never fabricate)
- Structure: greeting → solution → offer further help
- Include doc URLs when available in chunks
- Never expose internals (tier, model, Pinecone scores)

---

## Caching

- **Query classifier cache**: 256 entries (SHA-256 key)
- **Draft writer cache**: 128 entries (SHA-256 key)
- Both bypass-able with `use_cache=false`

---

## Error Handling

All services implement graceful fallbacks:

1. **Classifier fails** → Default to tier 3 with gpt-4.1-mini
2. **Pinecone fails or returns 0 chunks** → Return safe fallback message
3. **Model generation fails** → Return safe fallback message
4. **Empty or malformed output** → Return safe fallback message

Fallback message:
```
Thank you for reaching out. I'd be happy to help, but I need a bit more detail to provide an accurate answer. Could you please clarify your question or let me know which specific Directorist feature you're working with?

If this is urgent, feel free to contact our support team directly and we'll assist you right away.
```

---

## Testing

Run the example:

```bash
python3 examples/draft_writer_example.py
```

Or use the API:

```bash
curl -X POST http://localhost:8000/draft/generate \
  -H "Content-Type: application/json" \
  -d '{"user_query": "How do I install Directorist?", "use_cache": false}'
```

---

## Next Steps

1. **Set up Pinecone index** with your Directorist documentation:
   - Create index with dimension 1536 (for text-embedding-3-small)
   - Upsert chunks with metadata: text, source, section, url
   - Use namespace `directorist-docs`

2. **Add API keys** to `.env`:
   - `PINECONE_API_KEY` (required)
   - `ANTHROPIC_API_KEY` (optional, for Tier 4)
   - `GEMINI_API_KEY` (optional, for fallbacks)

3. **Test with real queries** to verify retrieval quality and adjust:
   - `min_score` threshold in `pinecone_service.py` (default 0.70)
   - `top_k` values in `TIER_TOP_K` dict
   - Model slugs in `QUERY_TIER_MODELS`

---

## Implementation Notes

- All model services are **lazy-init** — they only raise errors when called, not at import time
- OpenAI service is shared for embeddings, Tier 2, and Tier 3
- Groq service (existing) handles Tier 1 via `llama_service.py`
- Claude/Gemini services are isolated and only loaded when needed
- The `model` field in responses is always resolved from `QUERY_TIER_MODELS`, never from the LLM output
