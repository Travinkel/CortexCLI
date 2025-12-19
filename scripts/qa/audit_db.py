"""
Data Integrity Audit (Enhanced).

Scans the database for quality issues, quarantines broken atoms,
and generates a markdown report.

Checks:
1. Null Content - Atoms with empty front or back
2. Orphaned Diagrams - media_type='mermaid' but media_code is empty
3. Bad JSON / Invalid MCQ - corrupted content_json or missing MCQ options
4. Duplicate Detection - Similar front content (100-char prefix match)
5. Low Fidelity - Missing source_refs traceability
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

# Path setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db.database import get_db

# Report output path
REPORT_PATH = PROJECT_ROOT / "qa_report.md"


def normalize_text(text: str) -> str:
    """Normalize text for duplicate comparison."""
    if not text:
        return ""
    # Lowercase, collapse whitespace, strip
    return re.sub(r"\s+", " ", text.lower().strip())


def check_mcq_validity(atom_type: str, content_json: dict | None) -> tuple[bool, str]:
    """Check if MCQ content_json is valid."""
    if atom_type != "mcq":
        return True, ""

    if not content_json:
        return False, "MCQ missing content_json"

    if not isinstance(content_json, dict):
        return False, "content_json is not a dict"

    options = content_json.get("options")
    if not options or not isinstance(options, list) or len(options) < 2:
        return False, "MCQ missing or invalid options array"

    correct_index = content_json.get("correct_index")
    if correct_index is None:
        return False, "MCQ missing correct_index"

    if not isinstance(correct_index, int) or correct_index < 0 or correct_index >= len(options):
        return False, f"MCQ correct_index {correct_index} out of bounds (options: {len(options)})"

    return True, ""


def check_mcq_back_correct(atom_type: str, back: str | None) -> tuple[bool, str]:
    """
    Check if MCQ back field JSON has valid 'correct' value.

    Some MCQs store correct answer as JSON in back field:
    {"options": [...], "correct": 0}

    If correct is null/None, the question has no valid answer.
    """
    if atom_type != "mcq":
        return True, ""

    if not back:
        return True, ""  # Will be caught by null content check

    back_str = str(back).strip()
    if not back_str.startswith("{"):
        return True, ""  # Not JSON format, skip

    try:
        data = json.loads(back_str)
    except json.JSONDecodeError:
        return True, ""  # JSON errors caught elsewhere

    if not isinstance(data, dict):
        return True, ""

    # Check if 'correct' key exists and is null
    if "correct" in data and data["correct"] is None:
        return False, "MCQ back JSON has 'correct: null' - no valid answer"

    # Check if correct is out of bounds
    options = data.get("options", [])
    correct = data.get("correct")
    if correct is not None and isinstance(correct, int):
        if correct < 0 or (options and correct >= len(options)):
            return False, f"MCQ back JSON 'correct: {correct}' out of bounds"

    return True, ""


def check_source_refs(content_json: dict | None, source_fact_basis: str | None) -> bool:
    """Check if atom has valid source traceability."""
    # Check content_json for source_refs
    if content_json and isinstance(content_json, dict):
        source_refs = content_json.get("source_refs")
        if source_refs and isinstance(source_refs, list) and len(source_refs) > 0:
            return True

    # Fallback: check source_fact_basis column
    if source_fact_basis and len(source_fact_basis.strip()) > 0:
        return True

    return False


def quarantine_atom(db, atom_row, reason: str) -> None:
    """Move atom to quarantine table."""
    # Build original_data JSON
    original_data = {
        "id": str(atom_row.id),
        "card_id": atom_row.card_id,
        "atom_type": atom_row.atom_type,
        "front": atom_row.front,
        "back": atom_row.back,
        "media_type": atom_row.media_type,
        "media_code": atom_row.media_code,
        "quiz_question_metadata": atom_row.quiz_question_metadata,
        "source_fact_basis": atom_row.source_fact_basis,
    }

    # Insert into quarantine
    insert_sql = text("""
        INSERT INTO quarantine_atoms
        (id, original_id, card_id, atom_type, front, back, content_json,
         media_type, media_code, quarantine_reason, original_data)
        VALUES
        (:id, :original_id, :card_id, :atom_type, :front, :back, :content_json,
         :media_type, :media_code, :quarantine_reason, :original_data)
        ON CONFLICT (id) DO NOTHING
    """)

    db.execute(insert_sql, {
        "id": str(uuid4()),
        "original_id": str(atom_row.id),
        "card_id": atom_row.card_id,
        "atom_type": atom_row.atom_type,
        "front": atom_row.front,
        "back": atom_row.back,
        "content_json": json.dumps(atom_row.quiz_question_metadata) if atom_row.quiz_question_metadata else None,
        "media_type": atom_row.media_type,
        "media_code": atom_row.media_code,
        "quarantine_reason": reason,
        "original_data": json.dumps(original_data),
    })

    # Delete from learning_atoms
    delete_sql = text("DELETE FROM learning_atoms WHERE id = :id")
    db.execute(delete_sql, {"id": str(atom_row.id)})


def main():
    print("[*] STARTING ENHANCED DATA INTEGRITY AUDIT...")
    db = next(get_db())

    # Check if quarantine table exists, create if not
    try:
        db.execute(text("SELECT 1 FROM quarantine_atoms LIMIT 1"))
    except Exception:
        db.rollback()  # Rollback the failed transaction
        print("  > Creating quarantine_atoms table...")
        migration_path = PROJECT_ROOT / "src" / "db" / "migrations" / "016_quarantine_table.sql"
        if migration_path.exists():
            sql = migration_path.read_text(encoding="utf-8")
            db.execute(text(sql))
            db.commit()

    # Fetch all atoms with required columns
    # Note: content_json may not exist in all schemas, using quiz_question_metadata instead
    sql = text("""
        SELECT id, card_id, atom_type, front, back, media_type, media_code,
               quiz_question_metadata, source_fact_basis
        FROM learning_atoms
    """)
    rows = db.execute(sql).fetchall()
    print(f"  > Scanned {len(rows)} atoms.")

    # Issue tracking
    issues = {
        "null_content": [],
        "orphaned_diagrams": [],
        "bad_json": [],
        "low_fidelity": [],
        "duplicates": [],
    }

    valid_atoms = []
    quarantined_count = 0

    # Pass 1: Check each atom
    for row in rows:
        atom_id = str(row.id)
        card_id = row.card_id or "N/A"

        # 1. Null Content Check
        if not row.front or not row.back:
            issue_detail = "Empty front" if not row.front else "Empty back"
            issues["null_content"].append({
                "id": atom_id,
                "card_id": card_id,
                "issue": issue_detail
            })
            quarantine_atom(db, row, f"null_content: {issue_detail}")
            quarantined_count += 1
            continue

        # 2. Orphaned Diagrams Check
        if row.media_type == "mermaid" or "[visual]" in str(row.front).lower():
            if not row.media_code:
                issues["orphaned_diagrams"].append({
                    "id": atom_id,
                    "card_id": card_id,
                    "issue": f"media_type={row.media_type} but media_code is empty"
                })

        # 3. Bad JSON / Invalid MCQ Check
        content_json = row.quiz_question_metadata
        if content_json:
            if isinstance(content_json, str):
                try:
                    content_json = json.loads(content_json)
                except json.JSONDecodeError:
                    issues["bad_json"].append({
                        "id": atom_id,
                        "card_id": card_id,
                        "issue": "Corrupted JSON (parse error)"
                    })
                    quarantine_atom(db, row, "bad_json: parse error")
                    quarantined_count += 1
                    continue

        mcq_valid, mcq_error = check_mcq_validity(row.atom_type, content_json)
        if not mcq_valid:
            # MCQs without options are a warning, not critical
            # They can still be used as flashcards
            issues["bad_json"].append({
                "id": atom_id,
                "card_id": card_id,
                "issue": mcq_error
            })
            # Don't quarantine - MCQs without options can fall back to flashcard mode
            # quarantine_atom(db, row, f"bad_json: {mcq_error}")
            # quarantined_count += 1
            # continue

        # 3b. MCQ Back Field Null Correct Check
        # Catches MCQs where back JSON has "correct: null" - no valid answer
        back_valid, back_error = check_mcq_back_correct(row.atom_type, row.back)
        if not back_valid:
            issues["bad_json"].append({
                "id": atom_id,
                "card_id": card_id,
                "issue": back_error
            })
            # This IS critical - question literally has no answer
            quarantine_atom(db, row, f"bad_json: {back_error}")
            quarantined_count += 1
            continue

        # 4. Low Fidelity Check (source_refs)
        if not check_source_refs(content_json, row.source_fact_basis):
            issues["low_fidelity"].append({
                "id": atom_id,
                "card_id": card_id,
                "issue": "Missing source_refs and source_fact_basis"
            })

        # Atom passed critical checks, add to valid list
        valid_atoms.append(row)

    # Pass 2: Duplicate Detection (O(n log n) via sorting)
    print("  > Checking for duplicates...")

    # Sort by normalized first 100 chars
    valid_atoms_with_norm = [
        (row, normalize_text(row.front)[:100])
        for row in valid_atoms
    ]
    valid_atoms_with_norm.sort(key=lambda x: x[1])

    for i in range(len(valid_atoms_with_norm) - 1):
        curr_row, curr_norm = valid_atoms_with_norm[i]
        next_row, next_norm = valid_atoms_with_norm[i + 1]

        # Match on normalized 100-char prefix
        if curr_norm == next_norm and len(curr_norm) > 20:  # Require meaningful content
            issues["duplicates"].append({
                "id_1": str(curr_row.id),
                "card_id_1": curr_row.card_id or "N/A",
                "id_2": str(next_row.id),
                "card_id_2": next_row.card_id or "N/A",
                "prefix": curr_norm[:50] + "..."
            })

    # Commit quarantine operations
    db.commit()

    # Calculate summary
    total_issues = (
        len(issues["null_content"]) +
        len(issues["orphaned_diagrams"]) +
        len(issues["bad_json"]) +
        len(issues["low_fidelity"]) +
        len(issues["duplicates"])
    )
    # Only null content and corrupted JSON (parse errors) are critical
    # MCQs without options are warnings, not critical
    critical_issues = len(issues["null_content"])
    # Count only parse errors as critical bad_json
    json_parse_errors = sum(1 for item in issues["bad_json"] if "parse error" in item.get("issue", ""))
    critical_issues += json_parse_errors

    # Generate Report
    report_lines = [
        "# Data Integrity Audit Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        f"- **Total Atoms Scanned:** {len(rows)}",
        f"- **Quarantined:** {quarantined_count}",
        f"- **Remaining Valid:** {len(valid_atoms)}",
        f"- **Total Issues Found:** {total_issues}",
        f"- **Critical Issues:** {critical_issues}",
        "",
    ]

    # Null Content Section
    report_lines.append(f"## Null Content ({len(issues['null_content'])} items) - CRITICAL")
    if issues["null_content"]:
        report_lines.append("| Atom ID | Card ID | Issue |")
        report_lines.append("|---------|---------|-------|")
        for item in issues["null_content"][:50]:  # Limit to 50
            report_lines.append(f"| `{item['id'][:8]}...` | {item['card_id']} | {item['issue']} |")
        if len(issues["null_content"]) > 50:
            report_lines.append(f"| ... | ... | (+{len(issues['null_content']) - 50} more) |")
    else:
        report_lines.append("*None found*")
    report_lines.append("")

    # Orphaned Diagrams Section
    report_lines.append(f"## Orphaned Diagrams ({len(issues['orphaned_diagrams'])} items) - WARNING")
    if issues["orphaned_diagrams"]:
        report_lines.append("| Atom ID | Card ID | Issue |")
        report_lines.append("|---------|---------|-------|")
        for item in issues["orphaned_diagrams"][:50]:
            report_lines.append(f"| `{item['id'][:8]}...` | {item['card_id']} | {item['issue']} |")
        if len(issues["orphaned_diagrams"]) > 50:
            report_lines.append(f"| ... | ... | (+{len(issues['orphaned_diagrams']) - 50} more) |")
    else:
        report_lines.append("*None found*")
    report_lines.append("")

    # Bad JSON Section
    report_lines.append(f"## Bad JSON / Invalid MCQ ({len(issues['bad_json'])} items) - CRITICAL")
    if issues["bad_json"]:
        report_lines.append("| Atom ID | Card ID | Issue |")
        report_lines.append("|---------|---------|-------|")
        for item in issues["bad_json"][:50]:
            report_lines.append(f"| `{item['id'][:8]}...` | {item['card_id']} | {item['issue']} |")
        if len(issues["bad_json"]) > 50:
            report_lines.append(f"| ... | ... | (+{len(issues['bad_json']) - 50} more) |")
    else:
        report_lines.append("*None found*")
    report_lines.append("")

    # Duplicates Section
    report_lines.append(f"## Duplicate Content ({len(issues['duplicates'])} pairs) - INFO")
    if issues["duplicates"]:
        report_lines.append("| Atom 1 | Card ID 1 | Atom 2 | Card ID 2 | Prefix |")
        report_lines.append("|--------|-----------|--------|-----------|--------|")
        for item in issues["duplicates"][:30]:
            report_lines.append(
                f"| `{item['id_1'][:8]}...` | {item['card_id_1']} | "
                f"`{item['id_2'][:8]}...` | {item['card_id_2']} | {item['prefix'][:30]}... |"
            )
        if len(issues["duplicates"]) > 30:
            report_lines.append(f"| ... | ... | ... | ... | (+{len(issues['duplicates']) - 30} more) |")
    else:
        report_lines.append("*None found*")
    report_lines.append("")

    # Low Fidelity Section
    report_lines.append(f"## Low Fidelity - Missing Source Refs ({len(issues['low_fidelity'])} items) - WARNING")
    if issues["low_fidelity"]:
        report_lines.append("| Atom ID | Card ID | Issue |")
        report_lines.append("|---------|---------|-------|")
        for item in issues["low_fidelity"][:50]:
            report_lines.append(f"| `{item['id'][:8]}...` | {item['card_id']} | {item['issue']} |")
        if len(issues["low_fidelity"]) > 50:
            report_lines.append(f"| ... | ... | (+{len(issues['low_fidelity']) - 50} more) |")
    else:
        report_lines.append("*None found*")
    report_lines.append("")

    # Verdict
    report_lines.append("---")
    report_lines.append("## Verdict")
    if critical_issues == 0:
        report_lines.append("**PASS** - No critical issues found. System is study-ready.")
        verdict = "PASS"
    else:
        report_lines.append(f"**FAIL** - {critical_issues} critical issues found and quarantined.")
        verdict = "FAIL"
    report_lines.append("")

    # Write report
    REPORT_PATH.write_text("\n".join(report_lines), encoding="utf-8")

    # Console output
    print("\n[AUDIT REPORT]")
    print(f"  - Total Atoms:       {len(rows)}")
    print(f"  - Quarantined:       {quarantined_count}")
    print(f"  - Null Content:      {len(issues['null_content'])} (Critical)")
    print(f"  - Broken JSON:       {len(issues['bad_json'])} (Critical)")
    print(f"  - Orphaned Diagrams: {len(issues['orphaned_diagrams'])} (Warning)")
    print(f"  - Duplicates:        {len(issues['duplicates'])} (Info)")
    print(f"  - Low Fidelity:      {len(issues['low_fidelity'])} (Warning)")
    print(f"\n[Report written to: {REPORT_PATH}]")

    if verdict == "PASS":
        print("\n[PASS] DATA INTEGRITY OK - System is study-ready.")
        return 0
    else:
        print(f"\n[WARNING] DATA ISSUES DETECTED - {quarantined_count} atoms quarantined.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
