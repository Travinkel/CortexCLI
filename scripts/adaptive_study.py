#!/usr/bin/env python3
"""
Adaptive Study CLI.

Full-loop adaptive learning with:
- Mastery tracking
- Just-in-time remediation
- Anki sync integration
- Session management

Usage:
    python scripts/adaptive_study.py study [--module MODULE]
    python scripts/adaptive_study.py status [--learner LEARNER_ID]
    python scripts/adaptive_study.py sync-mastery [--learner LEARNER_ID]
    python scripts/adaptive_study.py gaps [--learner LEARNER_ID]
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

# Fix Windows encoding issues
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from sqlalchemy import text

from config import get_settings
from src.db.database import session_scope
from src.adaptive import (
    LearningEngine,
    MasteryCalculator,
    SessionMode,
    SessionStatus,
    MasteryLevel,
)

settings = get_settings()

# ANSI colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def get_track_id(session) -> Optional[UUID]:
    """Get the ITN/CCNA track ID."""
    result = session.execute(text("""
        SELECT id FROM clean_tracks WHERE name ILIKE '%itn%' OR name ILIKE '%ccna%' LIMIT 1
    """))
    row = result.fetchone()
    if row:
        return UUID(str(row.id))
    return None


def print_mastery_bar(mastery: float, width: int = 30) -> str:
    """Create a visual mastery bar."""
    filled = int(mastery * width)
    empty = width - filled

    if mastery >= 0.85:
        color = Colors.GREEN
    elif mastery >= 0.65:
        color = Colors.CYAN
    elif mastery >= 0.40:
        color = Colors.YELLOW
    else:
        color = Colors.RED

    bar = f"{color}{'█' * filled}{'░' * empty}{Colors.ENDC}"
    return f"[{bar}] {mastery*100:.1f}%"


def cmd_status(args):
    """Show mastery status for a learner."""
    learner_id = args.learner

    print(f"\n{Colors.BOLD}═══════════════════════════════════════════════════════════════{Colors.ENDC}")
    print(f"{Colors.HEADER}MASTERY STATUS - Learner: {learner_id}{Colors.ENDC}")
    print(f"{Colors.BOLD}═══════════════════════════════════════════════════════════════{Colors.ENDC}\n")

    calc = MasteryCalculator()

    # Get summary
    summary = calc.get_mastery_summary(learner_id)

    print(f"Total concepts: {summary['total_concepts']}")
    print(f"Average mastery: {print_mastery_bar(summary['average_mastery'])}")
    print(f"Unlocked: {summary['unlocked']} | Locked: {summary['locked']}")

    print(f"\n{Colors.BOLD}By Level:{Colors.ENDC}")
    for level, count in summary['by_level'].items():
        color = {
            'mastery': Colors.GREEN,
            'proficient': Colors.CYAN,
            'developing': Colors.YELLOW,
            'novice': Colors.RED,
        }.get(level, Colors.ENDC)
        print(f"  {color}{level.capitalize():12}{Colors.ENDC}: {count}")

    # Get per-concept breakdown
    with session_scope() as session:
        track_id = get_track_id(session)
        if track_id:
            result = session.execute(text("""
                SELECT
                    cc.name,
                    lms.combined_mastery,
                    lms.review_mastery,
                    lms.review_count,
                    lms.is_unlocked
                FROM learner_mastery_state lms
                JOIN clean_concepts cc ON lms.concept_id = cc.id
                WHERE lms.learner_id = :learner_id
                ORDER BY lms.combined_mastery DESC
                LIMIT 20
            """), {"learner_id": learner_id})

            concepts = result.fetchall()
            if concepts:
                print(f"\n{Colors.BOLD}Top 20 Concepts:{Colors.ENDC}")
                print(f"{'Concept':<50} | {'Mastery':>12} | {'Reviews':>8}")
                print("-" * 75)
                for c in concepts:
                    status = Colors.GREEN + "✓" + Colors.ENDC if c.is_unlocked else Colors.RED + "✗" + Colors.ENDC
                    mastery = float(c.combined_mastery or 0)
                    print(f"{c.name[:48]:<50} | {print_mastery_bar(mastery, 10):>12} | {c.review_count or 0:>8} {status}")

    print()


def cmd_sync_mastery(args):
    """Sync mastery from Anki FSRS data."""
    learner_id = args.learner

    print(f"\n{Colors.BOLD}Syncing mastery from Anki for learner: {learner_id}{Colors.ENDC}\n")

    calc = MasteryCalculator()

    with session_scope() as session:
        track_id = get_track_id(session)

    count = calc.initialize_mastery_from_anki(learner_id, track_id)

    print(f"{Colors.GREEN}Initialized mastery for {count} concepts{Colors.ENDC}")

    # Show summary
    summary = calc.get_mastery_summary(learner_id)
    print(f"\nAverage mastery: {print_mastery_bar(summary['average_mastery'])}")
    print(f"Concepts at mastery level: {summary['by_level'].get('mastery', 0)}")
    print(f"Concepts developing: {summary['by_level'].get('developing', 0)}")
    print(f"Concepts novice: {summary['by_level'].get('novice', 0)}")
    print()


def cmd_gaps(args):
    """Show knowledge gaps for a learner."""
    learner_id = args.learner

    print(f"\n{Colors.BOLD}═══════════════════════════════════════════════════════════════{Colors.ENDC}")
    print(f"{Colors.HEADER}KNOWLEDGE GAPS - Learner: {learner_id}{Colors.ENDC}")
    print(f"{Colors.BOLD}═══════════════════════════════════════════════════════════════{Colors.ENDC}\n")

    engine = LearningEngine()
    gaps = engine.get_knowledge_gaps(learner_id)

    if not gaps:
        print(f"{Colors.GREEN}No significant knowledge gaps detected!{Colors.ENDC}\n")
        return

    print(f"Found {len(gaps)} knowledge gaps:\n")

    for i, gap in enumerate(gaps[:10], 1):
        priority_color = {
            'high': Colors.RED,
            'medium': Colors.YELLOW,
            'low': Colors.CYAN,
        }.get(gap.priority, Colors.ENDC)

        print(f"{i}. {Colors.BOLD}{gap.concept_name}{Colors.ENDC}")
        print(f"   Priority: {priority_color}{gap.priority.upper()}{Colors.ENDC}")
        print(f"   Current: {gap.current_mastery*100:.1f}% → Target: {gap.required_mastery*100:.1f}%")
        print(f"   Gap: {gap.mastery_gap*100:.1f}%")
        if gap.blocking_count > 0:
            print(f"   {Colors.RED}Blocking {gap.blocking_count} concepts{Colors.ENDC}")
        print()


def cmd_study(args):
    """Start an adaptive study session."""
    learner_id = args.learner
    module_num = args.module
    card_count = args.count

    print(f"\n{Colors.BOLD}═══════════════════════════════════════════════════════════════{Colors.ENDC}")
    print(f"{Colors.HEADER}ADAPTIVE STUDY SESSION{Colors.ENDC}")
    print(f"{Colors.BOLD}═══════════════════════════════════════════════════════════════{Colors.ENDC}")
    print(f"Learner: {learner_id}")
    print(f"Target cards: {card_count}")
    if module_num:
        print(f"Module: {module_num}")
    print()

    engine = LearningEngine()

    # Get module concept if specified
    target_concept_id = None
    target_cluster_id = None

    if module_num:
        with session_scope() as session:
            result = session.execute(text("""
                SELECT DISTINCT cc.id, cc.name
                FROM clean_concepts cc
                JOIN learning_atoms ca ON ca.concept_id = cc.id
                JOIN clean_modules cm ON ca.module_id = cm.id
                WHERE cm.name ILIKE :pattern
                LIMIT 1
            """), {"pattern": f"%Module {module_num}%"})
            row = result.fetchone()
            if row:
                target_concept_id = UUID(str(row.id))
                print(f"Target concept: {row.name}\n")

    # Create session
    session_state = engine.create_session(
        learner_id=learner_id,
        mode=SessionMode.ADAPTIVE,
        target_concept_id=target_concept_id,
        target_cluster_id=target_cluster_id,
        atom_count=card_count,
    )

    if not session_state.current_atom:
        print(f"{Colors.YELLOW}No atoms available for study. Generate content first.{Colors.ENDC}\n")
        return

    print(f"Session started: {session_state.session_id}")
    print(f"Atoms to review: {session_state.progress.atoms_remaining}")
    print()

    # Study loop
    correct = 0
    total = 0

    while session_state.current_atom:
        atom = session_state.current_atom
        total += 1

        print(f"\n{Colors.BOLD}─── Card {total} ───{Colors.ENDC}")
        print(f"Concept: {atom.concept_name or 'Unknown'}")
        print(f"Type: {atom.atom_type}")
        print()
        print(f"{Colors.CYAN}Q: {atom.front}{Colors.ENDC}")
        print()

        # Wait for user input
        input(f"Press Enter to reveal answer...")
        print()
        print(f"{Colors.GREEN}A: {atom.back}{Colors.ENDC}")
        print()

        # Self-assessment
        while True:
            response = input("Did you know it? (y/n/s=skip/q=quit): ").strip().lower()
            if response in ['y', 'yes', '1', 'correct']:
                is_correct = True
                break
            elif response in ['n', 'no', '0', 'incorrect']:
                is_correct = False
                break
            elif response in ['s', 'skip']:
                is_correct = None
                break
            elif response in ['q', 'quit']:
                # End session
                engine.end_session(session_state.session_id, SessionStatus.ABANDONED)
                print(f"\n{Colors.YELLOW}Session abandoned.{Colors.ENDC}")
                print(f"Reviewed: {total-1} cards")
                print(f"Correct: {correct}")
                return

        if is_correct is not None:
            # Submit answer
            result = engine.submit_answer(
                session_id=session_state.session_id,
                atom_id=atom.atom_id,
                answer="correct" if is_correct else "incorrect",
            )

            if is_correct:
                correct += 1
                print(f"{Colors.GREEN}✓ Correct!{Colors.ENDC}")
            else:
                print(f"{Colors.RED}✗ Incorrect{Colors.ENDC}")

                # Check for remediation
                if result.remediation_triggered:
                    print(f"\n{Colors.YELLOW}⚠ Knowledge gap detected!{Colors.ENDC}")
                    if result.remediation_plan:
                        print(f"Concept: {result.remediation_plan.gap_concept_name}")
                        print(f"Recommended: Review {len(result.remediation_plan.atoms)} related cards")

                        inject = input("Would you like to review prerequisite content? (y/n): ").strip().lower()
                        if inject in ['y', 'yes']:
                            engine.inject_remediation(
                                session_state.session_id,
                                result.remediation_plan,
                            )
                            print(f"{Colors.CYAN}Remediation cards added to session{Colors.ENDC}")

        # Get next atom
        next_atom = engine.get_next_atom(session_state.session_id)
        if next_atom:
            session_state.current_atom = next_atom
        else:
            break

    # Session complete
    engine.end_session(session_state.session_id, SessionStatus.COMPLETED)

    accuracy = (correct / total * 100) if total > 0 else 0

    print(f"\n{Colors.BOLD}═══════════════════════════════════════════════════════════════{Colors.ENDC}")
    print(f"{Colors.GREEN}SESSION COMPLETE{Colors.ENDC}")
    print(f"{Colors.BOLD}═══════════════════════════════════════════════════════════════{Colors.ENDC}")
    print(f"Cards reviewed: {total}")
    print(f"Correct: {correct}")
    print(f"Accuracy: {accuracy:.1f}%")
    print()


def cmd_next_atom(args):
    """Get the next optimal atom for a learner."""
    learner_id = args.learner

    engine = LearningEngine()

    with session_scope() as session:
        track_id = get_track_id(session)

    # Get sequence of next atoms
    from src.adaptive.path_sequencer import PathSequencer
    sequencer = PathSequencer()

    atoms = sequencer.get_next_atoms(learner_id, count=args.count)

    print(f"\n{Colors.BOLD}Next {len(atoms)} atoms for {learner_id}:{Colors.ENDC}\n")

    with session_scope() as session:
        for i, atom_id in enumerate(atoms[:10], 1):
            result = session.execute(text("""
                SELECT ca.front, ca.atom_type, cc.name as concept_name
                FROM learning_atoms ca
                LEFT JOIN clean_concepts cc ON ca.concept_id = cc.id
                WHERE ca.id = :atom_id
            """), {"atom_id": str(atom_id)})
            row = result.fetchone()
            if row:
                print(f"{i}. [{row.atom_type}] {row.concept_name or 'Unknown'}")
                print(f"   {row.front[:80]}...")
                print()


def main():
    parser = argparse.ArgumentParser(
        description="Adaptive Study CLI - Full-loop adaptive learning"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # study command
    study_parser = subparsers.add_parser("study", help="Start an adaptive study session")
    study_parser.add_argument("--learner", default="default", help="Learner ID")
    study_parser.add_argument("--module", type=int, help="Target module number")
    study_parser.add_argument("--count", type=int, default=20, help="Number of cards")

    # status command
    status_parser = subparsers.add_parser("status", help="Show mastery status")
    status_parser.add_argument("--learner", default="default", help="Learner ID")

    # sync-mastery command
    sync_parser = subparsers.add_parser("sync-mastery", help="Sync mastery from Anki")
    sync_parser.add_argument("--learner", default="default", help="Learner ID")

    # gaps command
    gaps_parser = subparsers.add_parser("gaps", help="Show knowledge gaps")
    gaps_parser.add_argument("--learner", default="default", help="Learner ID")

    # next-atom command
    next_parser = subparsers.add_parser("next-atom", help="Get next optimal atoms")
    next_parser.add_argument("--learner", default="default", help="Learner ID")
    next_parser.add_argument("--count", type=int, default=10, help="Number of atoms")

    args = parser.parse_args()

    if args.command == "study":
        cmd_study(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "sync-mastery":
        cmd_sync_mastery(args)
    elif args.command == "gaps":
        cmd_gaps(args)
    elif args.command == "next-atom":
        cmd_next_atom(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
