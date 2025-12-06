"""
Staging table models for raw Notion data.

These tables hold the raw JSONB from Notion API responses.
They are ephemeral and can be rebuilt from Notion at any time.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class StgNotionFlashcard(Base):
    """Raw flashcard data from Notion."""

    __tablename__ = "stg_notion_flashcards"

    notion_page_id: Mapped[str] = mapped_column(Text, primary_key=True)
    raw_properties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    raw_content: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    last_synced_at: Mapped[datetime] = mapped_column(default=func.now())
    sync_hash: Mapped[str | None] = mapped_column(Text)


class StgNotionConcept(Base):
    """Raw concept (subconcept) data from Notion."""

    __tablename__ = "stg_notion_concepts"

    notion_page_id: Mapped[str] = mapped_column(Text, primary_key=True)
    raw_properties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    parent_type: Mapped[str | None] = mapped_column(Text)  # 'area', 'cluster', or NULL
    parent_notion_id: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime] = mapped_column(default=func.now())


class StgNotionConceptArea(Base):
    """Raw concept area (L0) data from Notion."""

    __tablename__ = "stg_notion_concept_areas"

    notion_page_id: Mapped[str] = mapped_column(Text, primary_key=True)
    raw_properties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(default=func.now())


class StgNotionConceptCluster(Base):
    """Raw concept cluster (L1) data from Notion."""

    __tablename__ = "stg_notion_concept_clusters"

    notion_page_id: Mapped[str] = mapped_column(Text, primary_key=True)
    raw_properties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    parent_area_notion_id: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime] = mapped_column(default=func.now())


class StgNotionModule(Base):
    """Raw module data from Notion."""

    __tablename__ = "stg_notion_modules"

    notion_page_id: Mapped[str] = mapped_column(Text, primary_key=True)
    raw_properties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(default=func.now())


class StgNotionTrack(Base):
    """Raw track data from Notion."""

    __tablename__ = "stg_notion_tracks"

    notion_page_id: Mapped[str] = mapped_column(Text, primary_key=True)
    raw_properties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(default=func.now())


class StgNotionProgram(Base):
    """Raw program data from Notion."""

    __tablename__ = "stg_notion_programs"

    notion_page_id: Mapped[str] = mapped_column(Text, primary_key=True)
    raw_properties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(default=func.now())
