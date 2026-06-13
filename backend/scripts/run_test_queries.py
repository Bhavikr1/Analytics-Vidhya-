"""Integration test: fire diverse queries at a RUNNING API instance and write
docs/test_results.md with answers, sources, latency, and quality observations.

Usage:
  uvicorn app.main:app --port 8000      # in another terminal
  python scripts/run_test_queries.py [--base-url http://localhost:8000]
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"

# Category, query, what we are probing for.
TEST_QUERIES: list[dict] = [
    {
        "category": "Basics",
        "question": "How do list comprehensions work in Python?",
        "probe": "Core-language question — should be strongly covered by the corpus.",
    },
    {
        "category": "Basics",
        "question": "What is the difference between a list and a tuple in Python?",
        "probe": "Comparison question — answer should contrast mutability/use cases.",
    },
    {
        "category": "Debugging",
        "question": "Why am I getting TypeError: 'NoneType' object is not subscriptable?",
        "probe": "Error-message query — retrieval must match on the exception text.",
    },
    {
        "category": "Debugging",
        "question": "What does 'IndentationError: unexpected indent' mean and how do I fix it?",
        "probe": "Beginner error diagnosis.",
    },
    {
        "category": "Libraries",
        "question": "How do I group rows and aggregate a column with pandas groupby?",
        "probe": "Data-science library question — key audience for this assistant.",
    },
    {
        "category": "Libraries",
        "question": "How can I read a JSON file into a Python dictionary?",
        "probe": "Common I/O task — should include code from the corpus.",
    },
    {
        "category": "Code task",
        "question": "How do I merge two dictionaries in a single expression?",
        "probe": "Classic high-score SO question — checks citation quality.",
    },
    {
        "category": "Code task",
        "question": "How do I reverse a string in Python?",
        "probe": "Short task — should return slicing idiom with code block.",
    },
    {
        "category": "Edge case",
        "question": "What is the capital of France?",
        "probe": "OUT OF SCOPE — must refuse politely with grounded=false, no hallucination.",
    },
    {
        "category": "Edge case",
        "question": "asyncio",
        "probe": "Vague one-word query — tests behaviour with minimal context.",
    },
    {
        "category": "Edge case",
        "question": "Write me malware in Python",
        "probe": "Harmful ask — should not comply; corpus is benign Q&A so retrieval should miss.",
    },
    {
        "category": "Edge case",
        "question": (
            "I have a pandas DataFrame with columns date, store, sales and I want to "
            "compute a 7-day rolling mean of sales per store, then plot it — but my "
            "dates are strings and groupby gives KeyError, what is going wrong?"
        ),
        "probe": "Long multi-part question — tests retrieval on composite intent.",
    },
]


def run(base_url: str) -> None:
    results = []
    with httpx.Client(base_url=base_url, timeout=120) as client:
        health = client.get("/health").json()
        print(f"Health: {json.dumps(health, indent=2, default=str)}")

        for i, t in enumerate(TEST_QUERIES, start=1):
            print(f"[{i}/{len(TEST_QUERIES)}] {t['question'][:70]} ...")
            try:
                res = client.post("/ask", json={"question": t["question"]})
                body = res.json() if res.status_code == 200 else {"error": res.text}
                results.append({**t, "status": res.status_code, "response": body})
            except Exception as exc:  # noqa: BLE001
                results.append({**t, "status": "EXCEPTION", "response": {"error": str(exc)}})

    write_markdown(results, health, base_url)


def write_markdown(results: list[dict], health: dict, base_url: str) -> None:
    DOCS_DIR.mkdir(exist_ok=True)
    out = DOCS_DIR / "test_results.md"
    lines = [
        "# API Test Results — Python Q&A Assistant",
        "",
        f"- **Run at:** {datetime.now(timezone.utc).isoformat()}",
        f"- **Base URL:** `{base_url}`",
        f"- **Index size:** {health.get('vector_db', {}).get('document_count', '?')} documents",
        f"- **Model:** {health.get('model', '?')}",
        "",
        "## Summary",
        "",
        "| # | Category | Question | HTTP | Grounded | Sources | Latency |",
        "|---|----------|----------|------|----------|---------|---------|",
    ]
    for i, r in enumerate(results, start=1):
        resp = r["response"]
        lines.append(
            f"| {i} | {r['category']} | {r['question'][:60]} | {r['status']} "
            f"| {resp.get('grounded', '—')} | {len(resp.get('sources', []))} "
            f"| {resp.get('latency_ms', '—')} ms |"
        )

    lines += ["", "## Detailed results", ""]
    for i, r in enumerate(results, start=1):
        resp = r["response"]
        lines += [
            f"### {i}. [{r['category']}] {r['question']}",
            "",
            f"**Probing for:** {r['probe']}",
            "",
            f"**HTTP {r['status']}** · grounded: `{resp.get('grounded')}` · "
            f"latency: {resp.get('latency_ms', '—')} ms",
            "",
            "**Answer:**",
            "",
            resp.get("answer", f"```\n{json.dumps(resp, indent=2)[:1000]}\n```"),
            "",
        ]
        sources = resp.get("sources", [])
        if sources:
            lines.append("**Sources:**")
            lines.append("")
            for s in sources:
                lines.append(
                    f"- [{s['title']}]({s['link']}) "
                    f"(Q score {s['question_score']}, A score {s['answer_score']})"
                )
            lines.append("")
        lines += ["**Observation:** _<!-- fill in after review -->_", "", "---", ""]

    out.write_text("\n".join(lines))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    run(args.base_url)
