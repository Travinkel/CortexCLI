"""
Prerequisites module for soft/hard gating.

This module provides:
- PrerequisiteService: CRUD operations and tag parsing
- GatingService: Access evaluation and waiver management

Gating Types:
- soft: Warning shown but access allowed
- hard: Access blocked until mastery threshold met

Mastery Thresholds:
- foundation: 0.40
- integration: 0.65 (default)
- mastery: 0.85
"""

from .gating_service import GatingService
from .prerequisite_service import PrerequisiteService

__all__ = [
    "PrerequisiteService",
    "GatingService",
]
