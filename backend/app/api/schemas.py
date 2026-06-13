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


# Session / chat-history schemas
class SessionCreate(BaseModel):
    title: str = "New Chat"


class SessionUpdateTitle(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: list[Source] | None = None
    grounded: bool | None = None
    latency_ms: int | None = None
    model: str | None = None
    created_at: datetime


class SessionWithMessages(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse]


# Authentication schemas
class LoginRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Username for authentication",
        examples=["Analytics Vidhya"]
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Password for authentication"
    )


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token expiration time in seconds")


class TokenPayload(BaseModel):
    username: str
    exp: int
