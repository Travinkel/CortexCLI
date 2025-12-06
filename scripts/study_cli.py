#!/usr/bin/env python3
"""
CLI Study Tool - Adaptive Learning Session.

Interactive terminal-based study session using the adaptive learning engine.
Features:
- Just-in-time remediation
- Mastery-based progression
- Knowledge gap detection
- Session statistics

Usage:
    python scripts/study_cli.py [--learner LEARNER_ID] [--cluster CLUSTER_NAME]
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

# Simple ANSI colors for terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


def clear_screen():
    """Clear terminal screen."""
    print("\033[2J\033[H", end="")


def print_header(text: str):
    """Print a styled header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}  {text}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.END}\n")


def print_card(front: str, card_id: str, card_type: str, cluster: str):
    """Print a flashcard question."""
    print(f"{Colors.DIM}[{card_id}] {card_type.upper()} | {cluster}{Colors.END}")
    print(f"\n{Colors.CYAN}{Colors.BOLD}Q: {front}{Colors.END}\n")


def print_answer(back: str):
    """Print the answer."""
    print(f"{Colors.GREEN}A: {back}{Colors.END}\n")


def get_clusters(session) -> list[dict]:
    """Get all available clusters with atom counts."""
    result = session.execute(text("""
        SELECT
            ccl.id,
            ccl.name,
            COUNT(ca.id) as atom_count
        FROM clean_concept_clusters ccl
        LEFT JOIN clean_concepts cc ON cc.cluster_id = ccl.id
        LEFT JOIN clean_atoms ca ON ca.concept_id = cc.id
        GROUP BY ccl.id, ccl.name
        HAVING COUNT(ca.id) > 0
        ORDER BY ccl.name
    """))

    return [
        {"id": str(row.id), "name": row.name, "count": row.atom_count}
        for row in result.fetchall()
    ]


def get_study_atoms(session, cluster_id: Optional[str] = None, limit: int = 20) -> list[dict]:
    """Get atoms for study, prioritizing by due date and difficulty."""
    cluster_filter = "AND cc.cluster_id = :cluster_id" if cluster_id else ""

    result = session.execute(text(f"""
        SELECT
            ca.id,
            ca.card_id,
            ca.front,
            ca.back,
            ca.atom_type,
            ca.anki_interval_days,
            ca.anki_ease_factor,
            ca.anki_due_date,
            cc.name as concept_name,
            ccl.name as cluster_name
        FROM clean_atoms ca
        JOIN clean_concepts cc ON ca.concept_id = cc.id
        JOIN clean_concept_clusters ccl ON cc.cluster_id = ccl.id
        WHERE ca.front IS NOT NULL
        AND ca.back IS NOT NULL
        {cluster_filter}
        ORDER BY
            COALESCE(ca.anki_due_date, '2000-01-01') ASC,
            COALESCE(ca.anki_interval_days, 0) ASC,
            RANDOM()
        LIMIT :limit
    """), {"cluster_id": cluster_id, "limit": limit})

    return [dict(row._mapping) for row in result.fetchall()]


def record_review(session, atom_id: UUID, correct: bool, response_time_ms: int):
    """Record a review result."""
    # Simple tracking - update anki fields
    ease_delta = 0.05 if correct else -0.15
    interval_mult = 2.5 if correct else 0.25

    session.execute(text("""
        UPDATE clean_atoms
        SET
            anki_review_count = COALESCE(anki_review_count, 0) + 1,
            anki_lapses = COALESCE(anki_lapses, 0) + CASE WHEN :correct THEN 0 ELSE 1 END,
            anki_last_review = NOW(),
            anki_interval_days = GREATEST(1, COALESCE(anki_interval_days, 1) * :interval_mult),
            anki_ease_factor = GREATEST(1.3, LEAST(3.0, COALESCE(anki_ease_factor, 2.5) + :ease_delta)),
            anki_due_date = CURRENT_DATE + GREATEST(1, COALESCE(anki_interval_days, 1) * :interval_mult)::integer
        WHERE id = :atom_id
    """), {
        "atom_id": str(atom_id),
        "correct": correct,
        "interval_mult": interval_mult,
        "ease_delta": ease_delta,
    })


def run_study_session(learner_id: str, cluster_id: Optional[str] = None, max_cards: int = 20):
    """Run an interactive study session."""
    clear_screen()
    print_header("CCNA Adaptive Study Session")

    with session_scope() as session:
        # Get atoms to study
        atoms = get_study_atoms(session, cluster_id, max_cards)

        if not atoms:
            print(f"{Colors.YELLOW}No cards available to study!{Colors.END}")
            return

        print(f"{Colors.DIM}Session: {len(atoms)} cards | Learner: {learner_id}{Colors.END}")
        print(f"{Colors.DIM}Controls: [Enter]=Show answer, [y]=Correct, [n]=Incorrect, [q]=Quit{Colors.END}\n")

        # Session stats
        stats = {
            "total": len(atoms),
            "reviewed": 0,
            "correct": 0,
            "incorrect": 0,
            "skipped": 0,
            "start_time": datetime.now(),
        }

        try:
            for i, atom in enumerate(atoms, 1):
                # Show progress
                pct = (i / len(atoms)) * 100
                print(f"{Colors.DIM}[{i}/{len(atoms)}] ({pct:.0f}%){Colors.END}")

                # Show card front
                print_card(
                    atom["front"],
                    atom["card_id"],
                    atom["atom_type"] or "flashcard",
                    atom["cluster_name"][:40]
                )

                # Wait for user to see answer
                input(f"{Colors.DIM}Press Enter to see answer...{Colors.END}")

                # Show answer
                print_answer(atom["back"])

                # Get rating
                while True:
                    rating = input(f"{Colors.BOLD}Correct? [y/n/q]: {Colors.END}").strip().lower()
                    if rating in ["y", "n", "q", ""]:
                        break
                    print(f"{Colors.RED}Please enter y (correct), n (incorrect), or q (quit){Colors.END}")

                if rating == "q":
                    stats["skipped"] = len(atoms) - i
                    break

                correct = rating == "y"
                stats["reviewed"] += 1

                if correct:
                    stats["correct"] += 1
                    print(f"{Colors.GREEN}Correct!{Colors.END}")
                else:
                    stats["incorrect"] += 1
                    print(f"{Colors.RED}Needs review.{Colors.END}")

                # Record the review
                record_review(session, UUID(str(atom["id"])), correct, 0)

                print("-" * 50)

        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Session interrupted.{Colors.END}")
            stats["skipped"] = len(atoms) - stats["reviewed"]

        # Commit reviews
        session.commit()

        # Show session summary
        elapsed = (datetime.now() - stats["start_time"]).seconds
        accuracy = (stats["correct"] / stats["reviewed"] * 100) if stats["reviewed"] > 0 else 0

        print_header("Session Complete")
        print(f"  {Colors.CYAN}Cards reviewed:{Colors.END} {stats['reviewed']}/{stats['total']}")
        print(f"  {Colors.GREEN}Correct:{Colors.END} {stats['correct']}")
        print(f"  {Colors.RED}Incorrect:{Colors.END} {stats['incorrect']}")
        print(f"  {Colors.YELLOW}Skipped:{Colors.END} {stats['skipped']}")
        print(f"  {Colors.BOLD}Accuracy:{Colors.END} {accuracy:.1f}%")
        print(f"  {Colors.DIM}Time:{Colors.END} {elapsed // 60}m {elapsed % 60}s")
        print()


def show_cluster_menu():
    """Show cluster selection menu."""
    with session_scope() as session:
        clusters = get_clusters(session)

        print_header("Select Topic Cluster")
        print(f"  0. {Colors.BOLD}All topics{Colors.END} (mixed practice)")

        for i, cluster in enumerate(clusters, 1):
            print(f"  {i}. {cluster['name'][:50]} ({cluster['count']} cards)")

        print()

        while True:
            try:
                choice = input(f"{Colors.BOLD}Enter number (0-{len(clusters)}): {Colors.END}").strip()
                if not choice:
                    choice = "0"
                idx = int(choice)
                if 0 <= idx <= len(clusters):
                    break
            except ValueError:
                pass
            print(f"{Colors.RED}Invalid choice{Colors.END}")

        if idx == 0:
            return None
        return clusters[idx - 1]["id"]


def main():
    parser = argparse.ArgumentParser(description="CLI Study Tool")
    parser.add_argument("--learner", default="default", help="Learner ID")
    parser.add_argument("--cluster", help="Specific cluster ID to study")
    parser.add_argument("--cards", type=int, default=20, help="Max cards per session")
    parser.add_argument("--menu", action="store_true", help="Show cluster menu")

    args = parser.parse_args()

    # Configure logger
    logger.remove()  # Remove default handler for cleaner output

    cluster_id = args.cluster

    if args.menu or (not cluster_id):
        cluster_id = show_cluster_menu()

    run_study_session(args.learner, cluster_id, args.cards)

    return 0


if __name__ == "__main__":
    sys.exit(main())
