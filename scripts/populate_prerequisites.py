#!/usr/bin/env python3
"""
Populate prerequisites for CCNA atoms.

This script:
1. Infers prerequisites from module order
2. Links concepts to their prerequisite concepts
3. Sets up soft/hard gating rules

Usage:
    python scripts/populate_prerequisites.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import UUID

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from sqlalchemy import text

from config import get_settings
from src.db.database import session_scope

settings = get_settings()


def get_itn_track_id(session) -> UUID:
    """Get the ITN/CCNA track ID."""
    result = session.execute(text("""
        SELECT id FROM clean_tracks WHERE name ILIKE '%itn%' OR name ILIKE '%ccna%' LIMIT 1
    """))
    row = result.fetchone()
    if row:
        return UUID(str(row.id))
    raise ValueError("CCNA/ITN track not found")


def get_concepts_with_atoms(session, track_id: UUID) -> list[dict]:
    """Get all concepts that have atoms, ordered by module."""
    result = session.execute(text("""
        SELECT
            cc.id,
            cc.name,
            ca.module_id,
            cm.name as module_name,
            COUNT(ca.id) as atom_count,
            CASE
                WHEN cm.name ~ '^Module \\d+' THEN
                    CAST(SUBSTRING(cm.name FROM 'Module (\\d+)') AS INTEGER)
                ELSE 999
            END as module_number
        FROM clean_concepts cc
        JOIN clean_atoms ca ON ca.concept_id = cc.id
        JOIN clean_modules cm ON ca.module_id = cm.id
        WHERE cm.track_id = :track_id
        GROUP BY cc.id, cc.name, ca.module_id, cm.name
        HAVING COUNT(ca.id) > 0
        ORDER BY module_number, cc.name
    """), {"track_id": str(track_id)})

    return [
        {
            "id": UUID(str(row.id)),
            "name": row.name,
            "module_id": UUID(str(row.module_id)),
            "module_name": row.module_name,
            "atom_count": row.atom_count,
            "module_number": row.module_number,
        }
        for row in result.fetchall()
    ]


def infer_prerequisites_from_modules(session, track_id: UUID) -> list[dict]:
    """
    Infer prerequisites based on module order.

    Concepts in later modules depend on concepts in earlier modules.
    """
    result = session.execute(text("""
        WITH concept_modules AS (
            SELECT DISTINCT
                cc.id as concept_id,
                cc.name as concept_name,
                ca.module_id,
                cm.name as module_name,
                CASE
                    WHEN cm.name ~ '^Module \\d+' THEN
                        CAST(SUBSTRING(cm.name FROM 'Module (\\d+)') AS INTEGER)
                    ELSE 999
                END as module_number
            FROM clean_concepts cc
            JOIN clean_atoms ca ON ca.concept_id = cc.id
            JOIN clean_modules cm ON ca.module_id = cm.id
            WHERE cm.track_id = :track_id
        )
        SELECT
            later.concept_id as source_concept_id,
            later.concept_name as source_name,
            earlier.concept_id as target_concept_id,
            earlier.concept_name as target_name,
            later.module_number as source_module_number,
            earlier.module_number as target_module_number
        FROM concept_modules later
        JOIN concept_modules earlier ON
            later.module_number > earlier.module_number
            AND later.module_number <= earlier.module_number + 2  -- Only 1-2 modules back
            AND later.concept_id != earlier.concept_id
        ORDER BY later.module_number, earlier.module_number
    """), {"track_id": str(track_id)})

    return [
        {
            "source_concept_id": UUID(str(row.source_concept_id)),
            "source_name": row.source_name,
            "target_concept_id": UUID(str(row.target_concept_id)),
            "target_name": row.target_name,
            "source_module_number": row.source_module_number,
            "target_module_number": row.target_module_number,
        }
        for row in result.fetchall()
    ]


def create_prerequisites(
    session,
    prerequisites: list[dict],
    gating_type: str = "soft",
    mastery_threshold: float = 0.65,
    dry_run: bool = False,
) -> int:
    """Create prerequisite records."""
    created = 0

    for prereq in prerequisites:
        # Check if already exists
        result = session.execute(text("""
            SELECT id FROM explicit_prerequisites
            WHERE source_concept_id = :source
            AND target_concept_id = :target
        """), {
            "source": str(prereq["source_concept_id"]),
            "target": str(prereq["target_concept_id"]),
        })

        if result.fetchone():
            continue  # Already exists

        if dry_run:
            logger.debug(
                f"[DRY RUN] Would create: {prereq['source_name'][:30]} -> {prereq['target_name'][:30]}"
            )
            created += 1
            continue

        # Create prerequisite
        session.execute(text("""
            INSERT INTO explicit_prerequisites (
                source_concept_id, target_concept_id,
                gating_type, mastery_threshold, status,
                origin, created_at
            ) VALUES (
                :source, :target,
                :gating_type, :threshold, 'active',
                :origin, NOW()
            )
        """), {
            "source": str(prereq["source_concept_id"]),
            "target": str(prereq["target_concept_id"]),
            "gating_type": gating_type,
            "threshold": mastery_threshold,
            "origin": "inferred",  # module_order is inferred
        })
        created += 1

    return created


def update_atom_prerequisite_counts(session, track_id: UUID, dry_run: bool = False):
    """Update atom prerequisite counts (skipped - column doesn't exist)."""
    # NOTE: clean_atoms doesn't have has_prerequisites/prerequisite_count columns
    # Prerequisites are tracked in explicit_prerequisites table and joined at query time
    logger.info("Skipping atom prerequisite counts (joined from explicit_prerequisites table)")


def main():
    parser = argparse.ArgumentParser(
        description="Populate prerequisites for CCNA atoms"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    logger.info("Populating prerequisites for CCNA/ITN track")
    if args.dry_run:
        logger.info("DRY RUN mode - no changes will be made")

    with session_scope() as session:
        # Get track ID
        try:
            track_id = get_itn_track_id(session)
            logger.info(f"Found track ID: {track_id}")
        except ValueError as e:
            logger.error(str(e))
            return 1

        # Get concepts with atoms
        concepts = get_concepts_with_atoms(session, track_id)
        logger.info(f"Found {len(concepts)} concepts with atoms")

        # Infer prerequisites from module order
        logger.info("Inferring prerequisites from module order...")
        module_prereqs = infer_prerequisites_from_modules(session, track_id)
        logger.info(f"Found {len(module_prereqs)} potential module-based prerequisites")

        # Add source type
        for prereq in module_prereqs:
            prereq["source_type"] = "module_order"

        # Create prerequisites (soft gating for module-based)
        created_module = create_prerequisites(
            session,
            module_prereqs,
            gating_type="soft",
            mastery_threshold=0.65,
            dry_run=args.dry_run,
        )
        logger.info(f"Created {created_module} module-based prerequisites")

        # Update atom prerequisite counts
        logger.info("Updating atom prerequisite counts...")
        update_atom_prerequisite_counts(session, track_id, args.dry_run)

        if not args.dry_run:
            session.commit()

        # Summary
        result = session.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN gating_type = 'soft' THEN 1 END) as soft,
                COUNT(CASE WHEN gating_type = 'hard' THEN 1 END) as hard
            FROM explicit_prerequisites
            WHERE status = 'active'
        """))

        summary = result.fetchone()
        logger.info(f"\nPrerequisite Summary:")
        logger.info(f"  Total: {summary.total}")
        logger.info(f"  Soft gating: {summary.soft}")
        logger.info(f"  Hard gating: {summary.hard}")

        # Atom summary - count atoms with concepts that have prerequisites
        result = session.execute(text("""
            SELECT
                COUNT(DISTINCT ca.id) as total,
                COUNT(DISTINCT CASE
                    WHEN EXISTS (
                        SELECT 1 FROM explicit_prerequisites ep
                        WHERE ep.source_concept_id = ca.concept_id
                        AND ep.status = 'active'
                    ) THEN ca.id
                END) as with_prereqs
            FROM clean_atoms ca
            JOIN clean_modules cm ON ca.module_id = cm.id
            WHERE cm.track_id = :track_id
        """), {"track_id": str(track_id)})

        atom_summary = result.fetchone()
        logger.info(f"\nAtom Summary:")
        logger.info(f"  Total atoms: {atom_summary.total}")
        logger.info(f"  With prerequisites: {atom_summary.with_prereqs}")

    logger.info("Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
