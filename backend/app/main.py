import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ttapi")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the RAG pipeline once at startup; never crash the app if it
    fails (health endpoint stays up and reports degraded state)."""
    try:
        from app.rag.chain import RAGPipeline

        app.state.pipeline = RAGPipeline()
        logger.info("RAG pipeline initialised")
    except Exception:  # noqa: BLE001
        logger.exception("Failed to initialise RAG pipeline")
        app.state.pipeline = None
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Python Programming Q&A Assistant",
        description=(
            "RAG-powered question answering over the Stack Overflow Python "
            "Q&A dataset. Built for the Analytics Vidhya AI Engineer assessment."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
