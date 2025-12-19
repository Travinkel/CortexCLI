#!/usr/bin/env python3
"""
True/False Quality Audit

Identifies malformed T/F atoms:
- Truncated statements (cut off mid-sentence)
- "is defined as:" pattern (often confusing)
- Code blocks in questions (hard to read)
- Factually incorrect definition swaps
- Very short statements

Run with --fix to delete critical issues and flag others for regeneration.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from sqlalchemy import create_engine, text

from config import get_settings

# Quality issue patterns for T/F atoms
TF_QUALITY_ISSUES = {
    "trick_question": {
        "name": "Trick question (modified to be false with no real explanation)",
        "sql_pattern": "back LIKE '%modified to be false%'",
        "severity": "critical",
        "action": "flag",  # These need regeneration, not deletion
    },
    "truncated_front": {
        "name": "Truncated front (ends mid-word/sentence)",
        "sql_pattern": r"""
            front ~ '\.\.\.$'
            OR front ~ '[a-z]$'
            OR front ~ ',$'
            OR front ~ ':$'
        """,
        "severity": "critical",
        "action": "delete",
    },
    "is_defined_as": {
        "name": "'X is defined as: Y' pattern (confusing)",
        "sql_pattern": "front LIKE '%is defined as:%'",
        "severity": "high",
        "action": "flag",
    },
    "note_prefix": {
        "name": "Starts with 'Note:' (not a proper statement)",
        "sql_pattern": "front LIKE 'Note:%' OR front LIKE 'Note: is defined as:%'",
        "severity": "critical",
        "action": "delete",
    },
    "code_blocks": {
        "name": "Contains code blocks (hard to read in CLI)",
        "sql_pattern": "front LIKE '%```%' OR back LIKE '%```%'",
        "severity": "medium",
        "action": "flag",
    },
    "malformed_json_back": {
        "name": "Malformed JSON in back field",
        "sql_pattern": """
            back NOT LIKE '%}%'
            OR back LIKE '%{\"answer\":%' AND back NOT LIKE '%}%'
        """,
        "severity": "critical",
        "action": "delete",
    },
    "very_short_front": {
        "name": "Very short front (< 30 chars)",
        "sql_pattern": "LENGTH(front) < 30",
        "severity": "high",
        "action": "flag",
    },
    "redundant_prefix": {
        "name": "Redundant 'True or False:' prefix",
        "sql_pattern": "front LIKE 'True or False:%'",
        "severity": "low",
        "action": "ignore",  # Just track, don't fix
    },
    "pipe_tables": {
        "name": "Contains table data (|)",
        "sql_pattern": "front LIKE '%|%' OR back LIKE '%|%'",
        "severity": "medium",
        "action": "flag",
    },
    "url_fragments": {
        "name": "Contains URL fragments",
        "sql_pattern": "front LIKE '%](https://%' OR front LIKE '%](http://%'",
        "severity": "critical",
        "action": "delete",
    },
}


def audit_true_false(conn, fix: bool = False) -> dict:
    """Run quality audit on all T/F atoms."""

    # Get total count
    result = conn.execute(text("SELECT COUNT(*) FROM clean_atoms WHERE atom_type = 'true_false'"))
    total = result.scalar()
    logger.info(f"Total True/False atoms: {total}")

    issues_found = {}
    atoms_to_delete = set()
    atoms_to_flag = set()

    for issue_id, issue in TF_QUALITY_ISSUES.items():
        try:
            sql_pattern = issue["sql_pattern"].strip()
            result = conn.execute(
                text(f"""
                SELECT id, card_id, front, back
                FROM clean_atoms
                WHERE atom_type = 'true_false'
                  AND ({sql_pattern})
            """)
            )

            rows = result.fetchall()
            count = len(rows)

            if count > 0:
                issues_found[issue_id] = {
                    "name": issue["name"],
                    "count": count,
                    "severity": issue["severity"],
                    "action": issue["action"],
                    "samples": [
                        (str(r.id), r.front[:60] if r.front else "", r.back[:40] if r.back else "")
                        for r in rows[:5]
                    ],
                }

                if issue["action"] == "delete":
                    atoms_to_delete.update(str(r.id) for r in rows)
                elif issue["action"] == "flag":
                    atoms_to_flag.update(str(r.id) for r in rows)

        except Exception as e:
            logger.warning(f"Could not check {issue_id}: {e}")

    # Print report
    logger.info("\n" + "=" * 70)
    logger.info("TRUE/FALSE QUALITY AUDIT REPORT")
    logger.info("=" * 70)

    critical_count = 0
    high_count = 0

    for issue_id, data in sorted(
        issues_found.items(),
        key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}[x[1]["severity"]],
    ):
        severity = data["severity"].upper()
        action = data["action"].upper()

        if data["severity"] == "critical":
            critical_count += data["count"]
        elif data["severity"] == "high":
            high_count += data["count"]

        logger.info(f"\n[{severity}] {data['name']}: {data['count']} atoms ({action})")

        for atom_id, front, back in data["samples"][:3]:
            logger.info(f"  - Q: {front}...")
            logger.info(f"    A: {back}...")

    logger.info("\n" + "-" * 70)
    logger.info("SUMMARY")
    logger.info("-" * 70)
    logger.info(f"Total T/F atoms: {total}")
    logger.info(f"Critical issues (DELETE): {len(atoms_to_delete)}")
    logger.info(f"High/Medium issues (FLAG): {len(atoms_to_flag)}")
    logger.info(f"Clean atoms: ~{total - len(atoms_to_delete) - len(atoms_to_flag)}")

    # Fix if requested
    if fix and atoms_to_delete:
        logger.info(f"\n[FIX MODE] Deleting {len(atoms_to_delete)} critical-issue atoms...")

        delete_list = list(atoms_to_delete)
        for i in range(0, len(delete_list), 100):
            batch = delete_list[i : i + 100]
            placeholders = ",".join(f"'{aid}'::uuid" for aid in batch)
            conn.execute(text(f"DELETE FROM clean_atoms WHERE id IN ({placeholders})"))

        conn.commit()
        logger.info(f"Deleted {len(atoms_to_delete)} malformed T/F atoms")

        # Get new count
        result = conn.execute(
            text("SELECT COUNT(*) FROM clean_atoms WHERE atom_type = 'true_false'")
        )
        new_total = result.scalar()
        logger.info(f"Remaining T/F atoms: {new_total}")

    if fix and atoms_to_flag:
        logger.info(f"\n[FIX MODE] Flagging {len(atoms_to_flag)} atoms for review...")

        flag_list = list(atoms_to_flag)
        for i in range(0, len(flag_list), 100):
            batch = flag_list[i : i + 100]
            placeholders = ",".join(f"'{aid}'::uuid" for aid in batch)
            conn.execute(
                text(f"""
                UPDATE clean_atoms
                SET quality_score = LEAST(COALESCE(quality_score, 100), 40.0),
                    source = COALESCE(source, '') || '_tf_flagged'
                WHERE id IN ({placeholders})
            """)
            )

        conn.commit()
        logger.info(f"Flagged {len(atoms_to_flag)} atoms with quality_score <= 40")

    return {
        "total": total,
        "issues": issues_found,
        "to_delete": len(atoms_to_delete),
        "to_flag": len(atoms_to_flag),
        "clean": total - len(atoms_to_delete) - len(atoms_to_flag),
    }


def check_json_validity(conn) -> None:
    """Check if T/F backs are valid JSON."""
    result = conn.execute(
        text("""
        SELECT id, front, back FROM clean_atoms
        WHERE atom_type = 'true_false'
        LIMIT 100
    """)
    )

    valid = 0
    invalid = 0

    for row in result:
        try:
            data = json.loads(row.back)
            if "answer" in data:
                valid += 1
            else:
                invalid += 1
                logger.warning(f"Missing 'answer' key: {row.back[:50]}")
        except json.JSONDecodeError:
            invalid += 1
            logger.warning(f"Invalid JSON: {row.back[:50]}")

    logger.info(f"\nJSON validity (sample of 100): {valid} valid, {invalid} invalid")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Audit True/False atom quality")
    parser.add_argument("--fix", action="store_true", help="Delete/flag malformed atoms")
    parser.add_argument("--check-json", action="store_true", help="Check JSON validity")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.database_url)

    with engine.connect() as conn:
        if args.check_json:
            check_json_validity(conn)
        else:
            audit_true_false(conn, fix=args.fix)


if __name__ == "__main__":
    main()
