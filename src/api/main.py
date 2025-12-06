"""
FastAPI application for notion-learning-sync.

Provides REST API for:
- Notion sync operations
- Content cleaning pipeline
- Review queue management
- Anki integration
- Content access and export
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from config import get_settings
from src.db.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    logger.info("Starting notion-learning-sync service...")
    init_db()
    logger.info(f"Service started on {settings.api_host}:{settings.api_port}")

    yield

    # Shutdown
    logger.info("Shutting down notion-learning-sync service...")


app = FastAPI(
    title="Notion Learning Sync",
    description="""
    Content synchronization and cleaning service for learning systems.

    ## Features

    - **Notion Sync**: Sync flashcards, concepts, modules, tracks, and programs from Notion
    - **Content Cleaning**: Atomicity validation, duplicate detection, AI rewriting
    - **Review Queue**: Manual approval workflow for AI-generated content
    - **Anki Integration**: Bidirectional sync with Anki (push cards, pull review stats)
    - **Export API**: Clean data access for right-learning and other consumers

    ## Data Flow

    ```
    Notion (Source of Truth)
        ↓ sync
    Staging Tables (raw)
        ↓ cleaning pipeline
    Canonical Tables (clean)
        ↓
    Anki / Personal Use / Right-Learning ETL
    ```
    """,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========================================
# Health & Status Endpoints
# ========================================


@app.get("/", tags=["Health"])
def root() -> dict[str, str]:
    """Root endpoint returning service info."""
    return {
        "service": "notion-learning-sync",
        "version": "0.1.0",
        "status": "ok",
    }


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, Any]:
    """Comprehensive health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": "ok",  # TODO: Add actual DB check
            "notion": "configured" if settings.notion_api_key else "not_configured",
            "anki": "configured",  # TODO: Add AnkiConnect ping
            "ai": "configured" if settings.has_ai_configured() else "not_configured",
        },
        "config": {
            "protect_notion": settings.protect_notion,
            "dry_run": settings.dry_run,
            "configured_databases": list(settings.get_configured_notion_databases().keys()),
        },
    }


@app.get("/config", tags=["Health"])
def get_config() -> dict[str, Any]:
    """Get current configuration (non-sensitive)."""
    return {
        "database_url": settings.database_url.split("@")[-1] if "@" in settings.database_url else "configured",
        "notion": {
            "configured": bool(settings.notion_api_key),
            "databases": settings.get_configured_notion_databases(),
        },
        "anki": {
            "connect_url": settings.anki_connect_url,
            "deck_name": settings.anki_deck_name,
            "note_type": settings.anki_note_type,
        },
        "ai": {
            "gemini_configured": bool(settings.gemini_api_key),
            "vertex_configured": bool(settings.vertex_project),
            "model": settings.ai_model,
        },
        "atomicity": {
            "front_max_words": settings.atomicity_front_max_words,
            "back_optimal_words": settings.atomicity_back_optimal_words,
            "back_warning_words": settings.atomicity_back_warning_words,
            "back_max_chars": settings.atomicity_back_max_chars,
            "mode": settings.atomicity_mode,
        },
        "semantic": settings.get_semantic_config(),
        "prerequisites": settings.get_prerequisite_config(),
        "quiz": settings.get_quiz_config(),
        "knowledge_thresholds": settings.get_knowledge_thresholds(),
        "sync": {
            "interval_minutes": settings.sync_interval_minutes,
            "protect_notion": settings.protect_notion,
            "dry_run": settings.dry_run,
        },
    }


# ========================================
# Import and mount routers
# ========================================

from src.api.routers import (
    anki_router,
    cleaning_router,
    content_router,
    review_router,
    semantic_router,
    sync_router,
    prerequisites_router,
    quiz_router,
    ccna_router,
    adaptive_router,
)

app.include_router(sync_router.router, prefix="/api/sync", tags=["Sync"])
app.include_router(anki_router.router, prefix="/api/anki", tags=["Anki"])
app.include_router(content_router.router, prefix="/api/content", tags=["Content"])
app.include_router(cleaning_router.router, prefix="/api/clean", tags=["Cleaning"])
app.include_router(review_router.router, prefix="/api/review", tags=["Review"])
app.include_router(semantic_router.router, prefix="/api/semantic", tags=["Semantic"])
app.include_router(prerequisites_router.router, prefix="/api/prerequisites", tags=["Prerequisites"])
app.include_router(quiz_router.router, prefix="/api/quiz", tags=["Quiz"])
app.include_router(ccna_router.router, prefix="/api/ccna", tags=["CCNA Generation"])
app.include_router(adaptive_router.router, prefix="/api/adaptive", tags=["Adaptive Learning"])
