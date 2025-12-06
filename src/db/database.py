"""
Database connection and session management.

Uses SQLAlchemy 2.0 with PostgreSQL.
Supports both sync and async sessions.
"""
from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import AsyncGenerator, Generator

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from config import get_settings
from .models import Base

settings = get_settings()

# Convert sync URL to async URL
def _get_async_url(sync_url: str) -> str:
    """Convert synchronous database URL to async URL."""
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif sync_url.startswith("postgresql+psycopg2://"):
        return sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    return sync_url

# Create engine
engine = create_engine(
    settings.database_url,
    echo=settings.log_level == "DEBUG",
    pool_pre_ping=True,  # Verify connections before using
)

# Session factory
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Initialize database tables.

    Creates all tables if they don't exist.
    For production, use Alembic migrations instead.
    """
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
    """Provide a transactional scope around a series of operations.

    Usage:
        with session_scope() as session:
            session.add(entity)
            # Commits automatically on success, rollbacks on exception
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions.

    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_session)):
            return db.query(Item).all()
    """
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

# Create async engine (lazy initialization to avoid import errors when asyncpg not installed)
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
    """FastAPI dependency for async database sessions.

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_async_session)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    factory = _get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def async_session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async transactional scope around a series of operations.

    Usage:
        async with async_session_scope() as session:
            await session.add(entity)
            # Commits automatically on success, rollbacks on exception
    """
    factory = _get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
