"""
Import ITN Practice Final Exam questions as atoms.

Parses the ITNPracticeFinalExam.txt file and creates MCQ atoms in the database.
"""

import json
import re
import sys
import uuid
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from sqlalchemy import create_engine, text

from config import get_settings

# Create standalone engine - use config for URL but fresh engine instance
settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)


SOURCE_FILE = "ITNPracticeFinalExam.txt"
CARD_ID_PREFIX = "ITN-EXAM"


def parse_itn_exam(filepath: Path) -> list[dict]:
    """Parse ITN Practice Final Exam into structured questions."""
    content = filepath.read_text(encoding="utf-8")

    questions = []

    # Split by question numbers (1. 2. 3. etc.)
    # Pattern: line starts with number followed by period
    pattern = r'\n(\d+)\.\s+'
    parts = re.split(pattern, content)

    # parts[0] is header, then alternating: number, content, number, content...
    i = 1
    while i < len(parts) - 1:
        q_num = parts[i]
        q_content = parts[i + 1]
        i += 2

        question = parse_question(q_num, q_content)
        if question:
            questions.append(question)

    return questions


def parse_question(q_num: str, content: str) -> dict | None:
    """Parse a single question block."""
    lines = content.strip().split('\n')
    if not lines:
        return None

    # First line(s) contain the question - find where options start
    question_lines = []
    option_start = 0

    for i, line in enumerate(lines):
        line_stripped = line.strip()
        # Skip empty lines at start
        if not line_stripped and not question_lines:
            continue
        # Check if this looks like an option (short line, no question mark at end)
        if question_lines and line_stripped and len(line_stripped) < 150:
            # Check if previous question line ended with ? or )
            last_q = question_lines[-1].strip() if question_lines else ""
            if last_q.endswith('?') or last_q.endswith(')'):
                option_start = i
                break
        question_lines.append(line)

    if not question_lines:
        return None

    question_text = ' '.join(line.strip() for line in question_lines).strip()

    # Check for multi-select
    is_multi = "(Choose two" in question_text or "(Choose three" in question_text
    required_count = 1
    if "(Choose two" in question_text:
        required_count = 2
    elif "(Choose three" in question_text:
        required_count = 3

    # Check for matching question
    if "Match the" in question_text or "Place the options" in question_text.lower():
        return parse_matching_question(q_num, question_text, lines[option_start:])

    # Parse options and find correct answer(s)
    options = []
    explanation = ""
    correct_indices = []

    remaining_lines = lines[option_start:]
    in_explanation = False
    explanation_lines = []

    for line in remaining_lines:
        line_stripped = line.strip()

        if not line_stripped:
            continue

        if line_stripped.startswith("Explanation:"):
            in_explanation = True
            explanation_lines.append(line_stripped.replace("Explanation:", "").strip())
            continue

        if in_explanation:
            explanation_lines.append(line_stripped)
            continue

        # Skip exhibit references
        if "Refer to the exhibit" in line_stripped:
            continue

        # This is an option
        # First option after question is usually correct in this format
        if line_stripped and not line_stripped.startswith("Other case"):
            options.append(line_stripped)

    if len(options) < 2:
        return None

    # In this format, the FIRST option listed is typically the correct answer
    # For multi-select, the first N options are correct
    correct_indices = list(range(required_count))

    explanation = ' '.join(explanation_lines).strip()

    # Build MCQ structure
    return {
        "question_number": int(q_num),
        "question": question_text,
        "options": options,
        "correct_indices": correct_indices,
        "is_multi": is_multi,
        "required_count": required_count,
        "explanation": explanation,
        "atom_type": "mcq",
    }


def parse_matching_question(q_num: str, question_text: str, remaining_lines: list[str]) -> dict | None:
    """Parse a matching question."""
    pairs = []
    explanation = ""
    in_explanation = False

    for line in remaining_lines:
        line_stripped = line.strip()

        if not line_stripped:
            continue

        if line_stripped.startswith("Explanation:"):
            in_explanation = True
            explanation = line_stripped.replace("Explanation:", "").strip()
            continue

        if in_explanation:
            explanation += " " + line_stripped
            continue

        # Look for tab or multiple spaces separating term from definition
        if '\t' in line_stripped:
            parts = line_stripped.split('\t')
            if len(parts) >= 2:
                pairs.append({"term": parts[0].strip(), "definition": parts[1].strip()})

    if len(pairs) < 2:
        return None

    return {
        "question_number": int(q_num),
        "question": question_text,
        "pairs": pairs,
        "explanation": explanation,
        "atom_type": "matching",
    }


def create_atom_from_question(q: dict, ccna_section_id: str | None = None) -> dict:
    """Convert parsed question to atom format."""
    atom_id = str(uuid.uuid4())
    q_num = q["question_number"]
    card_id = f"{CARD_ID_PREFIX}-{q['atom_type'].upper()}-{q_num:03d}"

    if q["atom_type"] == "mcq":
        back_content = {
            "options": q["options"],
            "correct": q["correct_indices"][0] if len(q["correct_indices"]) == 1 else q["correct_indices"],
            "multi_select": q["is_multi"],
            "required_count": q.get("required_count", 1),
            "explanation": q.get("explanation", ""),
        }

        return {
            "id": atom_id,
            "card_id": card_id,
            "front": q["question"],
            "back": json.dumps(back_content),
            "atom_type": "mcq",
            "ccna_section_id": ccna_section_id,
            "source_file": SOURCE_FILE,
            "quality_score": 0.75,
        }

    elif q["atom_type"] == "matching":
        back_content = {
            "pairs": q["pairs"],
            "explanation": q.get("explanation", ""),
        }

        return {
            "id": atom_id,
            "card_id": card_id,
            "front": q["question"],
            "back": json.dumps(back_content),
            "atom_type": "matching",
            "ccna_section_id": ccna_section_id,
            "source_file": SOURCE_FILE,
            "quality_score": 0.75,
        }

    return None


def import_atoms(atoms: list[dict], dry_run: bool = False) -> dict:
    """Import atoms into the database."""
    stats = {"created": 0, "skipped": 0, "errors": []}

    for atom in atoms:
        if not atom:
            continue

        # Use a fresh connection per atom to isolate failures
        with engine.connect() as conn:
            try:
                # Check if card_id already exists
                existing = conn.execute(
                    text("SELECT id FROM learning_atoms WHERE card_id = :card_id"),
                    {"card_id": atom["card_id"]}
                ).fetchone()

                if existing:
                    stats["skipped"] += 1
                    continue

                if dry_run:
                    logger.info(f"[DRY RUN] Would create: {atom['card_id']}")
                    stats["created"] += 1
                    continue

                conn.execute(
                    text("""
                        INSERT INTO learning_atoms
                        (id, card_id, front, back, atom_type, ccna_section_id, source_file, quality_score)
                        VALUES (:id, :card_id, :front, :back, :atom_type, :ccna_section_id, :source_file, :quality_score)
                    """),
                    atom
                )
                conn.commit()
                stats["created"] += 1
            except Exception as e:
                stats["errors"].append(f"{atom['card_id']}: {e}")
                logger.error(f"Failed to import {atom['card_id']}: {e}")

    return stats


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Import ITN Practice Final Exam questions")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually insert, just show what would be done")
    parser.add_argument("--file", default="ITNPracticeFinalExam.txt", help="Source file to parse")
    args = parser.parse_args()

    filepath = Path(args.file)
    if not filepath.exists():
        filepath = Path(__file__).parent.parent / args.file

    if not filepath.exists():
        logger.error(f"File not found: {filepath}")
        return

    logger.info(f"Parsing {filepath}...")
    questions = parse_itn_exam(filepath)
    logger.info(f"Found {len(questions)} questions")

    # Show breakdown by type
    mcq_count = sum(1 for q in questions if q["atom_type"] == "mcq")
    matching_count = sum(1 for q in questions if q["atom_type"] == "matching")
    logger.info(f"  MCQ: {mcq_count}, Matching: {matching_count}")

    # Convert to atoms
    atoms = [create_atom_from_question(q) for q in questions]
    atoms = [a for a in atoms if a]

    logger.info(f"Created {len(atoms)} atoms")

    # Import
    stats = import_atoms(atoms, dry_run=args.dry_run)

    logger.info(f"Import complete: created={stats['created']}, skipped={stats['skipped']}")
    if stats["errors"]:
        for err in stats["errors"][:5]:
            logger.error(err)


if __name__ == "__main__":
    main()
