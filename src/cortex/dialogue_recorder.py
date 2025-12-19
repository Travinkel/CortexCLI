"""
Dialogue Recorder: Persistence layer for Socratic tutoring sessions.

Records all dialogue turns for:
- Learning analytics
- Struggle pattern detection
- Cross-session remediation
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy import text

from src.db.database import engine


class DialogueRecorder:
    """
    Persists Socratic dialogue sessions to the database.

    Tracks:
    - Full dialogue history with timestamps
    - Cognitive signals detected per turn
    - Resolution outcomes
    - Prerequisite gaps identified
    """

    def __init__(self, learner_id: str = "default"):
        self.learner_id = learner_id

    def start_recording(self, atom_id: str) -> int | None:
        """
        Create a new dialogue record in the database.

        Returns:
            dialogue_id for the new record, or None on failure
        """
        try:
            with engine.begin() as conn:
                result = conn.execute(
                    text("""
                        INSERT INTO socratic_dialogues (atom_id, learner_id, started_at)
                        VALUES (:atom_id, :learner_id, :started_at)
                        RETURNING id
                    """),
                    {
                        "atom_id": atom_id,
                        "learner_id": self.learner_id,
                        "started_at": datetime.now(),
                    }
                )
                row = result.fetchone()
                return row[0] if row else None

        except Exception as e:
            logger.error(f"Failed to start dialogue recording: {e}")
            return None

    def record_turn(
        self,
        dialogue_id: int,
        turn_number: int,
        role: str,
        content: str,
        latency_ms: int | None = None,
        signal: str | None = None,
    ) -> bool:
        """
        Record a single dialogue turn.

        Args:
            dialogue_id: ID of the parent dialogue
            turn_number: Sequential turn number (0-indexed)
            role: "tutor" or "learner"
            content: The message content
            latency_ms: Response time in milliseconds (learner only)
            signal: Detected cognitive signal (learner only)

        Returns:
            True if successful
        """
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO dialogue_turns
                            (dialogue_id, turn_number, role, content, latency_ms, signal, timestamp)
                        VALUES
                            (:dialogue_id, :turn_number, :role, :content, :latency_ms, :signal, :timestamp)
                    """),
                    {
                        "dialogue_id": dialogue_id,
                        "turn_number": turn_number,
                        "role": role,
                        "content": content,
                        "latency_ms": latency_ms,
                        "signal": signal,
                        "timestamp": datetime.now(),
                    }
                )
                return True

        except Exception as e:
            logger.error(f"Failed to record dialogue turn: {e}")
            return False

    def finalize(
        self,
        dialogue_id: int,
        resolution: str,
        scaffold_level_reached: int,
        turns_count: int,
        total_duration_ms: int,
        detected_gaps: list[str] | None = None,
    ) -> bool:
        """
        Close a dialogue session with final statistics.

        Args:
            dialogue_id: ID of the dialogue to finalize
            resolution: "self_solved", "guided_solved", "gave_up", "revealed"
            scaffold_level_reached: Maximum scaffold level used (0-4)
            turns_count: Total number of turns in dialogue
            total_duration_ms: Total dialogue duration
            detected_gaps: List of prerequisite topics identified as gaps

        Returns:
            True if successful
        """
        try:
            gaps_json = json.dumps(detected_gaps or [])

            with engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE socratic_dialogues
                        SET
                            ended_at = :ended_at,
                            resolution = :resolution,
                            scaffold_level_reached = :scaffold_level,
                            turns_count = :turns_count,
                            total_duration_ms = :duration_ms,
                            detected_gaps = :gaps
                        WHERE id = :id
                    """),
                    {
                        "id": dialogue_id,
                        "ended_at": datetime.now(),
                        "resolution": resolution,
                        "scaffold_level": scaffold_level_reached,
                        "turns_count": turns_count,
                        "duration_ms": total_duration_ms,
                        "gaps": gaps_json,
                    }
                )
                return True

        except Exception as e:
            logger.error(f"Failed to finalize dialogue: {e}")
            return False

    def get_struggle_atoms(self, min_dialogues: int = 2) -> list[dict]:
        """
        Query atoms where learner frequently needed Socratic help.

        Args:
            min_dialogues: Minimum dialogue count to be considered a struggle

        Returns:
            List of {"atom_id": str, "dialogue_count": int, "avg_scaffold": float}
        """
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT
                            atom_id,
                            COUNT(*) as dialogue_count,
                            AVG(scaffold_level_reached) as avg_scaffold,
                            SUM(CASE WHEN resolution = 'revealed' THEN 1 ELSE 0 END) as reveal_count
                        FROM socratic_dialogues
                        WHERE learner_id = :learner_id
                        GROUP BY atom_id
                        HAVING COUNT(*) >= :min_count
                        ORDER BY dialogue_count DESC, avg_scaffold DESC
                    """),
                    {"learner_id": self.learner_id, "min_count": min_dialogues}
                )

                return [
                    {
                        "atom_id": row[0],
                        "dialogue_count": row[1],
                        "avg_scaffold": float(row[2]) if row[2] else 0.0,
                        "reveal_count": row[3],
                    }
                    for row in result.fetchall()
                ]

        except Exception as e:
            logger.error(f"Failed to get struggle atoms: {e}")
            return []

    def get_detected_gaps(self, limit: int = 10) -> list[dict]:
        """
        Query frequently detected prerequisite gaps.

        Returns:
            List of {"gap": str, "count": int}
        """
        try:
            with engine.connect() as conn:
                # Query dialogues with gaps
                result = conn.execute(
                    text("""
                        SELECT detected_gaps
                        FROM socratic_dialogues
                        WHERE learner_id = :learner_id
                          AND detected_gaps IS NOT NULL
                          AND detected_gaps != '[]'
                    """),
                    {"learner_id": self.learner_id}
                )

                # Aggregate gap counts
                gap_counts: dict[str, int] = {}
                for row in result.fetchall():
                    try:
                        gaps = json.loads(row[0]) if row[0] else []
                        for gap in gaps:
                            gap_counts[gap] = gap_counts.get(gap, 0) + 1
                    except json.JSONDecodeError:
                        continue

                # Sort by count
                sorted_gaps = sorted(gap_counts.items(), key=lambda x: x[1], reverse=True)

                return [{"gap": g, "count": c} for g, c in sorted_gaps[:limit]]

        except Exception as e:
            logger.error(f"Failed to get detected gaps: {e}")
            return []

    def get_dialogue_history(self, dialogue_id: int) -> list[dict]:
        """
        Retrieve full dialogue history for review.

        Returns:
            List of turn dictionaries
        """
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT turn_number, role, content, latency_ms, signal, timestamp
                        FROM dialogue_turns
                        WHERE dialogue_id = :id
                        ORDER BY turn_number
                    """),
                    {"id": dialogue_id}
                )

                return [
                    {
                        "turn": row[0],
                        "role": row[1],
                        "content": row[2],
                        "latency_ms": row[3],
                        "signal": row[4],
                        "timestamp": row[5].isoformat() if row[5] else None,
                    }
                    for row in result.fetchall()
                ]

        except Exception as e:
            logger.error(f"Failed to get dialogue history: {e}")
            return []

    def get_session_stats(self) -> dict:
        """
        Get aggregate statistics for the learner's Socratic sessions.

        Returns:
            Statistics dictionary
        """
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT
                            COUNT(*) as total_dialogues,
                            AVG(turns_count) as avg_turns,
                            AVG(scaffold_level_reached) as avg_scaffold,
                            AVG(total_duration_ms) as avg_duration_ms,
                            SUM(CASE WHEN resolution = 'self_solved' THEN 1 ELSE 0 END) as self_solved,
                            SUM(CASE WHEN resolution = 'guided_solved' THEN 1 ELSE 0 END) as guided_solved,
                            SUM(CASE WHEN resolution = 'gave_up' THEN 1 ELSE 0 END) as gave_up,
                            SUM(CASE WHEN resolution = 'revealed' THEN 1 ELSE 0 END) as revealed
                        FROM socratic_dialogues
                        WHERE learner_id = :learner_id
                    """),
                    {"learner_id": self.learner_id}
                )

                row = result.fetchone()
                if not row or row[0] == 0:
                    return {"total_dialogues": 0}

                return {
                    "total_dialogues": row[0],
                    "avg_turns": float(row[1]) if row[1] else 0.0,
                    "avg_scaffold": float(row[2]) if row[2] else 0.0,
                    "avg_duration_ms": float(row[3]) if row[3] else 0.0,
                    "resolution_breakdown": {
                        "self_solved": row[4] or 0,
                        "guided_solved": row[5] or 0,
                        "gave_up": row[6] or 0,
                        "revealed": row[7] or 0,
                    },
                }

        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return {"total_dialogues": 0}
