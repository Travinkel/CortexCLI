#!/usr/bin/env python3
"""
Backup learning progress data from PostgreSQL.
"""
import os
import sys

# Fix Windows encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

"""

Creates a JSON backup of all progress-related tables:
- atom_responses (quiz history)
- learner_mastery_state (mastery scores)
- learning_path_sessions (session metadata)
- session_atom_responses (detailed responses)
- pomodoro_sessions (study sessions)

Usage:
    python scripts/backup_progress.py
    python scripts/backup_progress.py --output my_backup.json
"""
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.db.database import engine


def backup_progress(output_path: Path = None) -> Path:
    """
    Export all progress data to JSON.

    Returns:
        Path to the created backup file
    """
    if output_path is None:
        backup_dir = Path(__file__).parent.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = backup_dir / f"pg_progress_backup_{timestamp}.json"

    backup_data = {
        "timestamp": datetime.now().isoformat(),
        "tables": {}
    }

    tables_to_backup = [
        "atom_responses",
        "learner_mastery_state",
        "learning_path_sessions",
        "session_atom_responses",
        "pomodoro_sessions",
        "war_mode_sessions",
        "war_mode_session_atoms",
        "ccna_study_sessions",
        "ccna_section_mastery",
    ]

    with engine.connect() as conn:
        for table in tables_to_backup:
            try:
                result = conn.execute(text(f"SELECT * FROM {table}"))
                rows = [dict(row._mapping) for row in result]
                backup_data["tables"][table] = rows
                print(f"  ✓ {table}: {len(rows)} records")
            except Exception as e:
                print(f"  ⚠ {table}: {e}")
                backup_data["tables"][table] = []

    # Convert UUIDs and dates to strings for JSON
    def serialize(obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        if hasattr(obj, 'hex'):
            return str(obj)
        return str(obj)

    with open(output_path, "w") as f:
        json.dump(backup_data, f, indent=2, default=serialize)

    print(f"\n✓ Backup saved: {output_path}")
    print(f"  Size: {output_path.stat().st_size / 1024:.1f} KB")

    return output_path


def restore_progress(backup_path: Path) -> int:
    """
    Restore progress data from a JSON backup.

    WARNING: This will merge with existing data (UPSERT behavior).

    Returns:
        Number of records restored
    """
    if not backup_path.exists():
        print(f"Backup file not found: {backup_path}")
        return 0

    with open(backup_path, "r") as f:
        backup_data = json.load(f)

    print(f"Restoring from: {backup_path.name}")
    print(f"Backup timestamp: {backup_data.get('timestamp', 'unknown')}")

    restored = 0

    with engine.connect() as conn:
        # Restore atom_responses
        for record in backup_data.get("tables", {}).get("atom_responses", []):
            try:
                conn.execute(text("""
                    INSERT INTO atom_responses
                    (id, atom_id, user_id, is_correct, response_time_ms, user_answer, responded_at)
                    VALUES (:id, :atom_id, :user_id, :is_correct, :response_time_ms, :user_answer, :responded_at)
                    ON CONFLICT (id) DO UPDATE SET
                        is_correct = EXCLUDED.is_correct,
                        response_time_ms = EXCLUDED.response_time_ms
                """), record)
                restored += 1
            except Exception as e:
                print(f"  ⚠ atom_responses: {e}")

        # Restore learner_mastery_state
        for record in backup_data.get("tables", {}).get("learner_mastery_state", []):
            try:
                conn.execute(text("""
                    INSERT INTO learner_mastery_state
                    (id, learner_id, concept_id, review_mastery, quiz_mastery, combined_mastery)
                    VALUES (:id, :learner_id, :concept_id, :review_mastery, :quiz_mastery, :combined_mastery)
                    ON CONFLICT (id) DO UPDATE SET
                        review_mastery = EXCLUDED.review_mastery,
                        quiz_mastery = EXCLUDED.quiz_mastery,
                        combined_mastery = EXCLUDED.combined_mastery
                """), record)
                restored += 1
            except Exception as e:
                print(f"  ⚠ learner_mastery_state: {e}")

        conn.commit()

    print(f"\n✓ Restored {restored} records")
    return restored


def list_backups() -> list:
    """List available PostgreSQL backups."""
    backup_dir = Path(__file__).parent.parent / "backups"
    if not backup_dir.exists():
        return []

    backups = sorted(backup_dir.glob("pg_progress_backup_*.json"), reverse=True)

    print("Available PostgreSQL backups:")
    for b in backups[:10]:
        size = b.stat().st_size / 1024
        print(f"  {b.name} ({size:.1f} KB)")

    if len(backups) > 10:
        print(f"  ... and {len(backups) - 10} more")

    return backups


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backup/restore learning progress")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--restore", "-r", help="Restore from backup file")
    parser.add_argument("--list", "-l", action="store_true", help="List available backups")

    args = parser.parse_args()

    if args.list:
        list_backups()
    elif args.restore:
        restore_progress(Path(args.restore))
    else:
        print("=== PostgreSQL Progress Backup ===\n")
        backup_progress(Path(args.output) if args.output else None)
