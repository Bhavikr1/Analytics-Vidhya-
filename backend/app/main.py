import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import auth, routes, sessions
from app.core.config import get_settings
from app.db.mongodb import close_db, connect_db

settings = get_settings()
IS_PROD = settings.environment.lower() == "production"

logging.basicConfig(level=logging.WARNING if IS_PROD else logging.INFO)
logger = logging.getLogger("ttapi")


# ── Security headers (production only) ────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if IS_PROD:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await connect_db()
    except Exception:
        logger.exception("Failed to connect to MongoDB — session history unavailable")

    # ChromaDB rebuild runs in background so healthcheck passes immediately
    async def _rebuild_chroma():
        try:
            from app.rag.indexer import ensure_chroma_populated
            await ensure_chroma_populated()
        except Exception:
            logger.exception("Background ChromaDB rebuild failed")

    asyncio.create_task(_rebuild_chroma())

    # RAG pipeline initialises immediately (ChromaDB may still be rebuilding)
    try:
        from app.rag.chain import RAGPipeline

        app.state.pipeline = RAGPipeline()
        logger.info("RAG pipeline initialised")
    except Exception:
        logger.exception("Failed to initialise RAG pipeline")
        app.state.pipeline = None

    yield

    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Python Programming Q&A Assistant",
        description=(
            "RAG-powered question answering over the Stack Overflow Python "
            "Q&A dataset. Built for the Analytics Vidhya AI Engineer assessment."
        ),
        version="1.0.0",
        lifespan=lifespan,
        # Swagger / ReDoc / OpenAPI schema are blocked in production
        docs_url=None if IS_PROD else "/docs",
        redoc_url=None if IS_PROD else "/redoc",
        openapi_url=None if IS_PROD else "/openapi.json",
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=IS_PROD,   # only send credentials header in production
        allow_methods=["GET", "POST", "PATCH", "DELETE"] if IS_PROD else ["*"],
        allow_headers=["Authorization", "Content-Type"] if IS_PROD else ["*"],
    )

    app.include_router(auth.router)
    app.include_router(routes.router)
    app.include_router(sessions.router)
    return app


app = create_app()
