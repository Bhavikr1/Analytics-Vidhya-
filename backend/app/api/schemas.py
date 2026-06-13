from datetime import datetime, timezone

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="A Python programming question in plain English.",
        examples=["How do I merge two dictionaries in Python?"],
    )


class Source(BaseModel):
    title: str
    link: str
    question_score: int
    answer_score: int
    snippet: str


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    grounded: bool = Field(
        description="False when no relevant context was found and the "
        "assistant declined to answer from the knowledge base."
    )
    latency_ms: int
    model: str


class VectorDBHealth(BaseModel):
    connected: bool
    document_count: int


class HealthResponse(BaseModel):
    status: str
    vector_db: VectorDBHealth
    model: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ErrorResponse(BaseModel):
    detail: str
