"""
Session state persistence for Cortex study sessions.

Enables save/resume functionality so users can interrupt and continue sessions.
Sessions are stored as JSON files in ~/.cortex/sessions/
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import uuid


# Default session directory
SESSION_DIR = Path.home() / ".cortex" / "sessions"


@dataclass
class SessionState:
    """Serializable session state."""

    session_id: str
    started_at: str  # ISO format
    last_saved_at: str  # ISO format
    mode: str  # 'adaptive', 'war', 'manual'
    modules: list[int]
    limit: int

    # Progress tracking
    atoms_completed: list[str]  # atom IDs
    atoms_remaining: list[str]  # atom IDs in queue order
    correct: int = 0
    incorrect: int = 0
    current_index: int = 0

    # Optional state
    war_mode: bool = False
    struggle_focus: list[str] = field(default_factory=list)

    # Expiry - sessions older than this are considered stale
    expiry_hours: int = 24

    def is_expired(self) -> bool:
        """Check if session has expired."""
        last_saved = datetime.fromisoformat(self.last_saved_at)
        return datetime.now() - last_saved > timedelta(hours=self.expiry_hours)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        """Create from dictionary."""
        return cls(**data)


class SessionStore:
    """
    Manages session persistence.

    Sessions are stored as JSON files with naming: {session_id}.json
    Only the most recent session is typically used for resume.
    """

    def __init__(self, session_dir: Optional[Path] = None):
        self.session_dir = session_dir or SESSION_DIR
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def save(self, state: SessionState) -> Path:
        """Save session state to disk."""
        state.last_saved_at = datetime.now().isoformat()
        filepath = self.session_dir / f"{state.session_id}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2)

        return filepath

    def load(self, session_id: str) -> Optional[SessionState]:
        """Load a specific session by ID."""
        filepath = self.session_dir / f"{session_id}.json"
        if not filepath.exists():
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return SessionState.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def get_latest(self) -> Optional[SessionState]:
        """Get the most recent non-expired session."""
        sessions = []

        for filepath in self.session_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                state = SessionState.from_dict(data)
                if not state.is_expired():
                    sessions.append((state, filepath))
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

        if not sessions:
            return None

        # Sort by last_saved_at descending
        sessions.sort(key=lambda x: x[0].last_saved_at, reverse=True)
        return sessions[0][0]

    def delete(self, session_id: str) -> bool:
        """Delete a session file."""
        filepath = self.session_dir / f"{session_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def cleanup_expired(self) -> int:
        """Remove all expired session files."""
        removed = 0
        for filepath in self.session_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                state = SessionState.from_dict(data)
                if state.is_expired():
                    filepath.unlink()
                    removed += 1
            except (json.JSONDecodeError, KeyError, TypeError):
                # Remove corrupted files
                filepath.unlink()
                removed += 1

        return removed

    def list_sessions(self) -> list[SessionState]:
        """List all non-expired sessions."""
        sessions = []
        for filepath in self.session_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                state = SessionState.from_dict(data)
                if not state.is_expired():
                    sessions.append(state)
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

        return sorted(sessions, key=lambda x: x.last_saved_at, reverse=True)


def create_session_state(
    modules: list[int],
    limit: int,
    war_mode: bool = False,
    atom_ids: Optional[list[str]] = None,
) -> SessionState:
    """Create a new session state."""
    now = datetime.now().isoformat()
    return SessionState(
        session_id=str(uuid.uuid4())[:8],
        started_at=now,
        last_saved_at=now,
        mode="war" if war_mode else "adaptive",
        modules=modules,
        limit=limit,
        atoms_completed=[],
        atoms_remaining=atom_ids or [],
        war_mode=war_mode,
    )
