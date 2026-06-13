from langchain_core.documents import Document

from app.rag.chain import format_context, make_sources
from app.rag.retriever import RetrievedDoc, relevant_only


def _doc(distance: float, title: str = "Sample question") -> RetrievedDoc:
    return RetrievedDoc(
        document=Document(
            page_content="Q: sample\nA: sample answer with code",
            metadata={
                "title": title,
                "link": "https://stackoverflow.com/questions/1",
                "question_score": 10,
                "answer_score": 7,
            },
        ),
        distance=distance,
    )


def test_relevant_only_filters_by_distance_threshold():
    docs = [_doc(0.2), _doc(0.59), _doc(0.61), _doc(0.9)]
    kept = relevant_only(docs)  # default threshold 0.60
    assert [d.distance for d in kept] == [0.2, 0.59]


def test_relevant_only_empty_when_all_far():
    assert relevant_only([_doc(0.8), _doc(0.95)]) == []


def test_format_context_numbers_sources():
    ctx = format_context([_doc(0.1, "First"), _doc(0.2, "Second")])
    assert '[1] "First"' in ctx
    assert '[2] "Second"' in ctx
    assert "question score: 10" in ctx


def test_make_sources_shape_and_snippet_cap():
    long_doc = RetrievedDoc(
        document=Document(
            page_content="x" * 1000,
            metadata={
                "title": "Long",
                "link": "https://stackoverflow.com/questions/2",
                "question_score": 3,
                "answer_score": 1,
            },
        ),
        distance=0.3,
    )
    sources = make_sources([long_doc])
    assert len(sources) == 1
    assert len(sources[0]["snippet"]) == 300
    assert sources[0]["title"] == "Long"
