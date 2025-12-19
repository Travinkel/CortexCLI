"""
SQLite State Store for Cortex.

Provides portable persistence for:
- SM-2 spaced repetition state per atom
- Review history log for analytics
- Session history for fatigue patterns

Database location: ~/.cortex/state.db
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from loguru import logger

# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SM2State:
    """SM-2 algorithm state for a single atom."""

    atom_id: str
    easiness_factor: float = 2.5  # EF starts at 2.5
    interval_days: int = 1  # Days until next review
    repetitions: int = 0  # Consecutive correct answers
    next_review: date | None = None
    last_reviewed: datetime | None = None

    @property
    def is_due(self) -> bool:
        """Check if this atom is due for review."""
        if self.next_review is None:
            return True  # Never reviewed = due
        return date.today() >= self.next_review

    @property
    def days_overdue(self) -> int:
        """Days past the scheduled review date."""
        if self.next_review is None:
            return 0
        delta = date.today() - self.next_review
        return max(0, delta.days)


@dataclass
class ReviewRecord:
    """A single review event."""

    id: int
    atom_id: str
    reviewed_at: datetime
    grade: int  # 0-5 SM-2 scale
    response_ms: int  # Time to answer
    confidence: int | None = None  # Self-reported 1-5


@dataclass
class SessionRecord:
    """A study session summary."""

    id: int
    started_at: datetime
    ended_at: datetime | None
    atoms_reviewed: int
    accuracy: float
    fatigue_detected: bool


# =============================================================================
# State Store
# =============================================================================


class StateStore:
    """
    SQLite-backed state persistence for the Cortex.

    Handles:
    - SM-2 state per atom (easiness, interval, repetitions)
    - Review log with timing and confidence
    - Session history for pattern analysis
    """

    DEFAULT_DB_PATH = Path.home() / ".cortex" / "state.db"

    def __init__(self, db_path: Path | None = None):
        """
        Initialize the state store.

        Args:
            db_path: Custom database path (defaults to ~/.cortex/state.db)
        """
        self.db_path = db_path or self.DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn: sqlite3.Connection | None = None
        self._init_schema()

        logger.info(f"StateStore initialized at {self.db_path}")

    @property
    def conn(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path), detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_schema(self) -> None:
        """Initialize database schema."""
        cursor = self.conn.cursor()

        # SM-2 state per atom
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sm2_state (
                atom_id TEXT PRIMARY KEY,
                easiness_factor REAL DEFAULT 2.5,
                interval_days INTEGER DEFAULT 1,
                repetitions INTEGER DEFAULT 0,
                next_review DATE,
                last_reviewed TIMESTAMP
            )
        """)

        # Review history log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                atom_id TEXT NOT NULL,
                reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                grade INTEGER NOT NULL,
                response_ms INTEGER,
                confidence INTEGER,
                FOREIGN KEY (atom_id) REFERENCES sm2_state(atom_id)
            )
        """)

        # Session history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TIMESTAMP NOT NULL,
                ended_at TIMESTAMP,
                atoms_reviewed INTEGER DEFAULT 0,
                accuracy REAL DEFAULT 0.0,
                fatigue_detected BOOLEAN DEFAULT 0
            )
        """)

        # Index for fast due-date queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sm2_next_review
            ON sm2_state(next_review)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_review_log_atom
            ON review_log(atom_id)
        """)

        self.conn.commit()

    # =========================================================================
    # SM-2 State Operations
    # =========================================================================

    def get_sm2_state(self, atom_id: str) -> SM2State:
        """
        Get SM-2 state for an atom.

        Args:
            atom_id: The atom identifier

        Returns:
            SM2State (default values if not found)
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM sm2_state WHERE atom_id = ?", (atom_id,))
        row = cursor.fetchone()

        if row is None:
            return SM2State(atom_id=atom_id)

        return SM2State(
            atom_id=row["atom_id"],
            easiness_factor=row["easiness_factor"],
            interval_days=row["interval_days"],
            repetitions=row["repetitions"],
            next_review=row["next_review"],
            last_reviewed=row["last_reviewed"],
        )

    def save_sm2_state(self, state: SM2State) -> None:
        """
        Save or update SM-2 state for an atom.

        Args:
            state: SM2State to persist
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO sm2_state (
                atom_id, easiness_factor, interval_days,
                repetitions, next_review, last_reviewed
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(atom_id) DO UPDATE SET
                easiness_factor = excluded.easiness_factor,
                interval_days = excluded.interval_days,
                repetitions = excluded.repetitions,
                next_review = excluded.next_review,
                last_reviewed = excluded.last_reviewed
        """,
            (
                state.atom_id,
                state.easiness_factor,
                state.interval_days,
                state.repetitions,
                state.next_review,
                state.last_reviewed,
            ),
        )
        self.conn.commit()

    def get_due_atom_ids(self, limit: int = 100) -> list[str]:
        """
        Get atom IDs that are due for review.

        Args:
            limit: Maximum atoms to return

        Returns:
            List of atom IDs due today or earlier
        """
        cursor = self.conn.cursor()
        today = date.today()

        cursor.execute(
            """
            SELECT atom_id FROM sm2_state
            WHERE next_review <= ?
            ORDER BY next_review ASC, interval_days ASC
            LIMIT ?
        """,
            (today, limit),
        )

        return [row["atom_id"] for row in cursor.fetchall()]

    def get_reviewed_atom_ids(self) -> set[str]:
        """
        Get all atom IDs that have been reviewed at least once.

        Returns:
            Set of atom IDs with review history
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT atom_id FROM sm2_state")
        return {row["atom_id"] for row in cursor.fetchall()}

    def count_due_atoms(self) -> int:
        """Count atoms due for review today."""
        cursor = self.conn.cursor()
        today = date.today()
        cursor.execute("SELECT COUNT(*) as cnt FROM sm2_state WHERE next_review <= ?", (today,))
        return cursor.fetchone()["cnt"]

    # =========================================================================
    # Review Log Operations
    # =========================================================================

    def log_review(
        self,
        atom_id: str,
        grade: int,
        response_ms: int,
        confidence: int | None = None,
    ) -> int:
        """
        Log a review event.

        Args:
            atom_id: The reviewed atom
            grade: SM-2 grade (0-5)
            response_ms: Time to answer in milliseconds
            confidence: Optional self-reported confidence (1-5)

        Returns:
            Review record ID
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO review_log (atom_id, grade, response_ms, confidence)
            VALUES (?, ?, ?, ?)
        """,
            (atom_id, grade, response_ms, confidence),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_review_history(
        self,
        atom_id: str,
        limit: int = 10,
    ) -> list[ReviewRecord]:
        """
        Get review history for an atom.

        Args:
            atom_id: The atom to query
            limit: Maximum records to return

        Returns:
            List of ReviewRecords, most recent first
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM review_log
            WHERE atom_id = ?
            ORDER BY reviewed_at DESC
            LIMIT ?
        """,
            (atom_id, limit),
        )

        return [
            ReviewRecord(
                id=row["id"],
                atom_id=row["atom_id"],
                reviewed_at=row["reviewed_at"],
                grade=row["grade"],
                response_ms=row["response_ms"],
                confidence=row["confidence"],
            )
            for row in cursor.fetchall()
        ]

    def get_recent_reviews(self, limit: int = 50) -> list[ReviewRecord]:
        """Get most recent reviews across all atoms."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM review_log
            ORDER BY reviewed_at DESC
            LIMIT ?
        """,
            (limit,),
        )

        return [
            ReviewRecord(
                id=row["id"],
                atom_id=row["atom_id"],
                reviewed_at=row["reviewed_at"],
                grade=row["grade"],
                response_ms=row["response_ms"],
                confidence=row["confidence"],
            )
            for row in cursor.fetchall()
        ]

    # =========================================================================
    # Session Operations
    # =========================================================================

    def start_session(self) -> int:
        """
        Start a new study session.

        Returns:
            Session ID
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO session_history (started_at, atoms_reviewed, accuracy)
            VALUES (?, 0, 0.0)
        """,
            (datetime.now(),),
        )
        self.conn.commit()
        return cursor.lastrowid

    def end_session(
        self,
        session_id: int,
        atoms_reviewed: int,
        accuracy: float,
        fatigue_detected: bool = False,
    ) -> None:
        """
        End a study session with summary stats.

        Args:
            session_id: The session to close
            atoms_reviewed: Total atoms reviewed
            accuracy: Fraction of correct answers
            fatigue_detected: Whether fatigue signals were detected
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE session_history SET
                ended_at = ?,
                atoms_reviewed = ?,
                accuracy = ?,
                fatigue_detected = ?
            WHERE id = ?
        """,
            (datetime.now(), atoms_reviewed, accuracy, fatigue_detected, session_id),
        )
        self.conn.commit()

    def get_session_history(self, limit: int = 30) -> list[SessionRecord]:
        """Get recent session history."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM session_history
            ORDER BY started_at DESC
            LIMIT ?
        """,
            (limit,),
        )

        return [
            SessionRecord(
                id=row["id"],
                started_at=row["started_at"],
                ended_at=row["ended_at"],
                atoms_reviewed=row["atoms_reviewed"],
                accuracy=row["accuracy"],
                fatigue_detected=bool(row["fatigue_detected"]),
            )
            for row in cursor.fetchall()
        ]

    # =========================================================================
    # Stats & Analytics
    # =========================================================================

    def get_stats(self) -> dict:
        """
        Get overall learning statistics.

        Returns:
            Dictionary with aggregate stats
        """
        cursor = self.conn.cursor()

        # Total atoms tracked
        cursor.execute("SELECT COUNT(*) as cnt FROM sm2_state")
        total_atoms = cursor.fetchone()["cnt"]

        # Due atoms
        today = date.today()
        cursor.execute("SELECT COUNT(*) as cnt FROM sm2_state WHERE next_review <= ?", (today,))
        due_atoms = cursor.fetchone()["cnt"]

        # Total reviews
        cursor.execute("SELECT COUNT(*) as cnt FROM review_log")
        total_reviews = cursor.fetchone()["cnt"]

        # Average grade (last 100 reviews)
        cursor.execute("""
            SELECT AVG(grade) as avg_grade FROM (
                SELECT grade FROM review_log ORDER BY reviewed_at DESC LIMIT 100
            )
        """)
        avg_grade = cursor.fetchone()["avg_grade"] or 0

        # Sessions completed
        cursor.execute("SELECT COUNT(*) as cnt FROM session_history WHERE ended_at IS NOT NULL")
        sessions = cursor.fetchone()["cnt"]

        # Retention rate (grade >= 3 is passing)
        cursor.execute("""
            SELECT
                COUNT(CASE WHEN grade >= 3 THEN 1 END) * 100.0 / COUNT(*) as retention
            FROM (
                SELECT grade FROM review_log ORDER BY reviewed_at DESC LIMIT 100
            )
        """)
        row = cursor.fetchone()
        retention = row["retention"] if row["retention"] else 0

        return {
            "total_atoms_tracked": total_atoms,
            "atoms_due": due_atoms,
            "total_reviews": total_reviews,
            "avg_grade_recent": round(avg_grade, 2),
            "retention_rate_percent": round(retention, 1),
            "sessions_completed": sessions,
        }

    def reset(self, module_filter: int | None = None, force: bool = False) -> int:
        """
        Reset review state (for testing or fresh start).

        DANGER: This deletes your learning progress! A backup is created first.

        Args:
            module_filter: If provided, only reset atoms from this module
            force: If True, skip confirmation prompt (use with caution!)

        Returns:
            Number of atoms reset
        """
        import json
        from datetime import datetime

        cursor = self.conn.cursor()

        # Count what will be deleted
        if module_filter is not None:
            pattern = f"M{module_filter}-%"
            cursor.execute("SELECT COUNT(*) FROM sm2_state WHERE atom_id LIKE ?", (pattern,))
        else:
            cursor.execute("SELECT COUNT(*) FROM sm2_state")
        count = cursor.fetchone()[0]

        if count == 0:
            return 0

        # Require confirmation for destructive operation
        if not force:
            print(f"\n⚠️  WARNING: This will delete {count} SM-2 progress records!")
            if module_filter:
                print(f"   Scope: Module {module_filter} only")
            else:
                print("   Scope: ALL progress data (full reset)")
            confirm = input("\nType 'DELETE' to confirm: ")
            if confirm != "DELETE":
                print("Reset cancelled.")
                return 0

        # Create backup before deletion
        backup_dir = self.db_path.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"progress_backup_{timestamp}.json"

        # Export current state
        cursor.execute("SELECT * FROM sm2_state")
        sm2_data = [dict(row) for row in cursor.fetchall()]
        cursor.execute("SELECT * FROM review_log")
        review_data = [dict(row) for row in cursor.fetchall()]
        cursor.execute("SELECT * FROM session_history")
        session_data = [dict(row) for row in cursor.fetchall()]

        backup = {
            "timestamp": timestamp,
            "module_filter": module_filter,
            "sm2_state": sm2_data,
            "review_log": review_data,
            "session_history": session_data,
        }

        with open(backup_file, "w") as f:
            json.dump(backup, f, indent=2, default=str)
        print(f"✓ Backup saved: {backup_file}")

        # Now perform deletion
        if module_filter is not None:
            pattern = f"M{module_filter}-%"
            cursor.execute("DELETE FROM review_log WHERE atom_id LIKE ?", (pattern,))
            cursor.execute("DELETE FROM sm2_state WHERE atom_id LIKE ?", (pattern,))
        else:
            cursor.execute("DELETE FROM review_log")
            cursor.execute("DELETE FROM sm2_state")
            cursor.execute("DELETE FROM session_history")

        self.conn.commit()
        print(f"✓ Reset complete: {cursor.rowcount} records deleted")
        return cursor.rowcount

    def restore(self, backup_file: str | None = None) -> int:
        """
        Restore progress from a backup file.

        Args:
            backup_file: Path to backup JSON file. If None, uses most recent backup.

        Returns:
            Number of records restored
        """
        import json
        from pathlib import Path

        backup_dir = self.db_path.parent / "backups"

        if backup_file is None:
            # Find most recent backup
            backups = sorted(backup_dir.glob("progress_backup_*.json"), reverse=True)
            if not backups:
                print("No backup files found!")
                return 0
            backup_file = backups[0]
            print(f"Using most recent backup: {backup_file.name}")
        else:
            backup_file = Path(backup_file)

        if not backup_file.exists():
            print(f"Backup file not found: {backup_file}")
            return 0

        with open(backup_file) as f:
            backup = json.load(f)

        cursor = self.conn.cursor()
        restored = 0

        # Restore SM-2 state
        for record in backup.get("sm2_state", []):
            cursor.execute(
                """
                INSERT OR REPLACE INTO sm2_state
                (atom_id, easiness, interval, repetitions, next_review, last_review)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    record["atom_id"],
                    record["easiness"],
                    record["interval"],
                    record["repetitions"],
                    record.get("next_review"),
                    record.get("last_review"),
                ),
            )
            restored += 1

        # Restore review log
        for record in backup.get("review_log", []):
            cursor.execute(
                """
                INSERT INTO review_log (atom_id, grade, reviewed_at, response_time_ms)
                VALUES (?, ?, ?, ?)
            """,
                (
                    record["atom_id"],
                    record["grade"],
                    record["reviewed_at"],
                    record.get("response_time_ms"),
                ),
            )

        # Restore session history
        for record in backup.get("session_history", []):
            cursor.execute(
                """
                INSERT INTO session_history
                (session_id, started_at, ended_at, atoms_reviewed, correct_count, mode)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    record["session_id"],
                    record["started_at"],
                    record.get("ended_at"),
                    record["atoms_reviewed"],
                    record["correct_count"],
                    record.get("mode", "adaptive"),
                ),
            )

        self.conn.commit()
        print(f"✓ Restored {restored} SM-2 records from {backup_file.name}")
        return restored

    def list_backups(self) -> list:
        """List available backup files."""
        backup_dir = self.db_path.parent / "backups"
        if not backup_dir.exists():
            return []
        return sorted(backup_dir.glob("progress_backup_*.json"), reverse=True)

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
