#!/usr/bin/env python3
"""
Ingestion Bridge: Hydrate clean_atoms and quiz_questions from generated content.

This script populates the canonical PostgreSQL schema from:
1. ccna_generated_atoms table (default source)
2. JSON files from output/module_*.json (optional)

Idempotency:
- Uses card_id as unique constraint to prevent duplicates
- Running twice is safe; existing records are updated

Usage:
    python scripts/hydrate_db.py                      # Hydrate from DB source
    python scripts/hydrate_db.py --from-json          # Hydrate from JSON files
    python scripts/hydrate_db.py --dry-run            # Preview without writing
    python scripts/hydrate_db.py --module NET-M1      # Process specific module
    python scripts/hydrate_db.py --grade-filter B     # Only Grade B+ atoms
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from sqlalchemy import text

from src.db.database import init_db, session_scope

# Quiz-compatible atom types that need QuizQuestion records
QUIZ_TYPES = {"mcq", "true_false", "matching", "parsons", "ranking", "numeric", "short_answer"}

# Grade hierarchy for filtering
GRADE_ORDER = {"A": 1, "B": 2, "C": 3, "D": 4, "F": 5}


@dataclass
class HydrationStats:
    """Statistics from hydration run."""

    atoms_processed: int = 0
    atoms_created: int = 0
    atoms_updated: int = 0
    atoms_skipped: int = 0
    quiz_questions_created: int = 0
    quiz_questions_updated: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def summary(self) -> str:
        return (
            f"Processed: {self.atoms_processed} | "
            f"Created: {self.atoms_created} | "
            f"Updated: {self.atoms_updated} | "
            f"Skipped: {self.atoms_skipped} | "
            f"Quiz Questions: {self.quiz_questions_created} created, {self.quiz_questions_updated} updated | "
            f"Errors: {len(self.errors)}"
        )


def get_module_uuid_map() -> dict[str, UUID]:
    """Get mapping from module_id (NET-M1) to clean_modules UUID."""
    module_map = {}
    try:
        with session_scope() as session:
            result = session.execute(
                text("""
                SELECT name, id FROM clean_modules
                WHERE name LIKE 'CCNA%' OR name LIKE 'Module%' OR name LIKE 'NET-M%'
            """)
            )
            for row in result:
                # Extract module number and map various formats
                name = row[0]
                module_uuid = row[1]

                # Try to extract module number
                import re

                match = re.search(r"(\d+)", name)
                if match:
                    module_num = int(match.group(1))
                    module_map[f"NET-M{module_num}"] = module_uuid
                    module_map[f"M{module_num}"] = module_uuid
    except Exception as e:
        logger.warning(f"Could not load module mapping: {e}")

    return module_map


def get_section_to_concept_map() -> dict[str, UUID]:
    """Get mapping from section_id to concept UUID."""
    section_concept_map = {}
    try:
        with session_scope() as session:
            # Get concepts linked to sections via naming patterns
            result = session.execute(
                text("""
                SELECT ca.ccna_section_id, ca.concept_id
                FROM clean_atoms ca
                WHERE ca.concept_id IS NOT NULL
                  AND ca.ccna_section_id IS NOT NULL
                GROUP BY ca.ccna_section_id, ca.concept_id
            """)
            )
            for row in result:
                if row[0] and row[1]:
                    section_concept_map[row[0]] = row[1]
    except Exception as e:
        logger.debug(f"Could not load section-concept mapping: {e}")

    return section_concept_map


def extract_fidelity_metadata(atom_data: dict[str, Any]) -> dict[str, Any]:
    """Extract fidelity tracking metadata from atom data."""
    metadata = {}

    # Handle is_hydrated flag
    if "is_hydrated" in atom_data:
        metadata["is_hydrated"] = atom_data["is_hydrated"]

    # Handle fidelity_type
    if "fidelity_type" in atom_data:
        metadata["fidelity_type"] = atom_data["fidelity_type"]

    # Handle source_fact_basis
    if "source_fact_basis" in atom_data:
        metadata["source_fact_basis"] = atom_data["source_fact_basis"]

    return metadata if metadata else None


def map_atom_to_clean_atom(
    atom_data: dict[str, Any],
    module_map: dict[str, UUID],
    section_concept_map: dict[str, UUID],
) -> dict[str, Any]:
    """
    Map raw atom data to CleanAtom column values.

    Handles both ccna_generated_atoms DB rows and JSON file format.
    """
    module_id = atom_data.get("module_id", "")
    section_id = atom_data.get("section_id") or atom_data.get("source_section_id")

    # Get linked UUIDs
    module_uuid = module_map.get(module_id)
    concept_id = section_concept_map.get(section_id) if section_id else None

    # Extract fidelity metadata for JSONB column
    extract_fidelity_metadata(atom_data)

    # Calculate word counts
    front = atom_data.get("front", "") or ""
    back = atom_data.get("back", "") or ""
    front_word_count = len(front.split()) if front else 0
    back_word_count = len(back.split()) if back else 0

    # Determine atomicity status
    is_atomic = atom_data.get("is_atomic", True)
    atomicity_status = "atomic" if is_atomic else "verbose"

    # Quality score normalization (0-1 scale)
    quality_score = atom_data.get("quality_score")
    if quality_score is not None:
        # If score is 0-100, normalize to 0-1
        if quality_score > 1:
            quality_score = quality_score / 100.0

    # Extract fidelity fields directly (they are now columns, not in metadata)
    is_hydrated = atom_data.get("is_hydrated", False)
    fidelity_type = atom_data.get("fidelity_type", "verbatim_extract")
    source_fact_basis = atom_data.get("source_fact_basis")

    return {
        "card_id": atom_data.get("card_id"),
        "atom_type": atom_data.get("atom_type", "flashcard"),
        "front": front,
        "back": back,
        # Linkage
        "module_id": module_uuid,
        "concept_id": concept_id,
        # Quality metadata
        "quality_score": Decimal(str(quality_score)) if quality_score else None,
        "is_atomic": is_atomic,
        "front_word_count": front_word_count,
        "back_word_count": back_word_count,
        "atomicity_status": atomicity_status,
        "needs_review": atom_data.get("needs_review", False),
        # Source tracking
        "source": "ccna_generation",
        "batch_id": atom_data.get("generation_job_id"),
        # Fidelity tracking (High-Fidelity Atoms)
        "is_hydrated": is_hydrated,
        "fidelity_type": fidelity_type,
        "source_fact_basis": source_fact_basis,
    }


def map_atom_to_quiz_question(
    atom_data: dict[str, Any],
    clean_atom_id: UUID,
) -> dict[str, Any] | None:
    """
    Map raw atom data to QuizQuestion column values.

    Returns None if atom type doesn't need a quiz question.
    """
    atom_type = atom_data.get("atom_type", "flashcard")

    if atom_type not in QUIZ_TYPES:
        return None

    # Build question_content JSONB based on type
    content_json = atom_data.get("content_json") or {}

    # If content_json is a string, parse it
    if isinstance(content_json, str):
        try:
            content_json = json.loads(content_json)
        except json.JSONDecodeError:
            content_json = {}

    # Map atom type to quiz question type
    # Note: 'numeric' and 'parsons' are now first-class types in the DB schema
    question_type_map = {
        "mcq": "mcq",
        "true_false": "true_false",
        "matching": "matching",
        "parsons": "parsons",  # Now a first-class type
        "ranking": "ranking",
        "numeric": "numeric",  # Now a first-class type
        "short_answer": "short_answer",
    }
    question_type = question_type_map.get(atom_type, atom_type)

    # Map knowledge type
    knowledge_type = atom_data.get("knowledge_type", "conceptual")
    if isinstance(knowledge_type, str):
        knowledge_type = knowledge_type.lower()

    # Estimate difficulty
    difficulty = atom_data.get("difficulty")
    if difficulty is None:
        # Default difficulty based on type
        type_difficulty = {
            "mcq": Decimal("0.50"),
            "true_false": Decimal("0.40"),
            "matching": Decimal("0.60"),
            "ranking": Decimal("0.65"),
            "parsons": Decimal("0.70"),
            "numeric": Decimal("0.60"),
            "short_answer": Decimal("0.55"),
        }
        difficulty = type_difficulty.get(atom_type, Decimal("0.50"))
    elif isinstance(difficulty, (int, float)):
        difficulty = Decimal(str(difficulty))

    # Estimate cognitive load (intrinsic)
    intrinsic_load = _estimate_intrinsic_load(atom_type, content_json)

    return {
        "atom_id": clean_atom_id,
        "question_type": question_type,
        "question_content": content_json,
        "difficulty": difficulty,
        "intrinsic_load": intrinsic_load,
        "knowledge_type": knowledge_type,
        "points": 1,
        "partial_credit": atom_type in ("matching", "ranking", "parsons"),
        "is_active": True,
    }


def _estimate_intrinsic_load(atom_type: str, content: dict) -> int:
    """Estimate intrinsic cognitive load (1-5) based on content."""
    base_load = 2

    if atom_type == "matching":
        pairs = content.get("pairs", [])
        return min(5, base_load + len(pairs) // 2)
    elif atom_type == "mcq":
        options = content.get("options", [])
        return min(4, base_load + len(options) // 2)
    elif atom_type in ("parsons", "ranking"):
        items = content.get("items", content.get("blocks", []))
        return min(5, base_load + len(items) // 2)
    elif atom_type == "numeric":
        return 3  # Medium load for calculations

    return base_load


def fetch_atoms_from_db(
    module_filter: str | None = None,
    grade_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch generated atoms from ccna_generated_atoms table."""
    atoms = []

    with session_scope() as session:
        # Check if source table exists
        source_exists = session.execute(
            text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'ccna_generated_atoms'
            )
        """)
        ).scalar()

        if not source_exists:
            logger.error("Source table 'ccna_generated_atoms' does not exist!")
            logger.info("Run the migration script or use --from-json to load from files.")
            return atoms

        query = """
            SELECT
                card_id, atom_type, module_id, section_id,
                generation_job_id, front, back, content_json,
                knowledge_type, quality_grade, quality_score,
                quality_details, is_atomic, is_accurate, is_clear,
                needs_review, tags, bloom_level
            FROM ccna_generated_atoms
            WHERE front IS NOT NULL AND front != ''
        """

        params = {}

        if module_filter:
            query += " AND module_id = :module_id"
            params["module_id"] = module_filter

        if grade_filter:
            # Filter to include only this grade or better
            min_grade_order = GRADE_ORDER.get(grade_filter.upper(), 5)
            valid_grades = [g for g, order in GRADE_ORDER.items() if order <= min_grade_order]
            query += " AND quality_grade = ANY(:grades)"
            params["grades"] = valid_grades

        query += " ORDER BY module_id, section_id, card_id"

        result = session.execute(text(query), params)
        columns = result.keys()

        for row in result:
            atom = dict(zip(columns, row))
            atoms.append(atom)

    return atoms


def fetch_atoms_from_json(
    json_dir: Path,
    module_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch atoms from JSON files in output directory."""
    atoms = []

    pattern = "module_*.json"
    if module_filter:
        # Extract module number
        import re

        match = re.search(r"\d+", module_filter)
        if match:
            pattern = f"module_{match.group()}.json"

    for json_file in json_dir.glob(pattern):
        logger.info(f"Reading {json_file.name}")
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)

            # Handle both array and object formats
            if isinstance(data, list):
                atoms.extend(data)
            elif isinstance(data, dict):
                if "atoms" in data:
                    atoms.extend(data["atoms"])
                else:
                    atoms.append(data)
        except Exception as e:
            logger.error(f"Failed to read {json_file}: {e}")

    return atoms


def fetch_quiz_eligible_atoms_from_clean_atoms(
    module_filter: str | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch quiz-eligible atoms directly from clean_atoms table.

    This is useful when clean_atoms is already populated but quiz_questions
    table is missing or incomplete.
    """
    atoms = []

    query = """
        SELECT
            ca.id,
            ca.card_id,
            ca.atom_type,
            ca.front,
            ca.back,
            ca.concept_id,
            ca.module_id,
            ca.ccna_section_id as section_id,
            ca.quality_score,
            ca.is_atomic,
            ca.needs_review,
            ca.quiz_question_metadata
        FROM clean_atoms ca
        WHERE ca.atom_type IN ('mcq', 'true_false', 'matching', 'parsons', 'ranking', 'numeric', 'short_answer')
          AND ca.front IS NOT NULL
          AND ca.front != ''
    """

    params = {}

    if module_filter:
        # Filter by section_id pattern (e.g., NET-M1 or module number)
        import re

        match = re.search(r"\d+", module_filter)
        if match:
            module_num = match.group()
            query += " AND ca.ccna_section_id LIKE :section_pattern"
            params["section_pattern"] = f"{module_num}.%"

    query += " ORDER BY ca.ccna_section_id, ca.card_id"

    with session_scope() as session:
        result = session.execute(text(query), params)
        columns = result.keys()

        for row in result:
            atom = dict(zip(columns, row))
            atoms.append(atom)

    return atoms


def create_quiz_questions_from_clean_atoms(
    atoms: list[dict[str, Any]],
    dry_run: bool = False,
) -> HydrationStats:
    """
    Create QuizQuestion records for quiz-eligible atoms already in clean_atoms.

    This bridges the gap when clean_atoms exists but quiz_questions is empty.
    """
    stats = HydrationStats()

    if dry_run:
        logger.info("[DRY RUN] Would create quiz questions without writing to database")

    with session_scope() as session:
        for atom_data in atoms:
            stats.atoms_processed += 1
            clean_atom_id = atom_data.get("id")
            card_id = atom_data.get("card_id", "unknown")

            if not clean_atom_id:
                stats.atoms_skipped += 1
                continue

            try:
                # Check if quiz question already exists
                existing = session.execute(
                    text("SELECT id FROM quiz_questions WHERE atom_id = :atom_id"),
                    {"atom_id": clean_atom_id},
                ).fetchone()

                if existing:
                    stats.atoms_skipped += 1
                    continue

                if dry_run:
                    stats.quiz_questions_created += 1
                    continue

                # Build quiz question data
                quiz_values = map_atom_to_quiz_question(atom_data, clean_atom_id)

                if quiz_values:
                    # Convert content to JSON string for JSONB column
                    quiz_values_copy = quiz_values.copy()
                    if "question_content" in quiz_values_copy:
                        quiz_values_copy["question_content"] = json.dumps(
                            quiz_values_copy["question_content"]
                        )

                    # Add timestamps
                    quiz_values_copy["created_at"] = datetime.utcnow()
                    quiz_values_copy["updated_at"] = datetime.utcnow()

                    cols = ", ".join(quiz_values_copy.keys())
                    placeholders = ", ".join(f":{k}" for k in quiz_values_copy.keys())
                    session.execute(
                        text(f"""
                            INSERT INTO quiz_questions ({cols})
                            VALUES ({placeholders})
                        """),
                        quiz_values_copy,
                    )
                    stats.quiz_questions_created += 1

                # Commit every 500 atoms for efficiency
                if stats.atoms_processed % 500 == 0:
                    session.commit()
                    logger.info(
                        f"Progress: {stats.atoms_processed} atoms processed, {stats.quiz_questions_created} created"
                    )

            except Exception as e:
                stats.errors.append(f"Error processing {card_id}: {e}")
                logger.error(f"Failed to create quiz question for {card_id}: {e}")
                # Rollback to allow next insert
                session.rollback()
                continue

        # Final commit
        if not dry_run:
            session.commit()

    return stats


def hydrate_clean_atoms(
    atoms: list[dict[str, Any]],
    dry_run: bool = False,
) -> HydrationStats:
    """
    Hydrate clean_atoms and quiz_questions tables.

    Uses PostgreSQL UPSERT (INSERT ... ON CONFLICT) for idempotency.
    """
    stats = HydrationStats()

    # Load mappings
    logger.info("Loading module and concept mappings...")
    module_map = get_module_uuid_map()
    section_concept_map = get_section_to_concept_map()

    logger.info(
        f"Found {len(module_map)} modules, {len(section_concept_map)} section-concept links"
    )

    if dry_run:
        logger.info("[DRY RUN] Would process atoms without writing to database")

    with session_scope() as session:
        for atom_data in atoms:
            stats.atoms_processed += 1
            card_id = atom_data.get("card_id")

            if not card_id:
                stats.atoms_skipped += 1
                stats.errors.append(f"Atom missing card_id: {atom_data.get('front', '')[:50]}")
                continue

            try:
                # Map to CleanAtom columns
                clean_atom_values = map_atom_to_clean_atom(
                    atom_data, module_map, section_concept_map
                )

                if dry_run:
                    # Just validate
                    atom_type = atom_data.get("atom_type", "flashcard")
                    if atom_type in QUIZ_TYPES:
                        stats.quiz_questions_created += 1
                    stats.atoms_created += 1
                    continue

                # Check if atom exists
                existing = session.execute(
                    text("SELECT id FROM clean_atoms WHERE card_id = :card_id"),
                    {"card_id": card_id},
                ).fetchone()

                if existing:
                    # Update existing atom
                    clean_atom_id = existing[0]
                    update_cols = ", ".join(
                        f"{k} = :{k}" for k in clean_atom_values.keys() if k != "card_id"
                    )
                    session.execute(
                        text(f"""
                            UPDATE clean_atoms
                            SET {update_cols}, updated_at = NOW()
                            WHERE card_id = :card_id
                        """),
                        clean_atom_values,
                    )
                    stats.atoms_updated += 1
                else:
                    # Insert new atom
                    cols = ", ".join(clean_atom_values.keys())
                    placeholders = ", ".join(f":{k}" for k in clean_atom_values.keys())
                    result = session.execute(
                        text(f"""
                            INSERT INTO clean_atoms ({cols})
                            VALUES ({placeholders})
                            RETURNING id
                        """),
                        clean_atom_values,
                    )
                    clean_atom_id = result.fetchone()[0]
                    stats.atoms_created += 1

                # Handle quiz question if applicable
                quiz_values = map_atom_to_quiz_question(atom_data, clean_atom_id)

                if quiz_values:
                    # Check if quiz question exists for this atom
                    existing_quiz = session.execute(
                        text("SELECT id FROM quiz_questions WHERE atom_id = :atom_id"),
                        {"atom_id": clean_atom_id},
                    ).fetchone()

                    if existing_quiz:
                        # Update existing quiz question
                        update_cols = ", ".join(
                            f"{k} = :{k}" for k in quiz_values.keys() if k != "atom_id"
                        )
                        session.execute(
                            text(f"""
                                UPDATE quiz_questions
                                SET {update_cols}, updated_at = NOW()
                                WHERE atom_id = :atom_id
                            """),
                            quiz_values,
                        )
                        stats.quiz_questions_updated += 1
                    else:
                        # Insert new quiz question
                        cols = ", ".join(quiz_values.keys())
                        placeholders = ", ".join(f":{k}" for k in quiz_values.keys())
                        # Convert content to JSON string for JSONB column
                        quiz_values_copy = quiz_values.copy()
                        if "question_content" in quiz_values_copy:
                            quiz_values_copy["question_content"] = json.dumps(
                                quiz_values_copy["question_content"]
                            )
                        session.execute(
                            text(f"""
                                INSERT INTO quiz_questions ({cols})
                                VALUES ({placeholders})
                            """),
                            quiz_values_copy,
                        )
                        stats.quiz_questions_created += 1

                # Commit every 100 atoms
                if stats.atoms_processed % 100 == 0:
                    session.commit()
                    logger.info(f"Progress: {stats.atoms_processed} atoms processed")

            except Exception as e:
                stats.errors.append(f"Error processing {card_id}: {e}")
                logger.error(f"Failed to process {card_id}: {e}")
                # Continue with next atom
                continue

        # Final commit
        if not dry_run:
            session.commit()

    return stats


def print_table_counts() -> None:
    """Print current row counts for relevant tables."""
    with session_scope() as session:
        clean_atoms_count = session.execute(text("SELECT COUNT(*) FROM clean_atoms")).scalar()

        quiz_questions_count = session.execute(text("SELECT COUNT(*) FROM quiz_questions")).scalar()

        # Check if source table exists
        source_exists = session.execute(
            text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'ccna_generated_atoms'
            )
        """)
        ).scalar()

        source_atoms_count = 0
        if source_exists:
            source_atoms_count = session.execute(
                text("SELECT COUNT(*) FROM ccna_generated_atoms")
            ).scalar()

        logger.info("Current table counts:")
        if source_exists:
            logger.info(f"  ccna_generated_atoms (source): {source_atoms_count}")
        else:
            logger.info("  ccna_generated_atoms (source): TABLE NOT FOUND")
        logger.info(f"  clean_atoms: {clean_atoms_count}")
        logger.info(f"  quiz_questions: {quiz_questions_count}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Hydrate clean_atoms and quiz_questions from generated content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create quiz_questions from existing clean_atoms (recommended)
  python scripts/hydrate_db.py --quiz-only

  # Preview quiz creation without writing
  python scripts/hydrate_db.py --quiz-only --dry-run

  # Hydrate from ccna_generated_atoms table
  python scripts/hydrate_db.py

  # Preview without writing
  python scripts/hydrate_db.py --dry-run

  # Process specific module
  python scripts/hydrate_db.py --module NET-M1

  # Only Grade B or better atoms
  python scripts/hydrate_db.py --grade-filter B

  # Hydrate from JSON files
  python scripts/hydrate_db.py --from-json --json-dir output/
        """,
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without writing to database"
    )
    parser.add_argument(
        "--from-json", action="store_true", help="Read from JSON files instead of database"
    )
    parser.add_argument(
        "--json-dir",
        type=Path,
        default=Path("output"),
        help="Directory containing module_*.json files",
    )
    parser.add_argument("--module", type=str, help="Process only specific module (e.g., NET-M1)")
    parser.add_argument(
        "--grade-filter",
        type=str,
        choices=["A", "B", "C", "D"],
        help="Only process atoms with this grade or better",
    )
    parser.add_argument(
        "--init-db", action="store_true", help="Initialize database tables before hydrating"
    )
    parser.add_argument(
        "--quiz-only",
        action="store_true",
        help="Create quiz_questions from existing clean_atoms (no source table needed)",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Ingestion Bridge: Database Hydration")
    logger.info("=" * 60)

    # Initialize database if requested
    if args.init_db:
        logger.info("Initializing database tables...")
        init_db()

    # Show current counts
    print_table_counts()

    # Quiz-only mode: create quiz_questions from existing clean_atoms
    if args.quiz_only:
        logger.info("Quiz-only mode: Creating quiz_questions from existing clean_atoms")
        atoms = fetch_quiz_eligible_atoms_from_clean_atoms(args.module)

        if not atoms:
            logger.warning("No quiz-eligible atoms found in clean_atoms!")
            return

        logger.info(f"Found {len(atoms)} quiz-eligible atoms")

        # Show type distribution
        type_counts = {}
        for atom in atoms:
            atom_type = atom.get("atom_type", "unknown")
            type_counts[atom_type] = type_counts.get(atom_type, 0) + 1

        logger.info("Atom type distribution:")
        for atom_type, count in sorted(type_counts.items()):
            logger.info(f"  {atom_type}: {count}")

        logger.info("\nCreating quiz questions...")
        stats = create_quiz_questions_from_clean_atoms(atoms, dry_run=args.dry_run)

        logger.info("\n" + "=" * 60)
        logger.info("Quiz Question Creation Complete")
        logger.info("=" * 60)
        logger.info(stats.summary())

        if stats.errors:
            logger.warning("\nFirst 5 errors:")
            for err in stats.errors[:5]:
                logger.warning(f"  {err}")

        # Show final counts
        if not args.dry_run:
            logger.info("\nFinal table counts:")
            print_table_counts()

        return

    # Fetch atoms from source
    if args.from_json:
        logger.info(f"Fetching atoms from JSON files in {args.json_dir}")
        atoms = fetch_atoms_from_json(args.json_dir, args.module)
    else:
        logger.info("Fetching atoms from ccna_generated_atoms table")
        atoms = fetch_atoms_from_db(args.module, args.grade_filter)

    if not atoms:
        logger.warning("No atoms found to process!")
        return

    logger.info(f"Found {len(atoms)} atoms to process")

    # Show type distribution
    type_counts = {}
    for atom in atoms:
        atom_type = atom.get("atom_type", "unknown")
        type_counts[atom_type] = type_counts.get(atom_type, 0) + 1

    logger.info("Atom type distribution:")
    for atom_type, count in sorted(type_counts.items()):
        logger.info(f"  {atom_type}: {count}")

    # Hydrate
    logger.info("\nStarting hydration...")
    stats = hydrate_clean_atoms(atoms, dry_run=args.dry_run)

    logger.info("\n" + "=" * 60)
    logger.info("Hydration Complete")
    logger.info("=" * 60)
    logger.info(stats.summary())

    if stats.errors:
        logger.warning("\nFirst 5 errors:")
        for err in stats.errors[:5]:
            logger.warning(f"  {err}")

    # Show final counts
    if not args.dry_run:
        logger.info("\nFinal table counts:")
        print_table_counts()


if __name__ == "__main__":
    main()
