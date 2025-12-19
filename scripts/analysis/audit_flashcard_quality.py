#!/usr/bin/env python3
"""
Flashcard Quality Audit

Identifies and optionally fixes malformed flashcards:
- "What is This?" questions (65+ found)
- Truncated/incomplete backs
- Generic "In X, what is Y?" patterns
- Table data (contains |)
- Very short backs

Run with --fix to mark low-quality atoms for regeneration.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from sqlalchemy import create_engine, text

from config import get_settings

# Quality issue patterns
QUALITY_ISSUES = {
    "what_is_this": {
        "name": "What is This? questions",
        "sql_pattern": "front LIKE '%What is This%'",
        "severity": "critical",
        "action": "delete",
    },
    "malformed_url_back": {
        "name": "Malformed URL fragment in back",
        "sql_pattern": "back LIKE '%](https://%' OR back LIKE '%](http://%'",
        "severity": "critical",
        "action": "delete",
    },
    "malformed_url_front": {
        "name": "Malformed URL fragment in front",
        "sql_pattern": "front LIKE '%](https://%' OR front LIKE '%](http://%'",
        "severity": "critical",
        "action": "delete",
    },
    "generic_in_what": {
        "name": "Generic 'In X, what concept' pattern",
        "sql_pattern": "front ~ '^In .+, what (is|are|concept)'",
        "severity": "high",
        "action": "flag",
    },
    "very_short_back": {
        "name": "Very short back (< 15 chars)",
        "sql_pattern": "LENGTH(back) < 15 AND back NOT LIKE '{%' AND back NOT LIKE '%](http%'",
        "severity": "critical",
        "action": "delete",
    },
    "truncated_back": {
        "name": "Truncated back (ends with comma/article)",
        "sql_pattern": "back ~ '(,|, |\\s(the|a|an|of|in|for|to|and|or))$'",
        "severity": "high",
        "action": "flag",
    },
    "table_data": {
        "name": "Contains table data (|)",
        "sql_pattern": "(front LIKE '%|%' OR back LIKE '%|%')",
        "severity": "medium",
        "action": "flag",
    },
    "missing_question_mark": {
        "name": "Front missing question mark",
        "sql_pattern": "front NOT LIKE '%?' AND front NOT LIKE '%{{c%'",
        "severity": "low",
        "action": "ignore",
    },
    "back_starts_lowercase": {
        "name": "Back starts with lowercase (possible truncation)",
        "sql_pattern": "back ~ '^[a-z]' AND back NOT LIKE '{%'",
        "severity": "medium",
        "action": "flag",
    },
}


def audit_flashcards(conn, fix: bool = False) -> dict:
    """Run quality audit on all flashcards."""

    # Get total count
    result = conn.execute(text("SELECT COUNT(*) FROM clean_atoms WHERE atom_type = 'flashcard'"))
    total = result.scalar()
    logger.info(f"Total flashcards: {total}")

    issues_found = {}
    atoms_to_delete = set()
    atoms_to_flag = set()

    for issue_id, issue in QUALITY_ISSUES.items():
        try:
            result = conn.execute(
                text(f"""
                SELECT id, card_id, front, back
                FROM clean_atoms
                WHERE atom_type = 'flashcard'
                  AND {issue["sql_pattern"]}
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
                        (str(r.id), r.front[:50], r.back[:30] if r.back else "") for r in rows[:5]
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
    logger.info("FLASHCARD QUALITY AUDIT REPORT")
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
    logger.info(f"Total flashcards: {total}")
    logger.info(f"Critical issues (DELETE): {len(atoms_to_delete)}")
    logger.info(f"High/Medium issues (FLAG): {len(atoms_to_flag)}")
    logger.info(f"Clean flashcards: ~{total - len(atoms_to_delete) - len(atoms_to_flag)}")

    # Fix if requested
    if fix and atoms_to_delete:
        logger.info(f"\n[FIX MODE] Deleting {len(atoms_to_delete)} critical-issue atoms...")

        # Delete in batches
        delete_list = list(atoms_to_delete)
        for i in range(0, len(delete_list), 100):
            batch = delete_list[i : i + 100]
            placeholders = ",".join(f"'{aid}'::uuid" for aid in batch)
            conn.execute(text(f"DELETE FROM clean_atoms WHERE id IN ({placeholders})"))

        conn.commit()
        logger.info(f"Deleted {len(atoms_to_delete)} malformed flashcards")

        # Get new count
        result = conn.execute(
            text("SELECT COUNT(*) FROM clean_atoms WHERE atom_type = 'flashcard'")
        )
        new_total = result.scalar()
        logger.info(f"Remaining flashcards: {new_total}")

    if fix and atoms_to_flag:
        logger.info(f"\n[FIX MODE] Flagging {len(atoms_to_flag)} atoms for review...")

        # Update quality score to indicate issues
        flag_list = list(atoms_to_flag)
        for i in range(0, len(flag_list), 100):
            batch = flag_list[i : i + 100]
            placeholders = ",".join(f"'{aid}'::uuid" for aid in batch)
            conn.execute(
                text(f"""
                UPDATE clean_atoms
                SET quality_score = LEAST(quality_score, 50.0),
                    source = COALESCE(source, '') || '_flagged'
                WHERE id IN ({placeholders})
            """)
            )

        conn.commit()
        logger.info(f"Flagged {len(atoms_to_flag)} atoms with quality_score <= 50")

    return {
        "total": total,
        "issues": issues_found,
        "to_delete": len(atoms_to_delete),
        "to_flag": len(atoms_to_flag),
        "clean": total - len(atoms_to_delete) - len(atoms_to_flag),
    }


def show_samples(conn, limit: int = 20):
    """Show sample malformed flashcards."""
    logger.info("\n" + "=" * 70)
    logger.info("SAMPLE MALFORMED FLASHCARDS")
    logger.info("=" * 70)

    result = conn.execute(
        text("""
        SELECT id, card_id, front, back
        FROM clean_atoms
        WHERE atom_type = 'flashcard'
          AND (
            front LIKE '%What is This%'
            OR front ~ '^In .+, what (is|are|concept)'
            OR LENGTH(back) < 20
            OR back ~ '(,|, )$'
          )
        ORDER BY
            CASE
                WHEN front LIKE '%What is This%' THEN 1
                WHEN LENGTH(back) < 20 THEN 2
                ELSE 3
            END
        LIMIT :limit
    """),
        {"limit": limit},
    )

    for i, row in enumerate(result, 1):
        logger.info(f"\n[{i}] ID: {row.card_id}")
        logger.info(f"    Q: {row.front}")
        logger.info(f"    A: {row.back}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Audit flashcard quality")
    parser.add_argument("--fix", action="store_true", help="Delete/flag malformed atoms")
    parser.add_argument("--samples", type=int, default=0, help="Show N sample malformed cards")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.database_url)

    with engine.connect() as conn:
        if args.samples > 0:
            show_samples(conn, args.samples)
        else:
            audit_flashcards(conn, fix=args.fix)


if __name__ == "__main__":
    main()
