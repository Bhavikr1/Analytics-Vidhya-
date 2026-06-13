from dataclasses import dataclass

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import get_settings


@dataclass
class RetrievedDoc:
    document: Document
    distance: float  # cosine distance: 0 = identical, larger = less similar


def retrieve(vectorstore: Chroma, question: str) -> list[RetrievedDoc]:
    """Top-k similarity search. Returns ALL hits with their distances;
    relevance filtering is the caller's decision so the API can report
    why a question was considered out of scope."""
    settings = get_settings()
    results = vectorstore.similarity_search_with_score(question, k=settings.retrieval_k)
    return [RetrievedDoc(document=doc, distance=score) for doc, score in results]


def relevant_only(docs: list[RetrievedDoc]) -> list[RetrievedDoc]:
    settings = get_settings()
    return [d for d in docs if d.distance <= settings.max_relevance_distance]
