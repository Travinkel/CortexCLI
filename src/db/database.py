from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from config import get_settings
from src.db.models.base import Base

settings = get_settings()

# Sync engine/session
engine = create_engine(settings.database_url, echo=settings.log_level == "DEBUG", pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_engine():
    """Get the database engine."""
    return engine


def _get_async_url(url: str) -> str:
    """Convert sync postgres URL to asyncpg URL when needed."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")


def run_migration(migration_file: Path) -> None:
    """Run a SQL migration file."""
    if not migration_file.exists():
        raise FileNotFoundError(f"Migration file not found: {migration_file}")

    sql = migration_file.read_text(encoding="utf-8")
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    logger.info(f"Migration applied: {migration_file.name}")


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:  # Intentionally broad - rollback on any error before re-raising
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# Alias for compatibility
get_db = get_session

# ========================================
# Async Support
# ========================================

_async_engine = None
_AsyncSessionLocal = None


def _get_async_engine():
    """Get or create async engine (lazy initialization)."""
    global _async_engine
    if _async_engine is None:
        async_url = _get_async_url(settings.database_url)
        _async_engine = create_async_engine(
            async_url,
            echo=settings.log_level == "DEBUG",
            pool_pre_ping=True,
        )
    return _async_engine


def _get_async_session_factory():
    """Get or create async session factory."""
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            bind=_get_async_engine(),
            class_=AsyncSession,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _AsyncSessionLocal


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for async database sessions."""
    factory = _get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:  # Intentionally broad - rollback on any error before re-raising
            await session.rollback()
            raise


@asynccontextmanager
async def async_session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async transactional scope around a series of operations."""
    factory = _get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:  # Intentionally broad - rollback on any error before re-raising
            await session.rollback()
            raise


# --------------------------------------------------
# Data integrity validation
# Validates mastery counts match actual atom counts. Run via CLI or tests.
# --------------------------------------------------
def validate_mastery_counts() -> dict[str, Any]:
    """
    Validate ccna_section_mastery.atoms_total matches actual linked atom counts.

    Returns dict with:
        - valid: bool - True if all counts match
        - mismatches: list of {section_id, claimed, actual} for any mismatches
        - error: str if validation failed to run
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT
                        csm.section_id,
                        csm.atoms_total AS claimed,
                        COALESCE(sub.actual_count, 0) AS actual
                    FROM ccna_section_mastery csm
                    LEFT JOIN (
                        SELECT ccna_section_id AS section_id, COUNT(*) AS actual_count
                        FROM learning_atoms
                        WHERE ccna_section_id IS NOT NULL
                        GROUP BY ccna_section_id
                    ) AS sub ON csm.section_id = sub.section_id
                    WHERE csm.atoms_total != COALESCE(sub.actual_count, 0)
                    """
                )
            )
            mismatches = [
                {"section_id": row[0], "claimed": row[1], "actual": row[2]}
                for row in result.fetchall()
            ]
            return {
                "valid": len(mismatches) == 0,
                "mismatches": mismatches,
            }
    except Exception as e:
        logger.warning(f"Mastery count validation failed: {e}")
        return {"valid": False, "error": str(e), "mismatches": []}
