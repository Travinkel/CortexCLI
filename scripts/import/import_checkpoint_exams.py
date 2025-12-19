"""
Import CCNA checkpoint exam questions from text files.

Parses questions, options, and explanations from exam dump files.
Infers correct answers from explanation text when possible.
"""
import json
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from src.db.database import engine

PROJECT_ROOT = Path(__file__).parent.parent.parent


def detect_multi_select(question_text: str) -> tuple[bool, int]:
    """
    Detect if a question requires multiple answers.
    Returns (is_multi_select, required_count).
    """
    q_lower = question_text.lower()

    # Patterns for multi-select questions
    patterns = [
        (r'choose\s+two', 2),
        (r'choose\s+three', 3),
        (r'choose\s+four', 4),
        (r'select\s+two', 2),
        (r'select\s+three', 3),
        (r'\(choose\s+2\)', 2),
        (r'\(choose\s+3\)', 3),
        (r'two\s+(?:answers|options|choices)', 2),
        (r'three\s+(?:answers|options|choices)', 3),
    ]

    for pattern, count in patterns:
        if re.search(pattern, q_lower):
            return True, count

    return False, 1


def infer_correct_answers_multi(options: list[str], explanation: str, required_count: int) -> Optional[list[int]]:
    """
    Infer multiple correct answer indices from explanation text.
    Returns list of indices for the most likely correct options.
    """
    if not explanation or not options:
        return None

    explanation_lower = explanation.lower()

    # Score each option
    scores = []
    for i, opt in enumerate(options):
        opt_clean = opt.lower().strip()
        score = 0

        if opt_clean in explanation_lower:
            score += 10

        opt_words = set(opt_clean.split())
        for word in opt_words:
            if len(word) > 3 and word in explanation_lower:
                score += 1

        scores.append((i, score))

    # Sort by score and take top N
    scores.sort(key=lambda x: x[1], reverse=True)
    top_scores = scores[:required_count]

    # Only return if we have reasonable confidence
    if all(s[1] >= 3 for s in top_scores):
        return sorted([s[0] for s in top_scores])

    return None


def infer_correct_answer(options: list[str], explanation: str) -> Optional[int]:
    """
    Try to infer the correct answer index from the explanation text.
    Returns the index of the most likely correct option, or None if unsure.
    """
    if not explanation or not options:
        return None

    explanation_lower = explanation.lower()

    # Score each option by how well it matches the explanation
    scores = []
    for i, opt in enumerate(options):
        opt_clean = opt.lower().strip()
        score = 0

        # Direct mention in explanation (weighted heavily)
        if opt_clean in explanation_lower:
            score += 10

        # Check for key phrases that indicate correctness
        correctness_phrases = [
            f"{opt_clean} is",
            f"the answer is {opt_clean}",
            f"correct answer is {opt_clean}",
            f"{opt_clean} provides",
            f"{opt_clean} allows",
            f"{opt_clean} enables",
            f"using {opt_clean}",
        ]
        for phrase in correctness_phrases:
            if phrase in explanation_lower:
                score += 5

        # Check if option words appear frequently
        opt_words = set(opt_clean.split())
        for word in opt_words:
            if len(word) > 3 and word in explanation_lower:
                score += 1

        scores.append(score)

    # Return the highest scoring option if it's significantly better
    if scores:
        max_score = max(scores)
        if max_score >= 5:  # Confidence threshold
            # Check if there's a clear winner
            winners = [i for i, s in enumerate(scores) if s == max_score]
            if len(winners) == 1:
                return winners[0]

    return None


def parse_exam_file(filepath: Path) -> list[dict]:
    """Parse a checkpoint exam text file into question structures."""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    questions = []

    # Split by question numbers (1. 2. 3. etc)
    # Pattern: number followed by period and space at start of line
    parts = re.split(r'\n(\d+)\.\s+', content)

    # First part is header, then alternating: number, content
    i = 1
    while i < len(parts) - 1:
        q_num = parts[i]
        q_content = parts[i + 1] if i + 1 < len(parts) else ""
        i += 2

        if not q_content.strip():
            continue

        # Parse the question content
        lines = q_content.strip().split('\n')

        # First line(s) are the question text (until we hit options)
        question_lines = []
        option_lines = []
        explanation_lines = []
        in_explanation = False
        in_options = False

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for explanation marker
            if line.lower().startswith("explanation:") or line.lower().startswith("explanation "):
                in_explanation = True
                exp_text = re.sub(r'^explanation[:\s]*', '', line, flags=re.IGNORECASE)
                if exp_text:
                    explanation_lines.append(exp_text)
                continue

            if in_explanation:
                # Stop at next question indicator or certain patterns
                if re.match(r'^\d+\.\s', line):
                    break
                explanation_lines.append(line)
                continue

            # Check if this looks like an option (short line, no period at end typically)
            # Options are usually single lines without much punctuation
            is_option = (
                len(line) < 200 and
                not line.endswith('.') or
                line.count('.') <= 1
            ) and not any(line.lower().startswith(x) for x in ['refer to', 'note:', 'hint:'])

            # Heuristic: if we haven't started options and line looks like question continuation
            if not in_options and (
                line.endswith('?') or
                line.endswith(':') or
                '(Choose' in line or
                'select' in line.lower() or
                line.startswith('Which') or
                line.startswith('What') or
                len(question_lines) == 0
            ):
                question_lines.append(line)
            elif is_option and len(line) > 2:
                in_options = True
                # Clean option text
                opt = re.sub(r'^[a-dA-D][\.\)]\s*', '', line)  # Remove a. b. c. d. prefixes
                opt = re.sub(r'^\*+', '', opt)  # Remove asterisks
                opt = opt.strip()
                if opt and opt not in ['Other case']:  # Skip placeholder options
                    option_lines.append(opt)
            elif not in_options:
                question_lines.append(line)

        question_text = ' '.join(question_lines).strip()
        explanation_text = ' '.join(explanation_lines).strip()

        # Skip if no real question or options
        if not question_text or len(option_lines) < 2:
            continue

        # Detect multi-select
        is_multi, required_count = detect_multi_select(question_text)

        # Try to infer correct answer(s)
        if is_multi:
            correct_indices = infer_correct_answers_multi(option_lines, explanation_text, required_count)
            correct_idx = None  # Not used for multi-select
        else:
            correct_indices = None
            correct_idx = infer_correct_answer(option_lines, explanation_text)

        questions.append({
            "number": int(q_num),
            "question": question_text,
            "options": option_lines,
            "correct_index": correct_idx,
            "correct_indices": correct_indices,
            "is_multi_select": is_multi,
            "required_count": required_count,
            "explanation": explanation_text,
        })

    return questions


def determine_atom_type(question: dict) -> str:
    """Determine the atom type based on question structure."""
    q_text = question["question"].lower()
    options = question["options"]

    # Check for True/False
    if len(options) == 2:
        opts_lower = [o.lower() for o in options]
        if set(opts_lower) == {"true", "false"}:
            return "true_false"

    # Check for matching questions
    if "match" in q_text or any("->" in opt or "\t" in opt for opt in options):
        return "matching"

    # Default to MCQ
    return "mcq"


def infer_section_id(question: dict, source_file: str) -> str:
    """Infer CCNA section ID from question content and source file."""
    q_text = question["question"].lower()

    # Module-based inference from filename
    if "1-3" in source_file:
        return "1.1"  # Basic networking
    elif "4-7" in source_file:
        return "4.1"  # Physical layer
    elif "8-10" in source_file:
        return "8.1"  # Network layer
    elif "11-13" in source_file:
        return "11.1"  # IPv4 addressing
    elif "14-15" in source_file:
        return "14.1"  # Transport layer
    elif "16-17" in source_file:
        return "16.1"  # Application layer

    # ITN files - general networking
    if "itn" in source_file.lower():
        return "1.1"

    # Keyword-based inference
    keyword_sections = {
        "subnet": "11.4",
        "ipv4": "11.1",
        "ipv6": "12.1",
        "ethernet": "6.1",
        "vlan": "6.2",
        "switch": "6.1",
        "router": "14.1",
        "dhcp": "13.2",
        "dns": "13.3",
        "tcp": "14.1",
        "udp": "14.2",
        "osi": "3.1",
        "mac address": "6.1",
        "arp": "9.1",
        "icmp": "9.2",
        "acl": "7.2",
        "static route": "15.1",
    }

    for keyword, section in keyword_sections.items():
        if keyword in q_text:
            return section

    return "1.1"  # Default


def create_card_id(source_file: str, q_num: int, atom_type: str) -> str:
    """Create a unique card ID for the question."""
    # Extract source identifier
    if "Module1-3" in source_file or "1-3" in source_file:
        src = "CPE-M1-3"
    elif "Module4-7" in source_file or "4-7" in source_file:
        src = "CPE-M4-7"
    elif "Module8-10" in source_file or "8-10" in source_file:
        src = "CPE-M8-10"
    elif "Module11-13" in source_file or "11-13" in source_file:
        src = "CPE-M11-13"
    elif "Module14-15" in source_file or "14-15" in source_file:
        src = "CPE-M14-15"
    elif "Module16-17" in source_file or "16-17" in source_file:
        src = "CPE-M16-17"
    elif "FinalPacketTracer" in source_file:
        src = "ITN-PT"
    elif "PracticeFinal" in source_file:
        src = "ITN-PF"
    elif "SkillsAssessment" in source_file:
        src = "ITN-SA"
    elif "PracticeTest" in source_file:
        src = "ITN-TEST"
    else:
        src = "CPE"

    type_abbr = {"mcq": "MCQ", "true_false": "TF", "matching": "MATCH"}.get(atom_type, "Q")
    return f"{src}-{type_abbr}-{q_num:03d}"


def import_questions(filepath: Path, dry_run: bool = False) -> dict:
    """Import questions from a single file."""
    print(f"\n{'='*60}")
    print(f"Processing: {filepath.name}")
    print("="*60)

    questions = parse_exam_file(filepath)
    print(f"Parsed {len(questions)} questions")

    imported = 0
    skipped = 0
    needs_review = 0

    with engine.begin() as conn:
        for q in questions:
            atom_type = determine_atom_type(q)
            card_id = create_card_id(filepath.name, q["number"], atom_type)
            section_id = infer_section_id(q, filepath.name)

            # Check for duplicates
            exists = conn.execute(
                text("SELECT 1 FROM learning_atoms WHERE card_id = :card_id"),
                {"card_id": card_id}
            ).fetchone()

            if exists:
                print(f"  SKIP {card_id} (exists)")
                skipped += 1
                continue

            # Also check for duplicate question text
            dupe = conn.execute(
                text("SELECT card_id FROM learning_atoms WHERE front = :front LIMIT 1"),
                {"front": q["question"]}
            ).fetchone()

            if dupe:
                print(f"  SKIP {card_id} (duplicate of {dupe[0]})")
                skipped += 1
                continue

            # Build back field based on atom type
            if atom_type == "mcq":
                back_data = {
                    "options": q["options"],
                    "explanation": q["explanation"] if q["explanation"] else None
                }
                # Handle multi-select vs single-select
                if q["is_multi_select"]:
                    back_data["multi_select"] = True
                    back_data["required_count"] = q["required_count"]
                    back_data["correct"] = q["correct_indices"]  # List of indices
                else:
                    back_data["multi_select"] = False
                    back_data["correct"] = q["correct_index"]  # Single index
                back = json.dumps(back_data)
            elif atom_type == "true_false":
                # Find correct answer
                correct_opt = q["options"][q["correct_index"]] if q["correct_index"] is not None else None
                back = json.dumps({
                    "correct": correct_opt,
                    "explanation": q["explanation"]
                })
            else:
                back = json.dumps({
                    "options": q["options"],
                    "explanation": q["explanation"]
                })

            # Determine if review is needed
            if q["is_multi_select"]:
                review_flag = q["correct_indices"] is None
            else:
                review_flag = q["correct_index"] is None
            if review_flag:
                needs_review += 1

            if dry_run:
                status = "[REVIEW]" if review_flag else "[OK]"
                print(f"  {status} {card_id}: {q['question'][:50]}...")
                continue

            # Insert
            conn.execute(
                text("""
                    INSERT INTO learning_atoms (
                        card_id, front, back, atom_type, ccna_section_id,
                        source, needs_review, created_at
                    ) VALUES (
                        :card_id, :front, :back, :atom_type, :section_id,
                        :source, :needs_review, NOW()
                    )
                """),
                {
                    "card_id": card_id,
                    "front": q["question"],
                    "back": back,
                    "atom_type": atom_type,
                    "section_id": section_id,
                    "source": f"checkpoint_{filepath.stem}",
                    "needs_review": review_flag,
                }
            )
            status = "[REVIEW]" if review_flag else "[OK]"
            print(f"  {status} {card_id}")
            imported += 1

    return {"imported": imported, "skipped": skipped, "needs_review": needs_review}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Import checkpoint exam questions")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually import")
    parser.add_argument("--file", type=str, help="Import specific file only")
    args = parser.parse_args()

    # Find all exam files
    exam_files = [
        PROJECT_ROOT / "CCNAModule1-3.txt",
        PROJECT_ROOT / "CCNAModule4-7.txt",
        PROJECT_ROOT / "CCNAModule8-10.txt",
        PROJECT_ROOT / "CCNAModule11-13.txt",
        PROJECT_ROOT / "CCNAModule14-15.txt",
        PROJECT_ROOT / "CCNAModule16-17.txt",
        PROJECT_ROOT / "ITNFinalPacketTracer.txt",
        PROJECT_ROOT / "ITNPracticeFinalExam.txt",
        PROJECT_ROOT / "ITNPracticeTest.txt",
        PROJECT_ROOT / "ITNSkillsAssessment.txt",
    ]

    if args.file:
        exam_files = [PROJECT_ROOT / args.file]

    total_imported = 0
    total_skipped = 0
    total_review = 0

    for filepath in exam_files:
        if not filepath.exists():
            print(f"SKIP: {filepath.name} not found")
            continue

        result = import_questions(filepath, dry_run=args.dry_run)
        total_imported += result["imported"]
        total_skipped += result["skipped"]
        total_review += result["needs_review"]

    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print("="*60)
    print(f"Total imported: {total_imported}")
    print(f"Total skipped:  {total_skipped}")
    print(f"Needs review:   {total_review}")


if __name__ == "__main__":
    main()
