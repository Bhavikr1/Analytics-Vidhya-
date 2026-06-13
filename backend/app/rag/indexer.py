"""Rebuild the ChromaDB vector index from MongoDB knowledge_base collection.

Called automatically at startup when ChromaDB is empty.
"""

import logging
import time

from langchain_core.documents import Document
from tenacity import retry, stop_after_attempt, wait_exponential

from app.db.mongodb import get_db
from app.rag.vectorstore import get_document_count, get_vectorstore

logger = logging.getLogger("ttapi")

EMBED_BATCH = 50  # keep small — Gemini embedding API has rate limits


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=2, max=60))
def _add_batch(vectorstore, texts, metadatas, ids):
    vectorstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)


async def build_chroma_from_mongodb() -> int:
    """Fetch all documents from MongoDB and embed them into ChromaDB.
    Returns the number of documents indexed."""
    db = get_db()
    total = await db.knowledge_base.count_documents({})
    if total == 0:
        logger.warning(
            "MongoDB knowledge_base is empty — run  "
            "python scripts/ingest_to_mongodb.py  locally first."
        )
        return 0

    logger.info("Rebuilding ChromaDB from MongoDB: %d documents to embed ...", total)
    vectorstore = get_vectorstore()

    cursor = db.knowledge_base.find(
        {},
        {"_id": 1, "title": 1, "text": 1, "question_score": 1,
         "answer_score": 1, "link": 1, "creation_date": 1},
    )

    batch_texts, batch_meta, batch_ids = [], [], []
    indexed = 0
    started = time.perf_counter()

    async for doc in cursor:
        batch_texts.append(doc["text"])
        batch_meta.append({
            "title": doc.get("title", ""),
            "question_score": doc.get("question_score", 0),
            "answer_score": doc.get("answer_score", 0),
            "link": doc.get("link", ""),
            "creation_date": doc.get("creation_date", ""),
        })
        batch_ids.append(doc["_id"])

        if len(batch_texts) >= EMBED_BATCH:
            _add_batch(vectorstore, batch_texts, batch_meta, batch_ids)
            indexed += len(batch_texts)
            elapsed = time.perf_counter() - started
            rate = indexed / max(elapsed, 1)
            eta = (total - indexed) / max(rate, 0.1)
            logger.info(
                "Indexed %d/%d  (%.0f docs/s, ETA %.1f min)",
                indexed, total, rate, eta / 60,
            )
            batch_texts, batch_meta, batch_ids = [], [], []

    # flush remainder
    if batch_texts:
        _add_batch(vectorstore, batch_texts, batch_meta, batch_ids)
        indexed += len(batch_texts)

    logger.info("ChromaDB rebuild complete: %d documents indexed.", indexed)
    return indexed


async def ensure_chroma_populated() -> None:
    """Check ChromaDB document count; rebuild from MongoDB if empty."""
    try:
        count = get_document_count()
    except Exception:
        count = 0

    if count > 0:
        logger.info("ChromaDB already has %d documents — skipping rebuild.", count)
        return

    logger.info("ChromaDB is empty — starting rebuild from MongoDB ...")
    try:
        indexed = await build_chroma_from_mongodb()
        if indexed == 0:
            logger.error(
                "ChromaDB rebuild produced 0 documents. "
                "Run  python scripts/ingest_to_mongodb.py  to populate MongoDB first."
            )
    except Exception:
        logger.exception("ChromaDB rebuild failed")
