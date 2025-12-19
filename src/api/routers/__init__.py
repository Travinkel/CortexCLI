"""API routers for notion-learning-sync."""

from src.api.routers import (
    adaptive_router,
    anki_router,
    ccna_router,
    cleaning_router,
    prerequisites_router,
    quiz_router,
    semantic_router,
    sync_router,
)

__all__ = [
    "sync_router",
    "cleaning_router",
    "anki_router",
    "semantic_router",
    "prerequisites_router",
    "quiz_router",
    "ccna_router",
    "adaptive_router",
]
