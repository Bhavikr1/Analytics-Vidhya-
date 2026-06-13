import logging

from fastapi import APIRouter, HTTPException, Request

from app.api.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    VectorDBHealth,
)
from app.core.config import get_settings
from app.rag.vectorstore import get_document_count

logger = logging.getLogger("ttapi")

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    try:
        count = get_document_count()
        connected = True
    except Exception:  # noqa: BLE001 — health must never raise
        logger.exception("Vector DB health check failed")
        count = 0
        connected = False
    return HealthResponse(
        status="ok" if connected else "degraded",
        vector_db=VectorDBHealth(connected=connected, document_count=count),
        model=settings.generation_model,
    )


@router.post(
    "/ask",
    response_model=AskResponse,
    responses={503: {"description": "RAG pipeline unavailable"}},
)
async def ask(request: Request, body: AskRequest) -> AskResponse:
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="RAG pipeline is not initialised. Check server logs and GOOGLE_API_KEY.",
        )
    try:
        result = await pipeline.ask(body.question)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — surface as clean 502, log full trace
        logger.exception("RAG pipeline error for question: %s", body.question[:200])
        raise HTTPException(
            status_code=502, detail=f"Failed to generate an answer: {type(exc).__name__}"
        ) from exc
    return AskResponse(**result)
