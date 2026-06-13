import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import get_settings

logger = logging.getLogger("ttapi")

_client: AsyncIOMotorClient | None = None


async def connect_db() -> None:
    global _client
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    # Ping to verify connection
    await _client.admin.command("ping")
    logger.info("MongoDB connected to database: %s", settings.mongodb_db_name)


async def close_db() -> None:
    global _client
    if _client:
        _client.close()
        _client = None
        logger.info("MongoDB connection closed")


def get_db() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("MongoDB client is not initialised")
    settings = get_settings()
    return _client[settings.mongodb_db_name]
