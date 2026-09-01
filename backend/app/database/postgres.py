"""
Async PostgreSQL engine and session management for VisionRAG-X.
Uses SQLAlchemy 2.x asyncio extension with asyncpg driver.
"""
import asyncio
import logging
import time
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

engine: AsyncEngine = create_async_engine(
    settings.postgres_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

AsyncSessionLocal = async_session



# ---------------------------------------------------------------------------
# Declarative base (imported by all ORM models)
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session; roll back and close on any error."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

async def init_db() -> None:
    """Create all tables if they do not already exist."""
    # Import models here so that Base.metadata is populated before create_all.
    from app.knowledge import models  # noqa: F401  # side-effect import

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialised.")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

async def check_db_health() -> dict:
    """
    Return a health dict compatible with ComponentStatus.

    Retries up to 3 times with exponential backoff before reporting failure.
    """
    last_error: str | None = None

    for attempt in range(1, 4):
        try:
            t0 = time.monotonic()
            async with async_session() as session:
                await session.execute(text("SELECT 1"))
            latency_ms = (time.monotonic() - t0) * 1000
            return {
                "available": True,
                "latency_ms": round(latency_ms, 2),
                "error": None,
            }
        except OperationalError as exc:
            last_error = str(exc.__cause__ or exc)
            logger.warning(
                "DB health check attempt %d/3 failed: %s", attempt, last_error
            )
            if attempt < 3:
                await asyncio.sleep(2 ** (attempt - 1))  # 1s, 2s
        except Exception as exc:
            last_error = str(exc)
            logger.error("Unexpected DB error on attempt %d/3: %s", attempt, last_error)
            if attempt < 3:
                await asyncio.sleep(2 ** (attempt - 1))

    return {
        "available": False,
        "latency_ms": None,
        "error": last_error,
    }
