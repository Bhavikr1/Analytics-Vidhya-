"""Upload the processed corpus into MongoDB so Railway can rebuild ChromaDB
from it on startup — no need to bake chroma_db into the Docker image.

Usage (run once locally after corpus.parquet exists):
  python scripts/ingest_to_mongodb.py
  python scripts/ingest_to_mongodb.py --max-docs 1000   # smaller subset
"""

import argparse
import asyncio
import sys
from pathlib import Path

import pandas as pd
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReplaceOne

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402

CORPUS_PATH = BACKEND_DIR / "data" / "corpus.parquet"
BATCH_SIZE = 200


async def main(max_docs: int) -> None:
    if not CORPUS_PATH.exists():
        sys.exit(
            "corpus.parquet not found.\n"
            "Run  python scripts/ingest.py --corpus-only  first to build it."
        )

    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]

    df = pd.read_parquet(CORPUS_PATH)
    if max_docs:
        df = df.head(max_docs)
    print(f"Uploading {len(df)} documents to MongoDB collection 'knowledge_base' ...")

    docs = [
        {
            "_id": f"q{row.question_id}",
            "title": row.title,
            "text": row.text,
            "question_score": int(row.question_score),
            "answer_score": int(row.answer_score),
            "link": row.link,
            "creation_date": row.creation_date,
        }
        for row in df.itertuples(index=False)
    ]

    total = len(docs)
    for i in range(0, total, BATCH_SIZE):
        batch = docs[i : i + BATCH_SIZE]
        ops = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in batch]
        await db.knowledge_base.bulk_write(ops)
        done = min(i + BATCH_SIZE, total)
        print(f"  {done}/{total} uploaded", end="\r")

    # Create an index on _id (already exists by default) — add text index too
    await db.knowledge_base.create_index("title")
    count = await db.knowledge_base.count_documents({})
    print(f"\nDone. MongoDB knowledge_base collection: {count} documents.")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-docs",
        type=int,
        default=0,
        help="Limit number of docs (0 = all). Use 1000 for a quick test.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.max_docs))
