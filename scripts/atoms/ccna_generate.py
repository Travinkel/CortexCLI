#!/usr/bin/env python3
"""
CCNA Content Generation Script.

Executes the CCNA generation pipeline for specified modules.

Usage:
    python scripts/ccna_generate.py                     # Analyze modules only
    python scripts/ccna_generate.py --modules 7,9,10    # Generate specific modules
    python scripts/ccna_generate.py --priority          # Generate priority modules first
    python scripts/ccna_generate.py --dry-run           # Preview without generating
    python scripts/ccna_generate.py --create-hierarchy  # Create concept hierarchy first
    python scripts/ccna_generate.py --qa-report         # Run QA report on existing content
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from config import get_settings
from src.ccna.concept_generator import generate_ccna_hierarchy
from src.ccna.content_parser import CCNAContentParser
from src.ccna.curriculum_linker import setup_ccna_curriculum
from src.ccna.generation_pipeline import CCNAGenerationPipeline

# Priority modules (worst quality - need complete replacement)
PRIORITY_MODULES = [7, 9, 10, 15, 16]  # All Grade F
SEVERE_GAP_MODULES = [11]  # 9 cards vs ~360 needed


async def analyze_modules(parser: CCNAContentParser) -> dict:
    """Analyze all CCNA modules and return summary."""
    settings = get_settings()
    modules_path = Path(settings.ccna_modules_path)

    summary = {}
    total_lines = 0
    total_estimated = 0

    for i in range(1, 18):
        file_path = modules_path / f"CCNA Module {i}.txt"
        if file_path.exists():
            content = parser.parse_module(file_path)
            summary[i] = {
                "title": content.title,
                "lines": content.total_lines,
                "sections": len(content.sections),
                "estimated_atoms": content.estimated_atoms,
            }
            total_lines += content.total_lines
            total_estimated += content.estimated_atoms
            logger.info(
                f"Module {i}: {content.total_lines} lines, "
                f"{len(content.sections)} sections, "
                f"~{content.estimated_atoms} atoms estimated"
            )
        else:
            logger.warning(f"Module {i} not found at {file_path}")

    logger.info(f"\nTotal: {total_lines} lines, ~{total_estimated} atoms estimated")
    return summary


async def create_hierarchy() -> dict:
    """Create CCNA concept hierarchy using AI."""
    logger.info("=" * 60)
    logger.info("Creating CCNA Concept Hierarchy")
    logger.info("=" * 60)

    # Step 1: Setup curriculum structure (Program, Track, Modules)
    logger.info("\n[Step 1/2] Setting up curriculum structure...")
    try:
        curriculum_mapping = setup_ccna_curriculum()
        logger.info(f"  - Track ID: {curriculum_mapping.track_id}")
        logger.info(f"  - Modules linked: {len(curriculum_mapping.module_id_map)}")
    except Exception as e:
        logger.error(f"Failed to setup curriculum: {e}")
        return {"success": False, "error": str(e)}

    # Step 2: Generate concept hierarchy using AI
    logger.info("\n[Step 2/2] Generating concept hierarchy with AI...")
    try:
        result = await generate_ccna_hierarchy()
        logger.info("\nHierarchy generation complete:")
        logger.info(f"  - Concept Area ID: {result.get('concept_area_id')}")
        logger.info(f"  - Clusters created: {result.get('clusters_created', 0)}")
        logger.info(f"  - Concepts created: {result.get('concepts_created', 0)}")

        if result.get("errors"):
            logger.warning(f"  - Errors: {len(result['errors'])}")
            for err in result["errors"][:5]:
                logger.warning(f"    {err}")

        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Failed to generate hierarchy: {e}")
        return {"success": False, "error": str(e)}


async def run_qa_report() -> dict:
    """Run QA report on existing generated content."""
    logger.info("=" * 60)
    logger.info("Running QA Report on Generated Content")
    logger.info("=" * 60)

    from sqlalchemy import text

    from src.db.database import session_scope

    with session_scope() as session:
        # Get all generated atoms using raw SQL
        result = session.execute(
            text("""
            SELECT module_id, quality_grade, COUNT(*) as count
            FROM ccna_generated_atoms
            GROUP BY module_id, quality_grade
            ORDER BY module_id, quality_grade
        """)
        )
        rows = result.fetchall()

        if not rows:
            logger.warning("No generated atoms found in database")
            return {"success": False, "error": "No atoms found"}

        # Count by grade
        grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0, "ungraded": 0}
        module_counts = {}

        for row in rows:
            module_id = row[0] or "unknown"
            grade = row[1] or "ungraded"
            count = row[2]

            grade_counts[grade] = grade_counts.get(grade, 0) + count

            if module_id not in module_counts:
                module_counts[module_id] = {"total": 0, "grades": {}}
            module_counts[module_id]["total"] += count
            module_counts[module_id]["grades"][grade] = (
                module_counts[module_id]["grades"].get(grade, 0) + count
            )

        total = sum(grade_counts.values())
        ab_count = grade_counts["A"] + grade_counts["B"]
        ab_percentage = (ab_count / total * 100) if total > 0 else 0

        logger.info("\nOverall Results:")
        logger.info(f"  Total atoms: {total}")
        logger.info(f"  Grade A: {grade_counts['A']} ({grade_counts['A'] / total * 100:.1f}%)")
        logger.info(f"  Grade B: {grade_counts['B']} ({grade_counts['B'] / total * 100:.1f}%)")
        logger.info(f"  Grade C: {grade_counts['C']} ({grade_counts['C'] / total * 100:.1f}%)")
        logger.info(f"  Grade D: {grade_counts['D']} ({grade_counts['D'] / total * 100:.1f}%)")
        logger.info(f"  Grade F: {grade_counts['F']} ({grade_counts['F'] / total * 100:.1f}%)")
        logger.info(f"  Ungraded: {grade_counts['ungraded']}")
        logger.info(f"\n  A+B Percentage: {ab_percentage:.1f}% (target: >80%)")

        if ab_percentage >= 80:
            logger.info("  ✓ Quality target MET!")
        else:
            logger.warning(f"  ✗ Quality target not met (need {80 - ab_percentage:.1f}% more)")

        logger.info("\nPer-Module Breakdown:")
        for module_id in sorted(module_counts.keys()):
            data = module_counts[module_id]
            mod_ab = data["grades"].get("A", 0) + data["grades"].get("B", 0)
            mod_pct = (mod_ab / data["total"] * 100) if data["total"] > 0 else 0
            status = "✓" if mod_pct >= 80 else "✗"
            logger.info(f"  {module_id}: {data['total']} atoms, {mod_pct:.0f}% A/B {status}")

        return {
            "success": True,
            "total_atoms": total,
            "grade_counts": grade_counts,
            "ab_percentage": ab_percentage,
            "target_met": ab_percentage >= 80,
            "module_counts": module_counts,
        }


async def generate_modules(
    pipeline: CCNAGenerationPipeline,
    modules: list[int],
    dry_run: bool = False,
    with_concepts: bool = True,
) -> None:
    """Generate content for specified modules."""
    settings = get_settings()
    modules_path = Path(settings.ccna_modules_path)

    for module_num in modules:
        file_path = modules_path / f"CCNA Module {module_num}.txt"
        if not file_path.exists():
            logger.error(f"Module {module_num} not found at {file_path}")
            continue

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Processing Module {module_num}")
        logger.info(f"{'=' * 60}")

        if dry_run:
            logger.info("[DRY RUN] Would process module, skipping actual generation")
            continue

        try:
            # Use the enhanced method with concept linking
            if with_concepts:
                result = await pipeline.process_module_with_concept_linking(
                    module_path=file_path,
                    preserve_good_cards=True,
                    include_migration=True,
                    create_clean_atoms=True,
                )
            else:
                result = await pipeline.process_module(
                    module_path=file_path,
                    preserve_good_cards=True,
                )

            logger.info(f"Module {module_num} result:")
            logger.info(f"  - Generated: {result.atoms_generated}")
            logger.info(f"  - Passed QA: {result.atoms_passed_qa}")
            logger.info(f"  - Flagged: {result.atoms_flagged}")
            logger.info(f"  - Avg Quality Score: {result.avg_quality_score:.2f}")
            if result.grade_distribution:
                logger.info(f"  - Grades: {result.grade_distribution}")
            if result.errors:
                logger.warning(f"  - Errors: {len(result.errors)}")
                for err in result.errors[:5]:
                    logger.warning(f"    {err}")

        except Exception as e:
            logger.error(f"Failed to process module {module_num}: {e}")
            import traceback

            logger.debug(traceback.format_exc())
            continue


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="CCNA Content Generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze modules (default)
  python scripts/ccna_generate.py --analyze

  # Create concept hierarchy (run once before generating)
  python scripts/ccna_generate.py --create-hierarchy

  # Generate priority modules (worst quality)
  python scripts/ccna_generate.py --priority

  # Generate specific modules
  python scripts/ccna_generate.py --modules 7,9,10

  # Generate all modules
  python scripts/ccna_generate.py --all

  # Run QA report
  python scripts/ccna_generate.py --qa-report

  # Dry run (preview without generating)
  python scripts/ccna_generate.py --priority --dry-run
        """,
    )
    parser.add_argument(
        "--modules",
        type=str,
        help="Comma-separated list of module numbers (e.g., 7,9,10)",
    )
    parser.add_argument(
        "--priority",
        action="store_true",
        help="Process priority modules first (7, 9, 10, 15, 16, 11)",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Only analyze modules, don't generate",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without generating",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all 17 modules",
    )
    parser.add_argument(
        "--create-hierarchy",
        action="store_true",
        help="Create CCNA concept hierarchy (run once before generating)",
    )
    parser.add_argument(
        "--qa-report",
        action="store_true",
        help="Run QA report on existing generated content",
    )
    parser.add_argument(
        "--no-concepts",
        action="store_true",
        help="Skip concept linking (use basic generation)",
    )

    args = parser.parse_args()

    # Initialize services
    content_parser = CCNAContentParser()

    # QA report mode
    if args.qa_report:
        await run_qa_report()
        return

    # Create hierarchy mode
    if args.create_hierarchy:
        result = await create_hierarchy()
        if result.get("success"):
            logger.info("\nHierarchy created successfully!")
            logger.info("You can now run generation with: --priority or --all")
        else:
            logger.error(f"Failed: {result.get('error')}")
        return

    # Analyze-only mode
    if args.analyze:
        logger.info("Analyzing CCNA modules...")
        await analyze_modules(content_parser)
        return

    # Determine which modules to process
    if args.modules:
        modules = [int(m.strip()) for m in args.modules.split(",")]
    elif args.priority:
        modules = PRIORITY_MODULES + SEVERE_GAP_MODULES
        logger.info(f"Processing priority modules: {modules}")
    elif args.all:
        modules = list(range(1, 18))
    else:
        # Default: analyze only
        logger.info("No modules specified. Use --modules, --priority, or --all")
        logger.info("Running analysis...")
        await analyze_modules(content_parser)
        return

    # Initialize pipeline
    pipeline = CCNAGenerationPipeline()

    # Ensure curriculum is set up
    if not args.no_concepts:
        logger.info("Ensuring curriculum structure exists...")
        try:
            pipeline.ensure_curriculum_setup()
            logger.info("Curriculum structure ready.")
        except Exception as e:
            logger.warning(f"Could not setup curriculum: {e}")
            logger.info("Continuing without concept linking...")

    # Generate
    logger.info(f"Generating content for modules: {modules}")
    await generate_modules(
        pipeline,
        modules,
        dry_run=args.dry_run,
        with_concepts=not args.no_concepts,
    )

    logger.info("\nGeneration complete!")

    # Suggest QA report
    if not args.dry_run:
        logger.info("\nRun QA report with: python scripts/ccna_generate.py --qa-report")


if __name__ == "__main__":
    asyncio.run(main())
