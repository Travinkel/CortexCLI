#!/usr/bin/env python3
"""
CCNA Reading Progress Tracker.

This script:
1. Tracks which chapters/modules have been read
2. Links reading progress to mastery scores
3. Recommends chapters to re-read based on low mastery

Usage:
    python scripts/reading_progress.py mark-read --chapters 1-17
    python scripts/reading_progress.py status
    python scripts/reading_progress.py recommend-reread [--learner LEARNER_ID]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from sqlalchemy import text

from config import get_settings
from src.db.database import session_scope

settings = get_settings()

# Re-read recommendation thresholds
REREAD_THRESHOLD_HIGH = 0.40    # Priority: high - mastery below 40%
REREAD_THRESHOLD_MEDIUM = 0.60  # Priority: medium - mastery 40-60%
REREAD_THRESHOLD_LOW = 0.75     # Priority: low - mastery 60-75%


def ensure_reading_progress_table(session):
    """Create reading_progress table if it doesn't exist."""
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS reading_progress (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            learner_id TEXT NOT NULL,
            module_id UUID NOT NULL REFERENCES clean_modules(id) ON DELETE CASCADE,
            chapter_number INT,
            is_read BOOLEAN DEFAULT FALSE,
            read_at TIMESTAMPTZ,
            comprehension_level TEXT DEFAULT 'not_started'
                CHECK (comprehension_level IN ('not_started', 'skimmed', 'read', 'studied', 'mastered')),
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(learner_id, module_id)
        )
    """))
    session.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_reading_progress_learner ON reading_progress(learner_id)
    """))
    session.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_reading_progress_module ON reading_progress(module_id)
    """))
    session.commit()


def get_modules(session, cluster_name: str = "CCNA") -> list[dict]:
    """Get all modules for a cluster."""
    result = session.execute(text("""
        SELECT
            cm.id,
            cm.name,
            CASE
                WHEN cm.name ~ '^Module \\d+' THEN
                    CAST(SUBSTRING(cm.name FROM 'Module (\\d+)') AS INTEGER)
                ELSE 999
            END as chapter_number,
            COUNT(ca.id) as atom_count
        FROM clean_modules cm
        LEFT JOIN clean_atoms ca ON ca.module_id = cm.id
        WHERE cm.name ILIKE :cluster_pattern OR cm.name ~ '^Module \\d+'
        GROUP BY cm.id, cm.name
        ORDER BY chapter_number
    """), {"cluster_pattern": f"%{cluster_name}%"})

    return [
        {
            "id": str(row.id),
            "name": row.name,
            "chapter_number": row.chapter_number,
            "atom_count": row.atom_count,
        }
        for row in result.fetchall()
    ]


def mark_chapters_read(
    session,
    learner_id: str,
    chapter_range: str,
    comprehension: str = "read",
):
    """Mark chapters as read for a learner."""
    # Parse chapter range (e.g., "1-17" or "1,3,5")
    chapters_to_mark = set()
    for part in chapter_range.split(","):
        if "-" in part:
            start, end = part.split("-")
            chapters_to_mark.update(range(int(start), int(end) + 1))
        else:
            chapters_to_mark.add(int(part))

    # Get modules matching chapters
    modules = get_modules(session)
    marked = 0

    for module in modules:
        if module["chapter_number"] in chapters_to_mark:
            # Upsert reading progress
            session.execute(text("""
                INSERT INTO reading_progress (
                    learner_id, module_id, chapter_number,
                    is_read, read_at, comprehension_level
                ) VALUES (
                    :learner_id, :module_id, :chapter_number,
                    TRUE, NOW(), :comprehension
                )
                ON CONFLICT (learner_id, module_id) DO UPDATE SET
                    is_read = TRUE,
                    read_at = COALESCE(reading_progress.read_at, NOW()),
                    comprehension_level = :comprehension,
                    updated_at = NOW()
            """), {
                "learner_id": learner_id,
                "module_id": module["id"],
                "chapter_number": module["chapter_number"],
                "comprehension": comprehension,
            })
            marked += 1
            logger.info(f"Marked as read: Chapter {module['chapter_number']} - {module['name']}")

    session.commit()
    return marked


def get_reading_status(session, learner_id: str) -> list[dict]:
    """Get reading status for all chapters."""
    result = session.execute(text("""
        SELECT
            cm.id,
            cm.name,
            CASE
                WHEN cm.name ~ '^Module \\d+' THEN
                    CAST(SUBSTRING(cm.name FROM 'Module (\\d+)') AS INTEGER)
                ELSE 999
            END as chapter_number,
            rp.is_read,
            rp.read_at,
            rp.comprehension_level,
            COUNT(ca.id) as atom_count
        FROM clean_modules cm
        LEFT JOIN reading_progress rp ON rp.module_id = cm.id AND rp.learner_id = :learner_id
        LEFT JOIN clean_atoms ca ON ca.module_id = cm.id
        WHERE cm.name ~ '^Module \\d+'
        GROUP BY cm.id, cm.name, rp.is_read, rp.read_at, rp.comprehension_level
        ORDER BY chapter_number
    """), {"learner_id": learner_id})

    return [
        {
            "id": str(row.id),
            "name": row.name,
            "chapter_number": row.chapter_number,
            "is_read": row.is_read or False,
            "read_at": row.read_at,
            "comprehension_level": row.comprehension_level or "not_started",
            "atom_count": row.atom_count,
        }
        for row in result.fetchall()
    ]


def get_reread_recommendations(session, learner_id: str) -> list[dict]:
    """
    Get chapters recommended for re-reading based on low mastery scores.

    Returns chapters where:
    - User has marked as read
    - But concept mastery is below threshold
    """
    result = session.execute(text("""
        WITH module_mastery AS (
            SELECT
                cm.id as module_id,
                cm.name as module_name,
                CASE
                    WHEN cm.name ~ '^Module \\d+' THEN
                        CAST(SUBSTRING(cm.name FROM 'Module (\\d+)') AS INTEGER)
                    ELSE 999
                END as chapter_number,
                AVG(COALESCE(lms.combined_mastery, 0)) as avg_mastery,
                COUNT(cc.id) as concept_count,
                COUNT(cc.id) FILTER (WHERE COALESCE(lms.combined_mastery, 0) < 0.65) as low_mastery_count,
                ARRAY_AGG(cc.name) FILTER (WHERE COALESCE(lms.combined_mastery, 0) < 0.40) as very_low_concepts
            FROM clean_modules cm
            LEFT JOIN clean_atoms ca ON ca.module_id = cm.id
            LEFT JOIN clean_concepts cc ON cc.id = ca.concept_id
            LEFT JOIN learner_mastery_state lms ON lms.concept_id = cc.id AND lms.learner_id = :learner_id
            WHERE cm.name ~ '^Module \\d+'
            GROUP BY cm.id, cm.name
        )
        SELECT
            mm.*,
            rp.is_read,
            rp.read_at,
            rp.comprehension_level
        FROM module_mastery mm
        LEFT JOIN reading_progress rp ON rp.module_id = mm.module_id AND rp.learner_id = :learner_id
        WHERE rp.is_read = TRUE
        AND mm.avg_mastery < :low_threshold
        ORDER BY mm.avg_mastery ASC
    """), {
        "learner_id": learner_id,
        "low_threshold": REREAD_THRESHOLD_LOW,
    })

    recommendations = []
    for row in result.fetchall():
        # Determine priority based on mastery level
        if row.avg_mastery < REREAD_THRESHOLD_HIGH:
            priority = "high"
            reason = f"Critical: Mastery at {row.avg_mastery*100:.0f}% (target: 65%+)"
        elif row.avg_mastery < REREAD_THRESHOLD_MEDIUM:
            priority = "medium"
            reason = f"Review needed: Mastery at {row.avg_mastery*100:.0f}%"
        else:
            priority = "low"
            reason = f"Refresh recommended: Mastery at {row.avg_mastery*100:.0f}%"

        recommendations.append({
            "module_id": str(row.module_id),
            "module_name": row.module_name,
            "chapter_number": row.chapter_number,
            "priority": priority,
            "reason": reason,
            "current_mastery": float(row.avg_mastery) if row.avg_mastery else 0.0,
            "target_mastery": 0.65,
            "low_mastery_concepts": row.low_mastery_count,
            "concepts_needing_review": row.very_low_concepts or [],
        })

    return recommendations


def print_status(status_list: list[dict]):
    """Print reading status in a nice format."""
    print("\n" + "=" * 70)
    print("CCNA READING PROGRESS")
    print("=" * 70)

    read_count = sum(1 for s in status_list if s["is_read"])
    total_count = len(status_list)
    print(f"\nProgress: {read_count}/{total_count} chapters read ({read_count/total_count*100:.0f}%)\n")

    for status in status_list:
        if status["chapter_number"] > 100:
            continue  # Skip non-numbered modules

        icon = "[X]" if status["is_read"] else "[ ]"
        level = status["comprehension_level"]
        level_str = f"({level})" if level != "not_started" else ""

        print(f"  {icon} Chapter {status['chapter_number']:2d}: {status['name'][:45]:<45} {level_str}")

    print()


def print_recommendations(recommendations: list[dict]):
    """Print re-read recommendations."""
    print("\n" + "=" * 70)
    print("RE-READ RECOMMENDATIONS")
    print("=" * 70)

    if not recommendations:
        print("\nNo re-read recommendations! All read chapters have good mastery.")
        return

    # Group by priority
    by_priority = {"high": [], "medium": [], "low": []}
    for rec in recommendations:
        by_priority[rec["priority"]].append(rec)

    for priority, label in [("high", "HIGH PRIORITY"), ("medium", "MEDIUM PRIORITY"), ("low", "LOW PRIORITY")]:
        if by_priority[priority]:
            print(f"\n{label}:")
            for rec in by_priority[priority]:
                print(f"  Chapter {rec['chapter_number']}: {rec['module_name'][:40]}")
                print(f"    - {rec['reason']}")
                if rec["concepts_needing_review"]:
                    concepts = rec["concepts_needing_review"][:3]  # Show max 3
                    print(f"    - Focus on: {', '.join(str(c) for c in concepts)}")

    print()


def main():
    parser = argparse.ArgumentParser(description="CCNA Reading Progress Tracker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # mark-read command
    read_parser = subparsers.add_parser("mark-read", help="Mark chapters as read")
    read_parser.add_argument("--chapters", required=True, help="Chapter range (e.g., 1-17 or 1,3,5)")
    read_parser.add_argument("--learner", default="default", help="Learner ID")
    read_parser.add_argument(
        "--level",
        choices=["skimmed", "read", "studied", "mastered"],
        default="read",
        help="Comprehension level",
    )

    # status command
    status_parser = subparsers.add_parser("status", help="Show reading progress")
    status_parser.add_argument("--learner", default="default", help="Learner ID")

    # recommend-reread command
    reread_parser = subparsers.add_parser("recommend-reread", help="Get re-read recommendations")
    reread_parser.add_argument("--learner", default="default", help="Learner ID")

    args = parser.parse_args()

    with session_scope() as session:
        # Ensure table exists
        ensure_reading_progress_table(session)

        if args.command == "mark-read":
            count = mark_chapters_read(
                session,
                args.learner,
                args.chapters,
                args.level,
            )
            print(f"\nMarked {count} chapters as '{args.level}' for learner '{args.learner}'")

            # Show updated status
            status = get_reading_status(session, args.learner)
            print_status(status)

        elif args.command == "status":
            status = get_reading_status(session, args.learner)
            print_status(status)

        elif args.command == "recommend-reread":
            recommendations = get_reread_recommendations(session, args.learner)
            print_recommendations(recommendations)

    return 0


if __name__ == "__main__":
    sys.exit(main())
