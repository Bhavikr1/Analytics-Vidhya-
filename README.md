# Python Programming Q&A Assistant

An AI-powered question-answering system for Python developers, grounded in a curated corpus of 25,000 high-scoring Stack Overflow Q&A pairs. Ask any Python question and get a streamed, cited answer — with full session memory and a hybrid retrieval pipeline for accuracy.

Built for the **Analytics Vidhya AI Engineer Assessment**.

> **Live demo:** _Add your deployed URL here_

---

## What it does

- **Hybrid RAG pipeline** — combines dense semantic search (ChromaDB + Gemini embeddings) with sparse keyword search (MongoDB full-text) and fuses results via Reciprocal Rank Fusion for higher retrieval accuracy than either method alone
- **MMR diversity** — Maximal Marginal Relevance selects a diverse set of Stack Overflow references so the LLM synthesises from multiple angles, not near-duplicate results
- **Real-time streaming** — answers stream token-by-token via Server-Sent Events; the first token arrives in under a second
- **Session memory** — conversation history is persisted to MongoDB and injected into every LLM call so follow-up questions work naturally within a session
- **Grounded fallback** — when retrieval finds nothing relevant, the LLM answers from its own Python expertise and the response is clearly marked as "General Knowledge" rather than returning a robotic refusal
- **JWT authentication** — protected routes with stateless token verification; no server-side session state
- **Production-grade security** — HSTS, CSP headers, CORS lockdown, Swagger blocked in production

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ONE-TIME DATA PIPELINE (run locally)                                   │
│                                                                         │
│  Kaggle CSV (607k Q / 987k A)                                           │
│    → filter (score ≥ 5) → clean HTML → top 25k Q&A pairs               │
│    → python scripts/ingest_to_mongodb.py                                │
│    → MongoDB Atlas  knowledge_base  collection (25k docs)               │
└─────────────────────────────────────────────────────────────────────────┘

                           Cold start
                     MongoDB ──────────────► ChromaDB
                    (25k docs)   rebuild      (vector index)
                                 (background
                                  async task)

┌──────────────┐  SSE stream   ┌──────────────────────────────────────────┐
│  Next.js 15  │◄─────────────►│  FastAPI  (Railway · Docker)             │
│  (Vercel)    │  JWT auth     │                                          │
│              │               │  POST /sessions/{id}/ask                 │
│  - Sidebar   │               │    1. Fetch session history (MongoDB)    │
│  - Streaming │               │    2. Dense retrieval:                   │
│  - Markdown  │               │       embed query → ChromaDB cosine      │
│  - Sources   │               │       → threshold filter                 │
└──────────────┘               │       → MMR diverse selection            │
                               │    3. Sparse retrieval:                  │
                               │       MongoDB $text search (BM25-like)   │
                               │    4. Reciprocal Rank Fusion             │
                               │    5. LLM: Gemini 2.5 Flash (streaming)  │
                               │    6. Save message to MongoDB            │
                               │                                          │
                               │  MongoDB Atlas                           │
                               │    - sessions + messages (chat history)  │
                               │    - knowledge_base (25k docs)           │
                               └──────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| LLM | Gemini 2.5 Flash | Fast streaming, low latency, strong Python reasoning |
| Embeddings | Gemini Embedding-001 (768-dim) | Same provider, no extra API key |
| Vector DB | ChromaDB (cosine) | Lightweight, runs in container, persists to Railway Volume |
| Document DB | MongoDB Atlas (Motor async) | Persistent knowledge base + chat history; built-in text search for sparse leg |
| RAG framework | LangChain Core | Chain composition, prompt templates, message history types |
| Backend | FastAPI + Uvicorn | Native async, SSE streaming, automatic OpenAPI schema |
| Frontend | Next.js 15 + TypeScript | App Router, streaming-friendly, Vercel deploy |
| Styling | Tailwind CSS | Utility-first, dark theme |
| Auth | JWT (python-jose) | Stateless — any backend instance handles any request |
| Hosting | Railway (backend) · Vercel (frontend) | Docker image deploy; Railway Volume for ChromaDB persistence |

---

## Retrieval Pipeline Detail

```
Question
   │
   ├── Dense leg ──────────────────────────────────────────────────────┐
   │   Gemini embed → ChromaDB cosine search (fetch 4k candidates)    │
   │   → threshold filter (similarity ≥ 0.35)                         │
   │   → MMR selection (λ=0.6, k=8 diverse docs)                      │
   │                                                                   ▼
   │                                              Reciprocal Rank Fusion
   │                                              (RRF, k_const=60)
   │                                                                   ▲
   └── Sparse leg ─────────────────────────────────────────────────────┘
       MongoDB $text search → textScore ranking → top-8 keyword matches

                  └── Top-k fused results → LLM context
```

**Why hybrid?** Vector search catches semantic meaning but misses exact terms (function names, error types). Keyword search catches exact terms but misses paraphrased questions. RRF fusion ranks documents that appear highly in both lists significantly higher — giving the best of both approaches.

---

## File Structure

```
python-qa-assistant/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py           Login endpoint, JWT token issue
│   │   │   ├── routes.py         Health check, non-streaming ask
│   │   │   ├── sessions.py       Session CRUD + streaming SSE ask endpoint
│   │   │   └── schemas.py        Pydantic request/response models
│   │   ├── core/
│   │   │   ├── config.py         All settings from .env (zero hardcoded values)
│   │   │   └── auth.py           JWT verification dependency
│   │   ├── db/
│   │   │   └── mongodb.py        Async Motor connection manager
│   │   ├── rag/
│   │   │   ├── chain.py          RAGPipeline — grounded chain + fallback chain
│   │   │   ├── retriever.py      Hybrid retrieval (dense MMR + sparse + RRF)
│   │   │   ├── vectorstore.py    ChromaDB client
│   │   │   ├── embeddings.py     Gemini embedding function
│   │   │   └── indexer.py        MongoDB → ChromaDB rebuild + text index setup
│   │   └── main.py               App factory, security middleware, lifespan
│   ├── scripts/
│   │   └── ingest_to_mongodb.py  One-time corpus upload to MongoDB
│   ├── Dockerfile
│   ├── railway.toml
│   └── requirements.txt
│
└── frontend/
    ├── app/
    │   ├── page.tsx              Main layout — sidebar + chat window
    │   └── login/page.tsx        Login page (split-screen)
    ├── components/
    │   ├── ChatWindow.tsx        SSE streaming handler, message state
    │   ├── Sidebar.tsx           Session list — grouped by date, rename/delete
    │   ├── MessageBubble.tsx     Markdown, syntax highlight, source citations, metadata bar
    │   └── SourceList.tsx        Expandable Stack Overflow source links
    └── lib/
        ├── api.ts                All API calls + streamAsk async generator
        └── auth.ts               JWT storage, expiry check, logout
```

---

## Local Setup

### Prerequisites

- Python 3.11+ · Node 20+
- [Google AI Studio API key](https://aistudio.google.com/apikey) (free tier works)
- MongoDB Atlas cluster (free M0 tier works)

### 1. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in the values below
```

**`backend/.env` values required:**

```env
ENVIRONMENT=development

GOOGLE_API_KEY=your_key_here
GENERATION_MODEL=gemini-2.5-flash
EMBEDDING_MODEL=models/gemini-embedding-001

CHROMA_DIR=./chroma_db
CHROMA_COLLECTION=python_qa

RETRIEVAL_K=8
MAX_RELEVANCE_DISTANCE=0.65
RETRIEVAL_MMR_LAMBDA=0.6

CORS_ORIGINS=http://localhost:3000

MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGODB_DB_NAME=your_db_name

AUTH_USERNAME=your_username
AUTH_PASSWORD=your_password
JWT_SECRET_KEY=change-this-to-a-long-random-string
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### 2. Build the knowledge base (one-time)

```bash
# Download Kaggle dataset and process it into corpus.parquet first
python scripts/ingest.py --corpus-only   # if not already done

# Upload to MongoDB (takes ~2 min for 25k docs)
python scripts/ingest_to_mongodb.py

# Optional: smaller subset for testing
python scripts/ingest_to_mongodb.py --max-docs 1000
```

ChromaDB is **not** built locally — it rebuilds automatically from MongoDB when the backend starts. On first run this takes 10-15 minutes in the background; the app serves requests the whole time.

### 3. Run the backend

```bash
uvicorn app.main:app --port 8000 --reload
```

Swagger UI (development only): http://localhost:8000/docs

### 4. Run the frontend

```bash
cd frontend
npm install
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
npm run dev   # http://localhost:3000
```

---

## API Reference

All endpoints except `/health` require `Authorization: Bearer <token>`.

### `POST /auth/login-json`

```bash
curl -X POST localhost:8000/auth/login-json \
  -H 'Content-Type: application/json' \
  -d '{"username": "your_user", "password": "your_pass"}'
```

```json
{ "access_token": "eyJ...", "token_type": "bearer", "expires_in": 3600 }
```

### `POST /sessions/{id}/ask` — streaming

```bash
curl -X POST localhost:8000/sessions/{id}/ask \
  -H 'Authorization: Bearer eyJ...' \
  -H 'Content-Type: application/json' \
  -d '{"question": "How do I merge two dictionaries in Python?"}' \
  --no-buffer
```

Streams Server-Sent Events:

```
data: {"type": "thinking", "status": "retrieving"}
data: {"type": "thinking", "status": "generating"}
data: {"type": "token", "content": "You can merge "}
data: {"type": "token", "content": "two dictionaries..."}
data: {"type": "metadata", "sources": [...], "grounded": true, "latency_ms": 2341, "model": "gemini-2.5-flash"}
data: {"type": "done"}
```

### `GET /health`

```json
{
  "status": "ok",
  "vector_db": { "connected": true, "document_count": 25000 },
  "model": "gemini-2.5-flash",
  "timestamp": "2026-06-13T10:00:00Z"
}
```

| Status code | Meaning |
|---|---|
| `200` | Success |
| `401` | Missing or expired JWT |
| `422` | Validation error (question too short/long) |
| `503` | RAG pipeline not yet initialised |

---

## Deployment

### Backend — Railway (Docker image)

```bash
cd backend
railway login
railway link          # link to your Railway project
railway up --detach   # build and deploy Docker image
```

**Railway environment variables to set:**

All variables from `backend/.env` above, plus:

```env
ENVIRONMENT=production
CORS_ORIGINS=https://your-frontend.vercel.app
PORT=8080   # Railway injects this automatically
```

**Railway Volume:** Create a volume named `chroma-index` and mount it at `/app/chroma_db` in the Railway dashboard. This persists the ChromaDB index across deployments so it only rebuilds once.

### Frontend — Vercel

Import the `frontend/` directory into Vercel and set:

```env
NEXT_PUBLIC_API_URL=https://your-backend.up.railway.app
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Hybrid dense + sparse retrieval | Dense search misses exact terms (e.g. `KeyError`, `pd.merge`); sparse search misses paraphrased questions. RRF combines both signals so the best of each surfaces |
| MMR on dense candidates | Prevents returning 8 near-duplicate Stack Overflow answers; diverse context produces richer LLM synthesis |
| MongoDB as knowledge base store | ChromaDB is ephemeral in a container. MongoDB is persistent and cloud-hosted; ChromaDB rebuilds from it on every cold start so no large files are baked into the Docker image |
| Background async rebuild | `asyncio.create_task()` runs the ChromaDB rebuild without blocking startup. Railway's healthcheck passes immediately; the index becomes available gradually |
| SSE streaming over WebSockets | One-directional server→client token stream is all that's needed. SSE is simpler, works over HTTP/1.1, and requires no handshake overhead |
| LLM fallback on empty retrieval | A robotic "I don't know" response is a poor user experience. When the corpus has nothing, the LLM answers from general Python expertise — clearly labelled so the user knows the source |
| Conversation history injected via MessagesPlaceholder | Last 10 messages per session are passed to the LLM as HumanMessage/AIMessage objects. Follow-up questions resolve naturally without the user repeating context |
| JWT stateless auth | Any backend instance verifies any token — no sticky sessions needed, horizontal scaling is straightforward |

---

## Scaling for 100+ Concurrent Users

| Layer | Strategy |
|---|---|
| Backend | FastAPI async handlers support many concurrent SSE streams per instance. Add Railway replicas behind a load balancer — JWT auth means any instance handles any request |
| LLM API | Queue requests with Redis + asyncio; users wait in a visible queue rather than getting timeouts at peak load |
| Retrieval cache | Cache ChromaDB + MongoDB results in Redis (60s TTL). Identical or similar questions reuse cached results, reducing both latency and Gemini API cost |
| Vector DB | Replace ChromaDB with Pinecone or Weaviate at scale — both are managed, horizontally scalable, and support MMR natively |
| MongoDB | Motor connection pool (50–100 connections); Atlas auto-scales read replicas for high read throughput |
| Cost | Gemini 2.5 Flash ≈ $0.075/M tokens. 100 users × 500 tokens/answer = 50k tokens/min at peak. A 40% cache hit rate halves the API cost |

---

*Submitted by Bhavik — Analytics Vidhya AI Engineer Assessment 2026*
