"""
Cortex: ASI-themed neural study interface for CCNA mastery.

This is the main product - a CLI-based adaptive learning system.

Components:
- atoms: Modular question type handlers (MCQ, Parsons, Numeric, etc.)
- session: Interactive study session runner with NCDE integration
- session_store: Session persistence for save/resume functionality
"""

from .atoms import AtomType, HANDLERS, get_handler
from .session import CortexSession
from .session_store import SessionStore, SessionState, create_session_state

# Supported types derived from registered handlers
CORTEX_SUPPORTED_TYPES = list(HANDLERS.keys())

__all__ = [
    "AtomType",
    "HANDLERS",
    "get_handler",
    "CortexSession",
    "CORTEX_SUPPORTED_TYPES",
    "SessionStore",
    "SessionState",
    "create_session_state",
]
