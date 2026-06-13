from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    google_api_key: str = ""
    generation_model: str = "gemini-2.5-flash"
    embedding_model: str = "models/gemini-embedding-001"

    chroma_dir: str = str(BACKEND_DIR / "chroma_db")
    chroma_collection: str = "python_qa"

    retrieval_k: int = 5
    # Cosine distance above this is treated as "no relevant context found".
    max_relevance_distance: float = 0.60

    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
