# 🐍 Python Programming Q&A Assistant

An AI-powered question-answering system for data science learners, grounded in the
**Stack Overflow Python Q&A dataset**. Ask any Python question and get an accurate,
cited answer — backed by real, high-scoring Stack Overflow answers, never hallucinated.

Built for the Analytics Vidhya AI Engineer assessment (Round 1).

> **Live demo:** _<!-- add deployed URL here -->_

## What it does

- **RAG pipeline** (LangChain) — retrieves the most relevant Stack Overflow Q&A pairs
  from a Chroma vector index of ~25,000 top-scoring Python questions, then generates a
  grounded answer with **Gemini 2.0 Flash**, citing sources as `[1]`, `[2]`.
- **FastAPI backend** — `POST /ask` and `GET /health`, fully async, OpenAPI docs at `/docs`.
- **Next.js + TypeScript frontend** — chat UI with markdown rendering, syntax-highlighted
  code blocks, expandable source citations linking back to Stack Overflow, and a live
  API-health badge.
- **Honest refusals** — if retrieval finds nothing relevant (e.g. a non-Python question),
  the API returns `grounded: false` with a polite refusal instead of a hallucination.

## Architecture

```
                        ┌──────────────────────────────────────────┐
                        │           OFFLINE INGESTION              │
  Kaggle dataset ──────►│ filter score ≥5 ► pair best answer       │
  (607k Q / 987k A)     │ ► clean HTML (keep code) ► top 25k docs  │
                        │ ► embed (text-embedding-004, batched)    │
                        └───────────────────┬──────────────────────┘
                                            ▼
┌──────────────┐   POST /ask   ┌─────────────────────┐    ┌─────────────────┐
│   Next.js    │──────────────►│      FastAPI        │───►│  ChromaDB       │
│  chat UI     │◄──────────────│  retrieve top-5     │◄───│  (cosine, 25k)  │
│  (Vercel)    │   answer +    │  ► relevance gate   │    └─────────────────┘
└──────────────┘   sources     │  ► grounded prompt  │    ┌─────────────────┐
                               │  ► cite sources     │───►│ Gemini 2.0 Flash│
                               └─────────────────────┘    └─────────────────┘
```

Details in [`docs/architecture.md`](docs/architecture.md). Design decisions and the
100+ concurrent-user scaling plan are in the slide deck: [`docs/slides.md`](docs/slides.md).

## Quickstart

### Prerequisites

- Python 3.11+ (3.13 recommended), Node 20+
- A [Google AI Studio API key](https://aistudio.google.com/apikey) (free tier works)
- Kaggle credentials for the dataset download (or download the CSVs manually)

### 1. Backend setup

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp ../.env.example .env          # then fill in GOOGLE_API_KEY
```

### 2. Build the knowledge base (one-time, ~30–45 min)

```bash
# Download the Kaggle dataset (~2 GB) — needs ~/.kaggle/kaggle.json
python scripts/download_data.py

# Filter → clean → embed ~25k top Q&A pairs into ./chroma_db
python scripts/ingest.py

# Quick smoke-test index instead (500 docs, ~2 min):
python scripts/ingest.py --max-docs 500
```

The ingestion is **resumable** — if it is interrupted (rate limits, network), re-running
it skips everything already embedded.

### 3. Run the API

```bash
uvicorn app.main:app --port 8000 --reload
```

- Interactive docs: http://localhost:8000/docs
- Health check: `curl localhost:8000/health`

### 4. Run the frontend

```bash
cd ../frontend
npm install
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
npm run dev          # http://localhost:3000
```

## API reference

### `POST /ask`

```bash
curl -X POST localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question": "How do I merge two dictionaries in Python?"}'
```

```json
{
  "answer": "You can merge two dictionaries with the `|` operator… [1]",
  "sources": [
    {
      "title": "How do I merge two dictionaries in a single expression?",
      "link": "https://stackoverflow.com/questions/38987",
      "question_score": 6543,
      "answer_score": 5821,
      "snippet": "# How do I merge two dictionaries…"
    }
  ],
  "grounded": true,
  "latency_ms": 1843,
  "model": "gemini-2.0-flash"
}
```

| Field | Meaning |
|---|---|
| `grounded` | `false` when nothing relevant was retrieved and the assistant declined to answer |
| `sources` | Stack Overflow posts used as context, with scores and links |
| Errors | `422` invalid input · `502` LLM failure · `503` pipeline not initialised |

### `GET /health`

```json
{
  "status": "ok",
  "vector_db": { "connected": true, "document_count": 25000 },
  "model": "gemini-2.0-flash",
  "timestamp": "2026-06-11T12:00:00Z"
}
```

## Testing

```bash
# Unit tests — run fully offline (LLM + embeddings mocked), 16 tests
cd backend && .venv/bin/python -m pytest -v

# Integration test suite — 12 diverse queries against a running API,
# writes docs/test_results.md with answers, sources, latency, observations
python scripts/run_test_queries.py --base-url http://localhost:8000
```

Documented results: [`docs/test_results.md`](docs/test_results.md). Coverage includes
basics, debugging/error-message queries, pandas questions, out-of-scope refusal,
vague one-word queries, and a harmful-request probe.

## Key design decisions

| Decision | Why |
|---|---|
| Top ~25k Q&A pairs (question score ≥ 5, answer score ≥ 2) | Quality over volume: high-score pairs cover the overwhelming majority of real learner questions; keeps embedding cost ~$0 (free tier) and the index small enough for free-tier hosting |
| One Q&A pair = one chunk | Q&A pairs are natural retrieval units; splitting mid-answer destroys the code context |
| HTML → markdown preserving `<code>` as fenced blocks | Code is the core signal in programming Q&A; naive HTML stripping mangles it |
| Cosine-distance relevance gate (no extra LLM call) | Out-of-scope detection for free — one threshold, zero added latency |
| Role of the LLM is *synthesis only* | The system prompt forbids answering beyond the retrieved context — grounding is enforced, not requested |
| Lifespan-loaded pipeline, never crashes the app | `/health` stays up and reports degraded state even if the LLM/key is misconfigured |

## Deployment

**Backend → Render** (free tier): `render.yaml` blueprint included.

1. Push the repo, create a Render Blueprint from it.
2. Set `GOOGLE_API_KEY` in the dashboard.
3. Build the index onto the persistent disk: open a Render shell and run
   `python scripts/download_data.py && python scripts/ingest.py`
   (or upload a locally built `chroma_db/` to the disk).

**Frontend → Vercel:** import `frontend/`, set `NEXT_PUBLIC_API_URL` to the Render URL,
and add the Vercel domain to `CORS_ORIGINS` on the backend.

**Docker (local):**

```bash
docker compose up --build    # serves the API with your local chroma_db mounted
```

## Troubleshooting

### Common Issues & Solutions

#### 1. **404 NOT_FOUND - Embedding Model Errors**

**Error:**
```
models/text-embedding-004 is not found for API version v1beta
```

**Root Cause:** Using outdated embedding model names that don't exist in current Google GenAI SDK.

**Solution:**
Update your `.env` and `app/core/config.py`:

```bash
# .env
EMBEDDING_MODEL=models/gemini-embedding-001

# app/core/config.py
embedding_model: str = "models/gemini-embedding-001"
```

**Available Embedding Models (2025):**
- `models/gemini-embedding-001` (recommended for text)
- `models/gemini-embedding-2-preview` (latest multimodal)
- `models/gemini-embedding-2` (stable multimodal)

#### 2. **404 NOT_FOUND - Generation Model Errors**

**Error:**
```
models/gemini-2.0-pro is not found for API version v1beta
```

**Solution:**
Update to available generation models:

```bash
# .env
GENERATION_MODEL=gemini-2.5-flash

# app/core/config.py
generation_model: str = "gemini-2.5-flash"
```

**Available Generation Models:**
- `gemini-2.5-flash` (recommended - fast & cost-effective)
- `gemini-2.5-pro` (higher quality, slower)
- `gemini-3.5-flash` (latest)

#### 3. **429 RESOURCE_EXHAUSTED - Quota Issues**

**Error:**
```
You exceeded your current quota, please check your plan and billing details
```

**Solutions:**
1. **Wait for quota reset** (daily limits reset at midnight UTC)
2. **Check usage:** https://ai.dev/rate-limit
3. **Use different API key** with available quota
4. **Create minimal test data** (for development):

```python
# Create test collection with sample data
import chromadb
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

test_data = [
    'How do I merge two dictionaries in Python? Use dict1.update(dict2) or {**dict1, **dict2}',
    'What is list comprehension? It is [expr for item in iterable]',
    'How to handle exceptions? Use try-except blocks'
]

# Add to vector database for testing
```

#### 4. **Package Compatibility Issues**

**Error:**
```
Collection [uuid] does not exist
```

**Solution:**
Restart your server to pick up database changes:
```bash
# Stop server (Ctrl+C)
uvicorn app.main:app --reload
```

**For clean restart:**
```bash
# Remove old database and recreate
rm -rf chroma_db
python scripts/ingest.py
```

#### 5. **"I couldn't find anything relevant" Responses**

**Symptoms:**
API always returns generic fallback message instead of real answers.

**Root Causes & Solutions:**

1. **Empty Vector Database:**
   ```bash
   # Check database status
   curl localhost:8000/health
   # Should show: "document_count": > 0

   # If 0, rebuild database
   python scripts/download_data.py
   python scripts/ingest.py
   ```

2. **Quota Exhaustion During Ingestion:**
   - Check logs for 429 errors
   - Use test data (see quota section above)
   - Wait for quota reset

3. **Server Cache Issues:**
   - Restart server after database changes
   - Clear browser cache

#### 6. **SDK Version Conflicts**

**Check Current Versions:**
```bash
pip list | grep -E "(google|genai|langchain)"
```

**Expected Versions (Working Configuration):**
```
google-genai                  2.8.0+
langchain-google-genai        4.2.5+
langchain-core                1.4.7+
```

**If Conflicts Exist:**
```bash
# Clean installation
pip uninstall google-generativeai google-ai-generativelanguage  # Remove old SDKs
pip install -r requirements.txt --upgrade
```

### Quick Diagnostic Commands

```bash
# 1. Test API connectivity
curl localhost:8000/health

# 2. Check available models
python -c "
import google.genai as genai
client = genai.Client(api_key='YOUR_API_KEY')
models = client.models.list()
for model in models:
    if 'gemini' in model.name.lower():
        print(model.name)
"

# 3. Test embedding functionality
python -c "
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import get_settings
settings = get_settings()
embeddings = GoogleGenerativeAIEmbeddings(model=settings.embedding_model, google_api_key=settings.google_api_key)
result = embeddings.embed_query('test')
print(f'Success! Vector length: {len(result)}')
"

# 4. Test vector database
python -c "
from app.rag.vectorstore import get_vectorstore
vs = get_vectorstore()
results = vs.similarity_search('test', k=1)
print(f'Database has {len(results)} results')
"
```

### Working Test Questions (with minimal dataset)

After creating test data, these questions will work:

```bash
# Dictionary operations
curl -X POST localhost:8000/ask -H "Content-Type: application/json" \
  -d '{"question": "How do I merge two dictionaries in Python?"}'

# List comprehensions
curl -X POST localhost:8000/ask -H "Content-Type: application/json" \
  -d '{"question": "What is list comprehension?"}'

# Exception handling
curl -X POST localhost:8000/ask -H "Content-Type: application/json" \
  -d '{"question": "How to handle exceptions in Python?"}'
```

### Configuration Reference

**Working .env Configuration:**
```bash
# Google AI Studio API key
GOOGLE_API_KEY=your_api_key_here

# Models (verified working as of 2025)
GENERATION_MODEL=gemini-2.5-flash
EMBEDDING_MODEL=models/gemini-embedding-001

# Database settings
CHROMA_DIR=./chroma_db
CHROMA_COLLECTION=python_qa

# API settings
CORS_ORIGINS=http://localhost:3000
RETRIEVAL_K=5
MAX_RELEVANCE_DISTANCE=0.60
```

---

## Project structure

```
backend/
  app/
    main.py            FastAPI app factory + lifespan pipeline init
    api/               routes (ask, health) + Pydantic schemas
    rag/               embeddings, vectorstore, retriever, grounded chain
    core/config.py     pydantic-settings configuration
  scripts/
    download_data.py   Kaggle dataset fetch
    ingest.py          filter → clean → embed pipeline (resumable)
    run_test_queries.py integration test runner → docs/test_results.md
  tests/               offline unit tests (16)
frontend/              Next.js 16 + TypeScript + Tailwind chat UI
docs/                  architecture, slides, test results
```

---

*Submitted for the Analytics Vidhya AI Engineer assessment. Per the assessment NDA,
keep this repository private until the hiring process concludes.*
