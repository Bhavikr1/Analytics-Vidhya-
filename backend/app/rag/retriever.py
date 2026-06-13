"""Hybrid retriever: dense (ChromaDB + MMR) + sparse (MongoDB text) fused via RRF.

Pipeline:
  1. Dense leg  — embed query → fetch fetch_k candidates from ChromaDB →
                  threshold-filter by cosine similarity → MMR-select k diverse docs
  2. Sparse leg — MongoDB $text search (BM25-like) → top k docs
  3. Fusion     — Reciprocal Rank Fusion (RRF) of both ranked lists
  4. Return     — top-k unique docs ordered by fused score
"""

import logging
from dataclasses import dataclass

import numpy as np
from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import get_settings
from app.db.mongodb import get_db

logger = logging.getLogger("ttapi")


@dataclass
class RetrievedDoc:
    document: Document
    score: float  # 0–1, higher = more relevant


# ── Internal helpers ──────────────────────────────────────────────────────────

def _cosine_sim(a: list[float], b: list[float]) -> float:
    an = np.array(a, dtype=np.float32)
    bn = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(an) * np.linalg.norm(bn)
    return float(np.dot(an, bn) / (denom + 1e-10))


def _mmr(
    query_emb: list[float],
    candidates: list[tuple[Document, list[float], float]],  # (doc, emb, query_sim)
    k: int,
    lambda_mult: float,
) -> list[tuple[Document, float]]:
    """Greedy MMR selection: balance relevance (query sim) vs. diversity (inter-doc sim)."""
    if not candidates:
        return []

    selected: list[int] = []
    remaining = list(range(len(candidates)))

    while len(selected) < k and remaining:
        if not selected:
            best = max(remaining, key=lambda i: candidates[i][2])
        else:
            best, best_score = None, float("-inf")
            for i in remaining:
                q_sim = candidates[i][2]
                max_sel_sim = max(
                    _cosine_sim(candidates[i][1], candidates[j][1])
                    for j in selected
                )
                mmr_score = lambda_mult * q_sim - (1 - lambda_mult) * max_sel_sim
                if mmr_score > best_score:
                    best_score, best = mmr_score, i

        selected.append(best)
        remaining.remove(best)

    return [(candidates[i][0], candidates[i][2]) for i in selected]


def _rrf(ranked_lists: list[list[str]], k_const: int = 60) -> dict[str, float]:
    """Reciprocal Rank Fusion across multiple ranked lists."""
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k_const + rank)
    return scores


def _doc_id(rd: RetrievedDoc) -> str:
    return rd.document.metadata.get("_id") or rd.document.page_content[:80]


# ── Dense leg ─────────────────────────────────────────────────────────────────

def _dense_retrieve(
    vectorstore: Chroma,
    question: str,
    fetch_k: int,
    min_score: float,
    k: int,
    lambda_mult: float,
) -> list[RetrievedDoc]:
    """Embed question, fetch candidates from ChromaDB, threshold-filter, MMR-select."""
    col = vectorstore._collection
    count = col.count()
    if count == 0:
        logger.warning("ChromaDB collection is empty — dense retrieval skipped")
        return []

    query_emb: list[float] = vectorstore._embedding_function.embed_query(question)

    raw = col.query(
        query_embeddings=[query_emb],
        n_results=min(fetch_k, count),
        include=["documents", "metadatas", "distances", "embeddings"],
    )

    candidates: list[tuple[Document, list[float], float]] = []
    for text, meta, dist, emb in zip(
        raw["documents"][0],
        raw["metadatas"][0],
        raw["distances"][0],
        raw["embeddings"][0],
    ):
        sim = 1.0 - dist  # cosine distance → similarity
        if sim >= min_score:
            doc = Document(page_content=text, metadata=meta)
            candidates.append((doc, list(emb), sim))

    selected = _mmr(query_emb, candidates, k=k, lambda_mult=lambda_mult)
    return [RetrievedDoc(document=doc, score=sim) for doc, sim in selected]


# ── Sparse leg ────────────────────────────────────────────────────────────────

async def _sparse_retrieve(question: str, k: int) -> list[RetrievedDoc]:
    """MongoDB $text search (BM25-like keyword matching)."""
    try:
        db = get_db()
        cursor = db.knowledge_base.find(
            {"$text": {"$search": question}},
            {
                "score": {"$meta": "textScore"},
                "title": 1,
                "text": 1,
                "question_score": 1,
                "answer_score": 1,
                "link": 1,
                "creation_date": 1,
            },
        ).sort([("score", {"$meta": "textScore"})]).limit(k)

        results: list[RetrievedDoc] = []
        async for doc in cursor:
            raw_score = doc.get("score", 0.0)
            norm_score = min(raw_score / 20.0, 1.0)  # normalise; text scores vary widely
            langchain_doc = Document(
                page_content=doc.get("text", ""),
                metadata={
                    "_id": str(doc["_id"]),
                    "title": doc.get("title", ""),
                    "question_score": doc.get("question_score", 0),
                    "answer_score": doc.get("answer_score", 0),
                    "link": doc.get("link", ""),
                    "creation_date": doc.get("creation_date", ""),
                },
            )
            results.append(RetrievedDoc(document=langchain_doc, score=norm_score))
        return results

    except Exception:
        logger.warning("Sparse retrieval failed — falling back to dense only", exc_info=True)
        return []


# ── Hybrid fusion ─────────────────────────────────────────────────────────────

async def retrieve(vectorstore: Chroma, question: str) -> list[RetrievedDoc]:
    """Hybrid retrieval: dense MMR + sparse text search, fused via RRF."""
    settings = get_settings()
    min_score = 1.0 - settings.max_relevance_distance

    dense = _dense_retrieve(
        vectorstore,
        question,
        fetch_k=settings.retrieval_k * 4,
        min_score=min_score,
        k=settings.retrieval_k,
        lambda_mult=settings.retrieval_mmr_lambda,
    )
    sparse = await _sparse_retrieve(question, k=settings.retrieval_k)

    if not dense and not sparse:
        return []

    # RRF fusion
    dense_ids = [_doc_id(rd) for rd in dense]
    sparse_ids = [_doc_id(rd) for rd in sparse]
    fused_scores = _rrf([dense_ids, sparse_ids])

    # Collect all unique docs (prefer dense version which has full metadata)
    all_docs: dict[str, RetrievedDoc] = {}
    for rd in [*sparse, *dense]:  # dense last → overwrites sparse for same doc
        all_docs[_doc_id(rd)] = rd

    ranked = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
    return [all_docs[did] for did, _ in ranked[: settings.retrieval_k] if did in all_docs]


def relevant_only(docs: list[RetrievedDoc]) -> list[RetrievedDoc]:
    """Return docs that passed the threshold (already applied in dense leg; this
    acts as a final guard for any low-score sparse-only survivors)."""
    settings = get_settings()
    min_score = 1.0 - settings.max_relevance_distance
    return [d for d in docs if d.score >= min_score * 0.7]  # lenient for sparse-boosted docs
