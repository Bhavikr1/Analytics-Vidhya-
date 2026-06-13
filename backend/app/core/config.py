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

    environment: str  # "development" | "production"

    google_api_key: str
    generation_model: str
    embedding_model: str

    chroma_dir: str
    chroma_collection: str

    retrieval_k: int
    max_relevance_distance: float

    cors_origins: str

    mongodb_uri: str
    mongodb_db_name: str

    auth_username: str
    auth_password: str
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_access_token_expire_minutes: int

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
