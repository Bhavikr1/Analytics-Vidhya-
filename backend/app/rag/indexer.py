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


async def ensure_mongodb_text_index() -> None:
    """Create a compound text index on (title, text) for the sparse retrieval leg.
    Safe to call repeatedly — MongoDB ignores duplicate index creation."""
    try:
        from app.db.mongodb import get_db
        db = get_db()
        await db.knowledge_base.create_index(
            [("title", "text"), ("text", "text")],
            name="knowledge_base_text_idx",
            default_language="english",
        )
        logger.info("MongoDB text index on knowledge_base ensured.")
    except Exception:
        logger.warning("Could not create MongoDB text index — sparse retrieval may be unavailable", exc_info=True)


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


def _reset_chroma_collection() -> None:
    """Delete and recreate the ChromaDB collection to clear corruption."""
    try:
        from app.rag.vectorstore import get_chroma_client
        from app.core.config import get_settings
        settings = get_settings()
        client = get_chroma_client()
        client.delete_collection(settings.chroma_collection)
        logger.info("Deleted corrupted ChromaDB collection — will rebuild from scratch.")
    except Exception:
        logger.warning("Could not delete ChromaDB collection", exc_info=True)


async def ensure_chroma_populated() -> None:
    """Compare ChromaDB vs MongoDB counts; rebuild if empty or incomplete (< 95%)."""
    try:
        chroma_count = get_document_count()
    except Exception:
        logger.warning("ChromaDB collection is corrupted — resetting for fresh rebuild")
        _reset_chroma_collection()
        chroma_count = 0

    try:
        from app.db.mongodb import get_db
        db = get_db()
        mongo_count = await db.knowledge_base.count_documents({})
    except Exception:
        mongo_count = 0

    # Skip only when ChromaDB is at least 95% of MongoDB
    if chroma_count > 0 and (mongo_count == 0 or chroma_count >= int(mongo_count * 0.95)):
        logger.info(
            "ChromaDB has %d/%d documents — index is complete, skipping rebuild.",
            chroma_count, mongo_count,
        )
        return

    if chroma_count > 0:
        logger.info(
            "ChromaDB has %d/%d documents — index is incomplete, rebuilding ...",
            chroma_count, mongo_count,
        )
    else:
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
