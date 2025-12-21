"""
ETL Pipeline for Learning Content.

This module provides a pluggable ETL (Extract-Transform-Load) architecture
for ingesting learning content from multiple sources (CCNA, Security, PROG, etc.)
and transforming it into DARPA-class learning atoms.

Architecture:
    Extractors (plugins) -> Transformers (chain) -> Loaders (database)

Key Principles:
    - Open/Closed: Add new content sources without modifying existing code
    - Single Responsibility: Each component has one job
    - Strategy Pattern: Swappable transformers and loaders

Example:
    from src.etl import Pipeline, PipelineBuilder
    from src.etl.extractors import CCNAExtractor
    from src.etl.transformers import ICAPClassifier
    from src.etl.loaders import AtomLoader

    pipeline = (
        PipelineBuilder()
        .extract_from(CCNAExtractor(module_path))
        .transform_with(ICAPClassifier())
        .load_to(AtomLoader(db_session))
        .build()
    )

    result = await pipeline.run()
"""

from .pipeline import Pipeline, PipelineResult, PipelineBuilder
from .models import (
    RawChunk,
    TransformedAtom,
    AtomEnvelope,
    AtomContent,
    GradingLogic,
    EngagementMode,
    KnowledgeDimension,
    GradingMode,
    AtomOwner,
)

__all__ = [
    # Pipeline
    "Pipeline",
    "PipelineResult",
    "PipelineBuilder",
    # Models
    "RawChunk",
    "TransformedAtom",
    "AtomEnvelope",
    "AtomContent",
    "GradingLogic",
    # Enums
    "EngagementMode",
    "KnowledgeDimension",
    "GradingMode",
    "AtomOwner",
]
