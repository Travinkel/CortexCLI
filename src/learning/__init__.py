"""
Learning: Core domain for adaptive learning system.

This package contains the learning science logic:
- scheduler: FSRS + interleaving for optimal review timing
- diagnosis: NCDE cognitive diagnosis (encoding, retrieval errors)
- persona: Learner classification and adaptation
- remediation: Struggle-based routing and intervention
- models: Domain models (Atom, MasteryState, LearnerProfile)
"""

# Re-export key components for convenience
from src.adaptive.ncde_pipeline import NCDEPipeline, SessionContext, create_raw_event
from src.adaptive.neuro_model import CognitiveDiagnosis, FailMode
from src.adaptive.persona_service import PersonaService
from src.adaptive.scheduler_rl import PREREQUISITE_THRESHOLD
from src.study.study_service import StudyService

__all__ = [
    # Pipeline
    "NCDEPipeline",
    "SessionContext",
    "create_raw_event",
    # Diagnosis
    "CognitiveDiagnosis",
    "FailMode",
    # Persona
    "PersonaService",
    # Scheduler
    "PREREQUISITE_THRESHOLD",
    # Study
    "StudyService",
]
