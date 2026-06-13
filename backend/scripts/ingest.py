"""Build the Chroma vector index from the Stack Overflow Python dataset.

Two stages, both resumable:
  1. Corpus build: stream Questions.csv + Answers.csv (latin-1, chunked),
     filter by score, pair each question with its highest-scored answer,
     clean HTML to markdown (code blocks preserved) -> data/corpus.parquet
  2. Embedding: batch-embed corpus docs with Gemini text-embedding-004 into
     the persistent Chroma collection, skipping ids that already exist.

Usage:
  python scripts/ingest.py                  # full run (~25k docs)
  python scripts/ingest.py --max-docs 500   # small smoke-test index
  python scripts/ingest.py --rebuild-corpus # force corpus rebuild
"""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.rag.vectorstore import get_vectorstore  # noqa: E402

DATA_DIR = BACKEND_DIR / "data"
CORPUS_PATH = DATA_DIR / "corpus.parquet"

MIN_QUESTION_SCORE = 5
MIN_ANSWER_SCORE = 2
MAX_DOCS = 25_000
CSV_CHUNK = 50_000
EMBED_BATCH = 100
MAX_QUESTION_CHARS = 3_000
MAX_ANSWER_CHARS = 4_000


# ── HTML → markdown-ish text ─────────────────────────────────────────────────

def html_to_text(html: str) -> str:
    """Strip HTML but keep code: <pre><code> -> fenced block, <code> -> backticks."""
    soup = BeautifulSoup(html or "", "lxml")
    for pre in soup.find_all("pre"):
        code = pre.get_text()
        pre.replace_with(f"\n```python\n{code.rstrip()}\n```\n")
    for code in soup.find_all("code"):
        code.replace_with(f"`{code.get_text()}`")
    text = soup.get_text()
    # Collapse 3+ blank lines
    lines = [ln.rstrip() for ln in text.splitlines()]
    out, blanks = [], 0
    for ln in lines:
        blanks = blanks + 1 if not ln else 0
        if blanks <= 1:
            out.append(ln)
    return "\n".join(out).strip()


# ── Stage 1: corpus build ────────────────────────────────────────────────────

def load_qualifying_questions(min_q_score: int) -> pd.DataFrame:
    print(f"Scanning Questions.csv for score >= {min_q_score} ...")
    keep = []
    reader = pd.read_csv(
        DATA_DIR / "Questions.csv",
        encoding="latin-1",
        usecols=["Id", "CreationDate", "Score", "Title", "Body"],
        chunksize=CSV_CHUNK,
    )
    for i, chunk in enumerate(reader):
        keep.append(chunk[chunk["Score"] >= min_q_score])
        print(f"  questions chunk {i + 1}: kept {sum(len(k) for k in keep)} so far", end="\r")
    questions = pd.concat(keep, ignore_index=True)
    print(f"\nQualifying questions: {len(questions)}")
    return questions


def load_best_answers(question_ids: set[int], min_a_score: int) -> pd.DataFrame:
    print(f"Scanning Answers.csv for best answer per question (score >= {min_a_score}) ...")
    best: dict[int, tuple[int, str]] = {}  # parent_id -> (score, body)
    reader = pd.read_csv(
        DATA_DIR / "Answers.csv",
        encoding="latin-1",
        usecols=["ParentId", "Score", "Body"],
        chunksize=CSV_CHUNK,
    )
    for i, chunk in enumerate(reader):
        chunk = chunk[(chunk["Score"] >= min_a_score) & chunk["ParentId"].isin(question_ids)]
        for parent_id, score, body in chunk.itertuples(index=False):
            cur = best.get(parent_id)
            if cur is None or score > cur[0]:
                best[parent_id] = (int(score), body)
        print(f"  answers chunk {i + 1}: {len(best)} questions matched", end="\r")
    print(f"\nQuestions with a qualifying answer: {len(best)}")
    return pd.DataFrame(
        [(pid, s, b) for pid, (s, b) in best.items()],
        columns=["ParentId", "AnswerScore", "AnswerBody"],
    )


def build_corpus(args: argparse.Namespace) -> pd.DataFrame:
    questions = load_qualifying_questions(args.min_question_score)
    answers = load_best_answers(set(questions["Id"]), args.min_answer_score)

    merged = questions.merge(answers, left_on="Id", right_on="ParentId")
    merged = merged.sort_values("Score", ascending=False).head(args.max_docs)
    print(f"Corpus size after top-{args.max_docs} cut: {len(merged)}")

    print("Cleaning HTML (this takes a few minutes) ...")
    records = []
    for n, row in enumerate(merged.itertuples(index=False), start=1):
        q_text = html_to_text(row.Body)[:MAX_QUESTION_CHARS]
        a_text = html_to_text(row.AnswerBody)[:MAX_ANSWER_CHARS]
        records.append(
            {
                "question_id": int(row.Id),
                "title": str(row.Title),
                "question_score": int(row.Score),
                "answer_score": int(row.AnswerScore),
                "creation_date": str(row.CreationDate),
                "link": f"https://stackoverflow.com/questions/{int(row.Id)}",
                "text": f"# {row.Title}\n\n## Question\n{q_text}\n\n## Accepted/Top Answer\n{a_text}",
            }
        )
        if n % 1000 == 0:
            print(f"  cleaned {n}/{len(merged)}", end="\r")
    corpus = pd.DataFrame(records)
    DATA_DIR.mkdir(exist_ok=True)
    corpus.to_parquet(CORPUS_PATH, index=False)
    print(f"\nWrote corpus: {CORPUS_PATH} ({len(corpus)} docs)")
    return corpus


# ── Stage 2: embed into Chroma ───────────────────────────────────────────────

@retry(stop=stop_after_attempt(6), wait=wait_exponential(multiplier=2, min=2, max=120))
def add_batch(vectorstore, texts, metadatas, ids):
    vectorstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)


def embed_corpus(corpus: pd.DataFrame) -> None:
    settings = get_settings()
    if not settings.google_api_key:
        sys.exit("GOOGLE_API_KEY is not set — cannot embed. Add it to backend/.env")

    vectorstore = get_vectorstore()
    existing = set(vectorstore.get(include=[])["ids"])
    print(f"Chroma collection '{settings.chroma_collection}': {len(existing)} docs already present")

    pending = corpus[~corpus["question_id"].astype(str).radd("q").isin(existing)]
    print(f"Docs to embed: {len(pending)}")
    if pending.empty:
        print("Nothing to do.")
        return

    started = time.time()
    rows = pending.to_dict("records")
    for i in range(0, len(rows), EMBED_BATCH):
        batch = rows[i : i + EMBED_BATCH]
        add_batch(
            vectorstore,
            texts=[r["text"] for r in batch],
            metadatas=[
                {
                    "question_id": r["question_id"],
                    "title": r["title"],
                    "question_score": r["question_score"],
                    "answer_score": r["answer_score"],
                    "creation_date": r["creation_date"],
                    "link": r["link"],
                }
                for r in batch
            ],
            ids=[f"q{r['question_id']}" for r in batch],
        )
        done = i + len(batch)
        rate = done / max(time.time() - started, 1)
        eta = (len(rows) - done) / max(rate, 0.1)
        print(f"  embedded {done}/{len(rows)}  ({rate:.0f} docs/s, ETA {eta / 60:.1f} min)", end="\r")
    print(f"\nDone. Collection now has {len(vectorstore.get(include=[])['ids'])} docs.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-docs", type=int, default=MAX_DOCS)
    parser.add_argument("--min-question-score", type=int, default=MIN_QUESTION_SCORE)
    parser.add_argument("--min-answer-score", type=int, default=MIN_ANSWER_SCORE)
    parser.add_argument("--rebuild-corpus", action="store_true")
    parser.add_argument("--corpus-only", action="store_true", help="skip embedding stage")
    args = parser.parse_args()

    if CORPUS_PATH.exists() and not args.rebuild_corpus:
        corpus = pd.read_parquet(CORPUS_PATH)
        print(f"Loaded existing corpus: {len(corpus)} docs (use --rebuild-corpus to redo)")
        if len(corpus) > args.max_docs:
            corpus = corpus.head(args.max_docs)
            print(f"Capped to --max-docs={args.max_docs}")
    else:
        if not (DATA_DIR / "Questions.csv").exists():
            sys.exit(f"Dataset not found in {DATA_DIR}. Run scripts/download_data.py first.")
        corpus = build_corpus(args)

    if not args.corpus_only:
        embed_corpus(corpus)


if __name__ == "__main__":
    main()
