"""
Core Module - Shared domain models and interfaces.

This module contains the canonical implementations of core concepts
that are used across multiple modules (adaptive, study, quiz, etc.).

Components:
- mastery: Unified mastery calculation (ConceptMastery, MasteryCalculator)
- atom: Canonical atom representation (LearningAtom, AtomType)
- quiz: Quiz interfaces (IQuizRunner, IQuestionSelector)
- modes: Operating mode configuration (API, Pipeline, Offline)
- platform_client: Right-learning platform integration

Design Principle:
All domain-specific modules (src/adaptive/, src/study/, src/quiz/)
should import from src/core/ rather than reimplementing shared concepts.

Operating Modes (cortex-cli):
- API: Connected to right-learning platform
- Pipeline: CI/CD content validation
- Offline: Local-only, air-gapped operation
"""

from src.core.mastery import (
    ConceptMastery,
    MasteryCalculator,
    MasteryLevel,
    SimpleMasteryCalculator,
)

# Lazy imports for modes (optional dependency)
try:
    from src.core.modes import (
        ApiConfig,
        CortexCliConfig,
        ModeContext,
        ModeStrategy,
        OfflineConfig,
        OperatingMode,
        PipelineConfig,
        detect_mode,
        get_mode_strategy,
    )
    from src.core.platform_client import AuthResult, PlatformClient, SyncResult

    _MODES_AVAILABLE = True
except ImportError:
    _MODES_AVAILABLE = False

__all__ = [
    # Mastery
    "ConceptMastery",
    "MasteryLevel",
    "MasteryCalculator",
    "SimpleMasteryCalculator",
]

# Extend exports if modes are available
if _MODES_AVAILABLE:
    __all__.extend([
        # Modes
        "OperatingMode",
        "ApiConfig",
        "PipelineConfig",
        "OfflineConfig",
        "CortexCliConfig",
        "ModeContext",
        "ModeStrategy",
        "detect_mode",
        "get_mode_strategy",
        # Platform Client
        "PlatformClient",
        "AuthResult",
        "SyncResult",
    ])
