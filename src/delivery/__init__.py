"""
The Cortex: Standalone CCNA Learning CLI.

A portable, database-free CLI for interleaved spaced repetition study
using the generated CCNA learning atoms.

Components:
- AtomDeck: JSON loading and atom management
- SM2Scheduler: Spaced repetition algorithm
- InterleaveScheduler: Context-switching for optimal learning
- SessionTelemetry: Tracking and fatigue detection
- SocraticTutor: LLM-powered tutoring interventions
- StateStore: SQLite persistence
- CortexCLI: Main terminal interface
"""

from .atom_deck import Atom, AtomDeck
from .scheduler import InterleaveScheduler, SM2Scheduler, StudySession
from .state_store import ReviewRecord, SM2State, StateStore
from .telemetry import FatigueDetector, FatigueSignal, SessionTelemetry
from .tutor import SocraticTutor, get_socratic_guidance

__all__ = [
    # Atom loading
    "AtomDeck",
    "Atom",
    # Persistence
    "StateStore",
    "ReviewRecord",
    "SM2State",
    # Scheduling
    "SM2Scheduler",
    "InterleaveScheduler",
    "StudySession",
    # Telemetry
    "SessionTelemetry",
    "FatigueDetector",
    "FatigueSignal",
    # Tutoring
    "SocraticTutor",
    "get_socratic_guidance",
]
