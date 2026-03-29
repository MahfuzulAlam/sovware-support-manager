# Draft Writer Sub-Agent

The `draft_writer` sub-agent orchestrates a full RAG (Retrieval-Augmented Generation) pipeline for Directorist WordPress plugin support queries.

## Pipeline

1. **Query Classification** — classify the user query into tier 1–4 using `query_classifier`
2. **Vector Retrieval** — fetch relevant documentation chunks from Pinecone
3. **Model Selection** — route to the appropriate AI model based on tier
4. **Draft Generation** — generate a professional support reply

## Tier Routing

Tier routing is controlled by `QUERY_TIER_MODELS` in `app/sub_agents/query_classifier.py`:

```python
QUERY_TIER_MODELS: List[Dict[str, Any]] = [
    {"tier": 1, "type": "Basic / Lookup", "model": "llama-3.1-8b"},
    {"tier": 2, "type": "Configuration/How-to", "model": "gpt-4o-mini"},
    {"tier": 3, "type": "Troubleshooting / Multi-step Reasoning", "model": "gpt-4.1-mini"},
    {"tier": 4, "type": "Custom Code / Development", "model": "claude-sonnet-4-5"},
]
```

**To change which model is used for a tier**, edit this array. The LLM classifier only chooses the tier number; `type` and `model` are always resolved from this list.

## Environment Setup

Add to your `.env`:

```bash
# Existing keys
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...

# New for draft_writer
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=directorist-docs
PINECONE_NAMESPACE=directorist-docs
GROQ_QUERY_CLASSIFIER_MODEL=llama-3.2-3b-preview
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

New packages:
- `anthropic==0.39.0` — Claude API
- `google-generativeai==0.8.3` — Gemini API
- `pinecone-client==5.0.1` — Vector store

## API Endpoint

```http
POST /draft/generate
Content-Type: application/json

{
  "user_query": "How do I connect Stripe payments to Directorist?",
  "use_cache": true
}
```

Response:

```json
{
  "draft": "Hi there! To connect Stripe...",
  "tier": 2,
  "model": "gpt-4o-mini",
  "confidence": 0.92,
  "chunks_used": 5,
  "classification": {
    "tier": 2,
    "type": "Configuration/How-to",
    "model": "gpt-4o-mini",
    "confidence": 0.92,
    "reason": "Multi-step extension setup requiring sequential configuration steps.",
    "keywords_matched": ["connect", "Stripe", "payments"]
  }
}
```

## Programmatic Usage

```python
from app.sub_agents.draft_writer import draft_writer_service

result = await draft_writer_service.generate_draft(
    user_query="How do I install Directorist?",
    use_cache=True,
)

print(result["draft"])
# => "Hi there! To install Directorist..."
```

## Model Services

All model services are in `app/services/ai_models/`:

- **`llama_service.py`** — Tier 1 (Groq llama-3.1-8b-instant)
- **`openai_model_service.py`** — Tier 2/3 (gpt-4o-mini, gpt-4.1-mini) + embeddings
- **`claude_service.py`** — Tier 4 (claude-sonnet-4-5)
- **`gemini_service.py`** — Tier 2/3 fallbacks (gemini-1.5-flash, gemini-1.5-pro)
- **`model_router.py`** — `get_model(tier, slug)` router + `embed_query(text)`

## Pinecone Service

`app/services/pinecone_service.py` handles vector search:

- Embeds the query using OpenAI `text-embedding-3-small`
- Queries Pinecone with tier-based `top_k` (tier 1 → 3 chunks, tier 4 → 10 chunks)
- Filters results by min similarity score (default 0.70)
- Returns chunks with: `id`, `score`, `text`, `source`, `section`, `url`

## System Prompts

Four system prompts (one per tier) in `draft_writer.py`:

- **Tier 1** — concise, 80–150 words, direct answer
- **Tier 2** — detailed steps, 150–250 words, numbered/bulleted
- **Tier 3** — troubleshooting reasoning, 200–300 words, list possible causes
- **Tier 4** — technical code examples, 200–400 words, markdown code blocks

All prompts enforce:
- Use **only** documentation context (never fabricate)
- Structure: greeting → solution → offer further help
- Include doc URLs when available
- Never expose internal metadata (tier, model name, Pinecone scores)

## Caching

Both `query_classifier` and `draft_writer` use in-memory LRU caches (256 and 128 entries). Cache key is SHA-256 of the trimmed query. Set `use_cache=false` in the API request to bypass.

## Fallback Behavior

If classification, retrieval, or generation fails, the system returns a safe fallback message asking the user to clarify or contact support directly. The draft is never an empty string.
