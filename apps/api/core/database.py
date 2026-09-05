"""Database initialization and session management."""
from typing import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# Async engine for application queries
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.app_debug,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


async def init_db() -> None:
    """Initialize database connection pool."""
    try:
        async with engine.begin() as conn:
            # Test connection
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
        logger.info("database.connected", url=_mask_db_url(settings.database_url))
    except Exception as e:
        logger.error("database.connection_failed", error=str(e))
        raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def _mask_db_url(url: str) -> str:
    """Mask password in database URL for logging."""
    if "@" in url:
        prefix = url.split("@")[0]
        suffix = url.split("@")[1]
        if ":" in prefix:
            parts = prefix.rsplit(":", 1)
            return f"{parts[0]}:***@{suffix}"
    return url
