"""Test fixtures. The full suite runs offline: no GOOGLE_API_KEY, no network.
The RAG pipeline is replaced with a fake; Chroma uses a temp directory."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Must be set before app.core.config is imported anywhere.
_tmp_chroma = tempfile.mkdtemp(prefix="chroma_test_")
os.environ["CHROMA_DIR"] = _tmp_chroma
os.environ["GOOGLE_API_KEY"] = "test-key-not-used"

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.main import create_app  # noqa: E402


class FakePipeline:
    """Stands in for RAGPipeline — returns canned grounded answers."""

    def __init__(self, grounded: bool = True, error: Exception | None = None):
        self.grounded = grounded
        self.error = error
        self.model_name = "fake-model"

    async def ask(self, question: str) -> dict:
        if self.error:
            raise self.error
        if not self.grounded:
            return {
                "answer": "I couldn't find anything relevant to that in my knowledge base.",
                "sources": [],
                "grounded": False,
                "latency_ms": 5,
                "model": self.model_name,
            }
        return {
            "answer": "Use `dict1 | dict2` to merge dictionaries [1].",
            "sources": [
                {
                    "title": "How do I merge two dictionaries?",
                    "link": "https://stackoverflow.com/questions/38987",
                    "question_score": 6500,
                    "answer_score": 5800,
                    "snippet": "You can merge with the | operator in Python 3.9+...",
                }
            ],
            "grounded": True,
            "latency_ms": 42,
            "model": self.model_name,
        }


@pytest.fixture
def app():
    application = create_app()
    application.state.pipeline = FakePipeline()
    return application


@pytest.fixture
def client(app):
    # Skip lifespan: tests inject their own pipeline state.
    return TestClient(app)
