---
marp: true
theme: default
paginate: true
size: 16:9
style: |
  section { font-size: 24px; }
  h1 { color: #1a7f64; }
  table { font-size: 19px; }
---

# 🐍 Python Programming Q&A Assistant

### RAG over Stack Overflow's Python knowledge base

**Analytics Vidhya · AI Engineer Assessment — Round 1**

FastAPI · LangChain · Gemini 2.0 Flash · ChromaDB · Next.js + TypeScript

---

# What I built

- **Grounded Q&A system**: ask any Python question → answer synthesized *only* from
  real, high-scoring Stack Overflow answers, with clickable citations
- **REST API (FastAPI)**: `POST /ask`, `GET /health`, OpenAPI docs, async end-to-end
- **Chat frontend (Next.js + TS)**: markdown + syntax-highlighted code, expandable
  source cards, live health badge
- **Honest by design**: out-of-scope questions get a refusal (`grounded: false`),
  never a hallucination
- **Tested**: 16 offline unit tests + 12-query integration suite with documented results

---

# Architecture

```
                   OFFLINE (one-time, resumable)
 Kaggle 607k Q / 987k A ─► filter score≥5 ─► best answer per Q
        ─► clean HTML (keep code) ─► top 25k ─► embed ─► ChromaDB

                   ONLINE (per request)
 Next.js ──POST /ask──► FastAPI ──top-5 cosine──► ChromaDB
                          │
                  relevance gate (dist ≤ 0.6)
                   │ fail              │ pass
            refusal, no LLM    Gemini 2.0 Flash
            (grounded:false)   grounded prompt + [n] citations
```

---

# Key design decisions — data

| Decision | Why |
|---|---|
| **Top 25k of 607k questions** (Q score ≥ 5, A score ≥ 2) | Quality beats volume: high-score pairs cover most real learner questions; index fits free-tier hosting; embedding cost ≈ $0 |
| **Best-scored answer per question** | Dataset has no accepted-answer flag — community score is the best proxy |
| **One Q&A pair = one chunk** | Natural retrieval unit; mid-answer splitting destroys code context |
| **Code-preserving HTML cleaning** | `<pre><code>` → fenced blocks — code is *the* signal in programming Q&A |
| **Resumable ingestion** | Parquet corpus cache + skip-existing-ids: rate-limit interruptions lose nothing |

---

# Key design decisions — RAG & API

| Decision | Why |
|---|---|
| **Retrieval-score relevance gate** | Out-of-scope detection with zero extra latency/cost — below-threshold questions never reach the LLM |
| **Grounding enforced in pipeline, not just prompt** | No relevant docs ⇒ code path returns refusal; the LLM cannot answer unguarded |
| **Numbered context → `[n]` citations** | Every claim traceable to a verifiable Stack Overflow post |
| **Lifespan-loaded pipeline** | Index + LLM client built once at startup; misconfiguration degrades to 503, `/health` stays up |
| **Gemini 2.0 Flash + text-embedding-004** | Strong quality/latency/cost balance; single API key for both |

---

# API

```bash
POST /ask  {"question": "How do I merge two dictionaries?"}

{
  "answer": "Use the | operator (Python 3.9+)… [1]",
  "sources": [{"title": "...", "link": "https://stackoverflow.com/q/38987",
               "question_score": 6543, "answer_score": 5821}],
  "grounded": true, "latency_ms": 1843, "model": "gemini-2.0-flash"
}
```

- `422` invalid input · `502` LLM failure · `503` pipeline unavailable
- `GET /health` → vector-DB connectivity + document count + model

---

# Testing

**Offline unit tests (16, no network/key needed)** — LLM mocked:
health shape · happy path · validation (empty/short/long/wrong-type) ·
pipeline-down 503 · LLM-failure 502 · relevance-gate filtering · context formatting

**Integration suite (12 diverse queries)** → `docs/test_results.md`:

| Category | Examples | Result |
|---|---|---|
| Basics | list comprehensions, list vs tuple | grounded, cited |
| Debugging | `NoneType not subscriptable`, IndentationError | retrieval matches on error text |
| Libraries | pandas groupby, JSON I/O | grounded, code included |
| Edge cases | capital of France, "asyncio", malware request | refused / handled safely |

---

# Scaling to 100+ concurrent users

| Layer | Now | At scale |
|---|---|---|
| **API** | 1× uvicorn, async | k8s/ECS horizontal pods behind a load balancer; uvicorn workers = CPU cores |
| **LLM calls** | async, non-blocking | request coalescing + provider rate-limit pooling; streaming responses (SSE) to cut perceived latency |
| **Caching** | none | Redis **semantic cache** (embed question → reuse answer at distance < 0.05): learner questions repeat heavily → 40–60% LLM cost cut |
| **Vector DB** | embedded Chroma | managed Qdrant/pgvector — replicated, concurrent, decoupled from API pods |
| **Cost** | ~$0 (free tier) | Flash-tier model + semantic cache ≈ **$2–4 / 1k questions**; cache hits are free |
| **Resilience** | graceful 503s | rate limiting per user, circuit breaker on LLM, fallback model |

---

# What I'd do next

- **Streaming responses** (SSE) — first token in <1s instead of waiting for full answer
- **Hybrid retrieval** — BM25 + dense fusion: error-message queries benefit from exact
  token matching (`TypeError: …`)
- **Reranker** (cross-encoder) on top-20 → top-5 for sharper context
- **Eval harness** — golden Q&A set scored by an LLM judge on groundedness/completeness,
  run in CI on every prompt or threshold change
- **Feedback loop** — thumbs up/down per answer, logged for retrieval tuning

---

# Thank you

**Repo:** github.com/<user>/python-qa-assistant *(private per NDA)*
**Live demo:** *<deployed URL>*
**Docs:** README · `docs/architecture.md` · `docs/test_results.md`

*Stack: FastAPI · LangChain · Gemini 2.0 Flash · text-embedding-004 · ChromaDB ·
Next.js 16 · TypeScript · Tailwind · pytest*
