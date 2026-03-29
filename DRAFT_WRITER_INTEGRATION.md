# Draft Writer Integration Guide

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs the new packages:
- `anthropic==0.39.0` (Claude API)
- `google-generativeai==0.8.3` (Gemini API)
- `pinecone-client==5.0.1` (vector store)

### 2. Configure Environment

Add to your `.env` file:

```bash
# Required for basic functionality
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=directorist-docs
PINECONE_NAMESPACE=directorist-docs

# Optional: Tier 4 code generation
ANTHROPIC_API_KEY=sk-ant-...

# Optional: Tier 2/3 fallbacks
GEMINI_API_KEY=...

# Optional: Override classifier model
GROQ_QUERY_CLASSIFIER_MODEL=llama-3.2-3b-preview
```

### 3. Set Up Pinecone Index

Your Pinecone index must:
- Use dimension **1536** (matches OpenAI text-embedding-3-small)
- Contain chunks with metadata: `text`, `source`, `section`, `url`
- Use namespace `directorist-docs` (or override via `PINECONE_NAMESPACE`)

Example upsert:

```python
from pinecone import Pinecone

pc = Pinecone(api_key="...")
index = pc.Index("directorist-docs")

index.upsert(
    vectors=[
        {
            "id": "doc-1",
            "values": [0.1, 0.2, ...],  # 1536-dim embedding
            "metadata": {
                "text": "To install Directorist, go to Plugins > Add New...",
                "source": "Installation Guide",
                "section": "Getting Started",
                "url": "https://directorist.com/docs/install"
            }
        }
    ],
    namespace="directorist-docs"
)
```

### 4. Start the Server

```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Test the API

```bash
curl -X POST http://localhost:8000/draft/generate \
  -H "Content-Type: application/json" \
  -d '{
    "user_query": "How do I install Directorist?",
    "use_cache": false
  }'
```

---

## How It Works

### Pipeline

1. **Query Classification** (`query_classifier_service`)
   - Model: `llama-3.2-3b-preview` (Groq)
   - Output: tier (1–4), confidence, keywords
   - Enforces keyword rules: code words → tier 4, error words → tier 3
   - Bumps tier if confidence < 0.60

2. **Model Mapping** (`QUERY_TIER_MODELS`)
   - Maps tier → answer model
   - **Edit this array to change routing** (in `app/sub_agents/query_classifier.py`)

3. **Vector Retrieval** (`pinecone_service`)
   - Embeds query with OpenAI text-embedding-3-small
   - Searches Pinecone index
   - Returns top_k chunks (3 for tier 1, 10 for tier 4)
   - Filters by similarity ≥ 0.70

4. **Draft Generation** (`draft_writer_service`)
   - Selects model via `get_model(tier, model_slug)`
   - Applies tier-specific system prompt
   - Generates reply using retrieved chunks as context
   - Returns draft + metadata

### Caching

Both classifier and draft writer cache results by query hash:
- `query_classifier`: 256 entries
- `draft_writer`: 128 entries
- Set `use_cache=false` to bypass

---

## Customization

### Change Tier → Model Mapping

Edit `QUERY_TIER_MODELS` in `app/sub_agents/query_classifier.py`:

```python
QUERY_TIER_MODELS: List[Dict[str, Any]] = [
    {"tier": 1, "type": "Basic / Lookup", "model": "llama-3.1-8b"},
    {"tier": 2, "type": "Configuration/How-to", "model": "gpt-4o-mini"},  # Change this
    {"tier": 3, "type": "Troubleshooting / Multi-step Reasoning", "model": "gpt-4o"},  # Or this
    {"tier": 4, "type": "Custom Code / Development", "model": "claude-opus-4-5"},  # Or this
]
```

The model slug is passed to `model_router.get_model()`, which matches:
- `llama` or `mistral` → `llama_service` (Groq)
- `gpt` or `openai` → `openai_model_service`
- `claude` or `anthropic` → `claude_service`
- `gemini` or `google` → `gemini_service`

### Adjust Retrieval Parameters

In `app/services/pinecone_service.py`:

```python
TIER_TOP_K: Dict[int, int] = {
    1: 3,   # Fewer chunks for simple queries
    2: 5,
    3: 8,
    4: 10,  # More chunks for code generation
}
```

And `min_score` threshold (default 0.70) in the `search()` method.

### Tune System Prompts

Edit the `DRAFT_SYSTEM_TIER_*` constants in `app/sub_agents/draft_writer.py` to adjust:
- Tone (friendly, formal, technical)
- Structure (steps, bullets, code blocks)
- Word count ranges
- Formatting rules

---

## Programmatic Usage Example

```python
from app.sub_agents.draft_writer import draft_writer_service
from app.sub_agents.query_classifier import query_classifier_service

# Just classification
classification = await query_classifier_service.classify("How do I install Directorist?")
print(classification["tier"])  # 1
print(classification["model"])  # llama-3.1-8b

# Full draft generation
result = await draft_writer_service.generate_draft(
    user_query="Map not loading on mobile devices",
    use_cache=True,
)

print(f"Tier: {result['tier']}")  # 3
print(f"Model: {result['model']}")  # gpt-4.1-mini
print(f"Confidence: {result['confidence']}")  # 0.87
print(f"Chunks: {result['chunks_used']}")  # 8
print(f"\nDraft:\n{result['draft']}")
```

---

## File Structure

```
app/
├── sub_agents/
│   ├── draft_writer.py          (orchestrator)
│   ├── query_classifier.py      (routing logic + QUERY_TIER_MODELS)
│   └── DRAFT_WRITER_README.md
├── services/
│   ├── ai_models/
│   │   ├── __init__.py          (exports: get_model, embed_query)
│   │   ├── model_router.py      (tier/slug → service)
│   │   ├── llama_service.py     (Groq, Tier 1)
│   │   ├── openai_model_service.py  (Tier 2/3 + embeddings)
│   │   ├── claude_service.py    (Anthropic, Tier 4)
│   │   └── gemini_service.py    (Google, Tier 2/3 fallbacks)
│   ├── pinecone_service.py      (vector search)
│   ├── draft_writer_service.py  (re-export)
│   └── query_classifier_service.py  (re-export)
├── orchestrator/
│   ├── draft_writer.py          (API route: POST /draft/generate)
│   └── query_classifier.py      (API route: POST /query/classify)
├── schemas/
│   ├── draft_writer.py          (request/response models)
│   └── query_classifier.py      (request/response models)
└── main.py                      (router registration)

examples/
└── draft_writer_example.py      (demo script)

DRAFT_WRITER_IMPLEMENTATION.md   (this file)
```

---

## API Reference

### POST /draft/generate

Generate a RAG-based draft support reply.

**Request:**
```json
{
  "user_query": "string (required)",
  "use_cache": true
}
```

**Response:**
```json
{
  "draft": "Generated support reply text",
  "tier": 2,
  "model": "gpt-4o-mini",
  "confidence": 0.88,
  "chunks_used": 5,
  "classification": {
    "tier": 2,
    "type": "Configuration/How-to",
    "model": "gpt-4o-mini",
    "confidence": 0.88,
    "reason": "Multi-step extension setup requiring sequential configuration steps.",
    "keywords_matched": ["connect", "Stripe", "payments"]
  }
}
```

### POST /query/classify

Classify a query into a routing tier (internal use).

**Request:**
```json
{
  "user_query": "string (required)",
  "use_cache": true
}
```

**Response:**
```json
{
  "tier": 2,
  "type": "Configuration/How-to",
  "model": "gpt-4o-mini",
  "confidence": 0.88,
  "reason": "Multi-step extension setup.",
  "keywords_matched": ["connect", "Stripe"]
}
```

---

## Troubleshooting

### "OPENAI_API_KEY is required for embeddings"

Pinecone retrieval requires OpenAI embeddings. Make sure `OPENAI_API_KEY` is set in `.env`.

### "PINECONE_API_KEY is required"

Set `PINECONE_API_KEY` in `.env` and ensure your index exists.

### "ANTHROPIC_API_KEY is required for Claude service"

This only happens for Tier 4 queries. If you don't have an Anthropic key:
- Change tier 4 model in `QUERY_TIER_MODELS` to `gpt-4.1` or `gpt-4o`
- Or set a dummy key and handle the exception

### Retrieval returns 0 chunks

1. Verify your Pinecone index has data in the correct namespace
2. Check embedding dimension matches (1536 for text-embedding-3-small)
3. Lower `min_score` threshold in `pinecone_service.search()` if needed

### Classification confidence always < 0.60

The classifier may need more examples or a different model. Try:
- Set `GROQ_QUERY_CLASSIFIER_MODEL=llama-3.1-8b-instant` (more capable)
- Or disable the confidence bump in `_apply_routing_rules()` in `query_classifier.py`

---

## Production Checklist

- [ ] Install all dependencies from `requirements.txt`
- [ ] Set all required API keys in `.env`
- [ ] Create and populate Pinecone index with Directorist docs
- [ ] Test all 4 tiers with sample queries
- [ ] Verify chunk retrieval quality (adjust `min_score` if needed)
- [ ] Review and customize system prompts for your brand voice
- [ ] Set appropriate `GROQ_QUERY_CLASSIFIER_MODEL` if preview model fails
- [ ] Monitor cache hit rates and adjust `_CACHE_MAX` if needed
- [ ] Set up error monitoring for model API failures
- [ ] Consider rate limiting on `/draft/generate` endpoint

---

## Cost Optimization

- **Tier 1** (llama-3.1-8b via Groq): ~$0.0001/query
- **Tier 2** (gpt-4o-mini): ~$0.001/query
- **Tier 3** (gpt-4.1-mini): ~$0.003/query
- **Tier 4** (claude-sonnet-4-5): ~$0.015/query
- **Embeddings** (text-embedding-3-small): ~$0.00002/query

Cache hit rates of 40–60% can reduce costs significantly. Monitor `chunks_used` and adjust `top_k` if models receive too much context.
