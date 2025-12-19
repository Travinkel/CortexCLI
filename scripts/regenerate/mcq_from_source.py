"""
MCQ Regeneration Script - Parse CCNA source files and regenerate proper MCQs.

This script:
1. Reads CCNAModule*.txt and ITN*.txt source files
2. Parses questions, options, and identifies correct answers from explanations
3. Generates properly formatted MCQs with correct indices set
4. Inserts into database replacing broken MCQs
"""

import json
import re
import uuid
from pathlib import Path
from typing import Optional

# Source files to process
SOURCE_FILES = [
    "CCNAModule1-3.txt",
    "CCNAModule4-7.txt",
    "CCNAModule8-10.txt",
    "CCNAModule11-13.txt",
    "CCNAModule14-15.txt",
    "CCNAModule16-17.txt",
    "ITNFinalPacketTracer.txt",
    "ITNPracticeFinalExam.txt",
    "ITNPracticeTest.txt",
    "ITNSkillsAssessment.txt",
]

BASE_DIR = Path(__file__).parent.parent.parent


def parse_module_range(filename: str) -> tuple[int, int]:
    """Extract module range from filename like CCNAModule11-13.txt"""
    match = re.search(r'Module(\d+)-(\d+)', filename)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r'Module(\d+)', filename)
    if match:
        m = int(match.group(1))
        return m, m
    # ITN files default to module range
    if 'ITN' in filename:
        return 1, 17
    return 0, 0


def parse_questions(content: str, source_file: str) -> list[dict]:
    """
    Parse MCQ questions from source content.

    Returns list of dicts with:
    - question_num: int
    - question_text: str
    - options: list[str]
    - correct_indices: list[int]
    - explanation: str
    - is_multi_select: bool
    - required_count: int
    """
    questions = []

    # Split by question numbers
    # Pattern: number followed by period at start of line
    parts = re.split(r'\n(\d+)\.\s+', content)

    # parts[0] is header, then alternating [num, text, num, text...]
    for i in range(1, len(parts) - 1, 2):
        q_num = int(parts[i])
        q_content = parts[i + 1].strip()

        # Split into question + options + explanation
        lines = q_content.split('\n')

        # Find question text (first non-empty lines until we hit options)
        question_lines = []
        option_start = 0

        for j, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            # Check if this looks like an option (short line, or starts with *)
            if j > 0 and len(line) < 100 and not line.startswith('Explanation'):
                # Might be start of options
                option_start = j
                break
            question_lines.append(line)

        question_text = ' '.join(question_lines)

        # Check for multi-select indicator
        is_multi = 'Choose three' in question_text or 'Choose two' in question_text
        required_count = 3 if 'Choose three' in question_text else (2 if 'Choose two' in question_text else 1)

        # Extract options and explanation
        options = []
        explanation = ""
        correct_answers = []

        in_explanation = False
        for line in lines[option_start:]:
            line = line.strip()
            if not line:
                continue

            if line.startswith('Explanation:'):
                in_explanation = True
                explanation = line[12:].strip()
                continue

            if in_explanation:
                # After explanation, look for repeated answers (these are correct)
                # Common pattern: correct answers are listed again after explanation
                if any(opt.lower() == line.lower() for opt in options):
                    correct_answers.append(line)
                else:
                    explanation += ' ' + line
            else:
                # This is an option
                # Remove leading markers like *, -, numbers
                clean_opt = re.sub(r'^[\*\-\d\.\)\s]+', '', line).strip()
                if clean_opt and len(clean_opt) > 1:
                    options.append(clean_opt)

        # Determine correct indices
        correct_indices = []
        if correct_answers:
            for ans in correct_answers:
                for idx, opt in enumerate(options):
                    if opt.lower() == ans.lower() or ans.lower() in opt.lower():
                        if idx not in correct_indices:
                            correct_indices.append(idx)

        # If no correct answers found, try to infer from explanation
        if not correct_indices and explanation:
            exp_lower = explanation.lower()

            # Common patterns in explanations that reveal the answer:
            # "Therefore, the prefix length is /27"
            # "The correct answer is X"
            # "X is the correct answer"
            # "gives 62 usable host addresses" -> 62

            answer_patterns = [
                r'(?:therefore|thus|so)[,\s]+(?:the\s+)?(?:answer|prefix|mask|result)\s+(?:is|would be)\s+([^\.\,]+)',
                r'(?:the\s+)?(?:correct\s+)?answer\s+(?:is|would be)\s+([^\.\,]+)',
                r'prefix\s+(?:length\s+)?is\s+(/\d+)',
                r'subnet\s+mask\s+(?:is|would be)\s+([\d\.]+|/\d+)',
                r'(\d+)\s+usable?\s+(?:host\s+)?addresses',
                r'provides?\s+(\d+)\s+(?:host\s+)?addresses',
                r'2\^\d+\s*[-–]\s*2\s*=\s*(\d+)',
                r'yields?\s+(\d+)',
            ]

            for pattern in answer_patterns:
                match = re.search(pattern, exp_lower)
                if match:
                    answer_hint = match.group(1).strip()
                    # Find matching option
                    for idx, opt in enumerate(options):
                        opt_lower = opt.lower().strip()
                        if answer_hint in opt_lower or opt_lower in answer_hint:
                            if idx not in correct_indices:
                                correct_indices.append(idx)
                                break
                    if correct_indices:
                        break

            # Fallback: check if any option appears verbatim in explanation
            if not correct_indices:
                for idx, opt in enumerate(options):
                    opt_clean = opt.strip().lower()
                    if len(opt_clean) > 3 and opt_clean in exp_lower:
                        # Check it's not negated
                        neg_patterns = [f'not {opt_clean}', f'{opt_clean} is not', f'{opt_clean} will not']
                        if not any(re.search(p, exp_lower) for p in neg_patterns):
                            if idx not in correct_indices:
                                correct_indices.append(idx)

        # For single-answer MCQs, if still no correct found, mark first option
        # (This is a fallback - ideally all should be parsed correctly)
        if not correct_indices and not is_multi and options:
            # Try one more heuristic: first option after "Explanation" mention
            pass  # Don't guess, leave empty for manual review

        if options:  # Only add if we have options
            questions.append({
                'question_num': q_num,
                'question_text': question_text,
                'options': options,
                'correct_indices': correct_indices,
                'explanation': explanation,
                'is_multi_select': is_multi,
                'required_count': required_count,
                'source_file': source_file,
            })

    return questions


def generate_card_id(source_file: str, q_num: int, atom_type: str = "mcq") -> str:
    """Generate a unique card ID based on source and question number."""
    # Extract module info from filename
    if 'Module' in source_file:
        match = re.search(r'Module(\d+)-?(\d+)?', source_file)
        if match:
            start = match.group(1)
            end = match.group(2) or start
            prefix = f"CPE-M{start}-{end}"
    elif 'ITN' in source_file:
        if 'Final' in source_file:
            prefix = "ITN-FINAL"
        elif 'Practice' in source_file:
            prefix = "ITN-PRAC"
        elif 'Skills' in source_file:
            prefix = "ITN-SKILL"
        else:
            prefix = "ITN"
    else:
        prefix = "GEN"

    return f"{prefix}-{atom_type.upper()}-{q_num:03d}"


def create_mcq_back(options: list[str], correct_indices: list[int],
                    is_multi: bool, required_count: int, explanation: str) -> str:
    """Create properly formatted MCQ back field as JSON."""
    # Handle single vs multi select
    if is_multi:
        correct = correct_indices if len(correct_indices) > 1 else correct_indices[0] if correct_indices else None
    else:
        correct = correct_indices[0] if correct_indices else None

    data = {
        "options": options,
        "correct": correct,
        "multi_select": is_multi,
        "required_count": required_count,
        "explanation": explanation,
    }
    return json.dumps(data)


def process_source_files(dry_run: bool = True):
    """Process all source files and generate MCQs."""
    all_mcqs = []

    for filename in SOURCE_FILES:
        filepath = BASE_DIR / filename
        if not filepath.exists():
            print(f"[SKIP] {filename} not found")
            continue

        print(f"[PARSE] {filename}")
        content = filepath.read_text(encoding='utf-8', errors='replace')
        questions = parse_questions(content, filename)

        mod_start, mod_end = parse_module_range(filename)

        for q in questions:
            card_id = generate_card_id(filename, q['question_num'])

            # Create properly formatted back
            back = create_mcq_back(
                q['options'],
                q['correct_indices'],
                q['is_multi_select'],
                q['required_count'],
                q['explanation'],
            )

            mcq = {
                'id': str(uuid.uuid4()),
                'card_id': card_id,
                'atom_type': 'mcq',
                'front': q['question_text'],
                'back': back,
                'module_number': mod_start,  # Use start module
                'source_file': filename,
                'has_correct': len(q['correct_indices']) > 0,
            }
            all_mcqs.append(mcq)

        print(f"  -> {len(questions)} questions parsed")

    # Stats
    with_correct = sum(1 for m in all_mcqs if m['has_correct'])
    without_correct = len(all_mcqs) - with_correct

    print(f"\n[SUMMARY]")
    print(f"  Total MCQs: {len(all_mcqs)}")
    print(f"  With correct answer: {with_correct}")
    print(f"  Missing correct: {without_correct}")

    if dry_run:
        print("\n[DRY RUN] No database changes made")
        # Show sample
        if all_mcqs:
            print("\n[SAMPLE MCQ]")
            sample = all_mcqs[10] if len(all_mcqs) > 10 else all_mcqs[0]
            print(f"  Card ID: {sample['card_id']}")
            print(f"  Front: {sample['front'][:80]}...")
            back_data = json.loads(sample['back'])
            print(f"  Options: {len(back_data['options'])}")
            print(f"  Correct: {back_data['correct']}")
            print(f"  Multi-select: {back_data['multi_select']}")
    else:
        # Insert into database
        insert_mcqs(all_mcqs)

    return all_mcqs


def insert_mcqs(mcqs: list[dict]):
    """Insert MCQs into database, replacing any existing with same card_id."""
    import sys
    sys.path.insert(0, str(BASE_DIR))

    from sqlalchemy import text
    from src.db.database import engine

    with engine.begin() as conn:
        # Delete existing MCQs that we're regenerating
        card_ids = [m['card_id'] for m in mcqs]
        if card_ids:
            conn.execute(
                text("DELETE FROM learning_atoms WHERE card_id = ANY(:ids)"),
                {"ids": card_ids}
            )

        # Insert new MCQs
        for mcq in mcqs:
            if not mcq['has_correct']:
                continue  # Skip MCQs without correct answer

            conn.execute(
                text("""
                    INSERT INTO learning_atoms (id, card_id, atom_type, front, back, quality_score)
                    VALUES (:id, :card_id, :atom_type, :front, :back, 0.8)
                """),
                {
                    'id': mcq['id'],
                    'card_id': mcq['card_id'],
                    'atom_type': mcq['atom_type'],
                    'front': mcq['front'],
                    'back': mcq['back'],
                }
            )

        print(f"[DB] Inserted {sum(1 for m in mcqs if m['has_correct'])} MCQs")


if __name__ == '__main__':
    import sys
    dry_run = '--execute' not in sys.argv
    process_source_files(dry_run=dry_run)
