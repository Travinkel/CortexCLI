#!/usr/bin/env python3
"""
Compute Optimal Flashcard Count per Concept/Module.

Based on learning science research:
- Cognitive Load Theory (Sweller, 1988): Working memory ~4 chunks
- Miller's Law: 7±2 items in short-term memory
- SuperMemo 20 Rules (Wozniak, 1999): Minimum information principle
- FSRS Research: Optimal retention at 20-30 new cards/day
- Interleaving (Bjork): Mix topics for better retention

Usage:
    python scripts/compute_optimal_atoms.py [--analyze] [--recommend]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text

from config import get_settings
from src.db.database import session_scope

settings = get_settings()

# Learning science constants
WORKING_MEMORY_CHUNKS = 4  # Cowan (2001)
NEW_CARDS_PER_DAY_OPTIMAL = 25  # Sustainable daily rate
SECONDS_PER_CARD_REVIEW = 8  # Average review time
MINUTES_PER_DAY_TARGET = 30  # Target study time

# Optimal atoms per complexity level
OPTIMAL_RANGES = {
    "simple": (20, 40),  # Simple factual concepts
    "moderate": (40, 80),  # Moderate conceptual complexity
    "complex": (80, 150),  # Complex topics with sub-concepts
    "comprehensive": (150, 250),  # Major topic areas
}

# Complexity classification by topic keywords
COMPLEXITY_KEYWORDS = {
    "simple": ["introduction", "overview", "basic", "fundamentals"],
    "moderate": ["configuration", "addressing", "layer", "protocol"],
    "complex": ["security", "routing", "transport", "network layer"],
    "comprehensive": ["model", "architecture", "system"],
}


def classify_complexity(topic_name: str) -> str:
    """Classify topic complexity based on name keywords."""
    name_lower = topic_name.lower()

    for complexity, keywords in COMPLEXITY_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return complexity

    return "moderate"  # Default


def compute_optimal_count(
    current_count: int,
    complexity: str,
    sub_topic_count: int = 1,
) -> tuple[int, int, str]:
    """
    Compute optimal atom count for a concept.

    Returns: (min_optimal, max_optimal, recommendation)
    """
    base_min, base_max = OPTIMAL_RANGES.get(complexity, (40, 80))

    # Adjust for sub-topics (each sub-topic adds ~20-40 atoms)
    adjusted_min = base_min + (sub_topic_count - 1) * 20
    adjusted_max = base_max + (sub_topic_count - 1) * 40

    if current_count < adjusted_min:
        recommendation = f"ADD ~{adjusted_min - current_count} atoms"
    elif current_count > adjusted_max:
        current_count - adjusted_max
        sub_concepts_needed = (current_count // 80) + 1
        recommendation = f"SPLIT into {sub_concepts_needed} sub-concepts (~80 each)"
    else:
        recommendation = "OK"

    return adjusted_min, adjusted_max, recommendation


def analyze_atoms(session) -> dict:
    """Analyze current atom distribution."""
    result = session.execute(
        text("""
        SELECT
            cm.name as module_name,
            ccl.name as cluster_name,
            COUNT(ca.id) as atom_count,
            COUNT(DISTINCT ca.concept_id) as concept_count,
            COUNT(CASE WHEN ca.atom_type = 'flashcard' THEN 1 END) as flashcard_count,
            COUNT(CASE WHEN ca.atom_type = 'cloze' THEN 1 END) as cloze_count,
            COUNT(CASE WHEN ca.atom_type = 'mcq' THEN 1 END) as mcq_count,
            CASE
                WHEN cm.name ~ '^Module \\d+' THEN
                    CAST(SUBSTRING(cm.name FROM 'Module (\\d+)') AS INTEGER)
                ELSE 999
            END as module_number
        FROM clean_modules cm
        JOIN clean_atoms ca ON ca.module_id = cm.id
        JOIN clean_concepts cc ON ca.concept_id = cc.id
        JOIN clean_concept_clusters ccl ON cc.cluster_id = ccl.id
        GROUP BY cm.id, cm.name, ccl.name
        ORDER BY module_number
    """)
    )

    analysis = {
        "modules": [],
        "total_atoms": 0,
        "over_count": 0,
        "under_count": 0,
        "ok_count": 0,
    }

    for row in result.fetchall():
        complexity = classify_complexity(row.cluster_name)
        opt_min, opt_max, rec = compute_optimal_count(
            row.atom_count,
            complexity,
            row.concept_count,
        )

        if "ADD" in rec:
            analysis["under_count"] += 1
            status = "UNDER"
        elif "SPLIT" in rec:
            analysis["over_count"] += 1
            status = "OVER"
        else:
            analysis["ok_count"] += 1
            status = "OK"

        analysis["modules"].append(
            {
                "module": row.module_name,
                "cluster": row.cluster_name,
                "current": row.atom_count,
                "optimal_min": opt_min,
                "optimal_max": opt_max,
                "complexity": complexity,
                "status": status,
                "recommendation": rec,
                "type_breakdown": {
                    "flashcard": row.flashcard_count,
                    "cloze": row.cloze_count,
                    "mcq": row.mcq_count,
                },
            }
        )

        analysis["total_atoms"] += row.atom_count

    return analysis


def print_analysis(analysis: dict):
    """Print analysis results."""
    print("\n" + "=" * 100)
    print("OPTIMAL FLASHCARD ANALYSIS - Based on Learning Science")
    print("=" * 100)

    print("\nRESEARCH BASIS:")
    print("  - Cognitive Load Theory: ~4 chunks in working memory (Cowan, 2001)")
    print("  - SuperMemo 20 Rules: Atomic facts, minimum information (Wozniak, 1999)")
    print("  - FSRS Optimal: 20-30 new cards/day sustainable (open-spaced-repetition)")
    print("  - Interleaving: Mix topics for better retention (Bjork)")

    print("\n" + "=" * 100)
    print(f"{'Module':<50} | {'Current':>7} | {'Optimal':>12} | {'Status':>8} | Recommendation")
    print("=" * 100)

    for m in analysis["modules"]:
        module_short = m["module"][:48]
        opt_range = f"{m['optimal_min']}-{m['optimal_max']}"
        print(
            f"{module_short:<50} | {m['current']:>7} | {opt_range:>12} | {m['status']:>8} | {m['recommendation']}"
        )

    print("=" * 100)
    print("\nSUMMARY:")
    print(f"  Total atoms: {analysis['total_atoms']}")
    print(f"  Modules OK: {analysis['ok_count']}")
    print(f"  Modules over-populated: {analysis['over_count']}")
    print(f"  Modules under-populated: {analysis['under_count']}")

    print(f"\nSTUDY TIMELINE (at {NEW_CARDS_PER_DAY_OPTIMAL} new cards/day):")
    days_to_complete = analysis["total_atoms"] // NEW_CARDS_PER_DAY_OPTIMAL
    print(f"  Days to learn all: {days_to_complete} days (~{days_to_complete // 7} weeks)")
    print(f"  Daily review time: ~{MINUTES_PER_DAY_TARGET} minutes")

    # Atom type balance
    print("\nATOM TYPE DISTRIBUTION:")
    total_flashcard = sum(m["type_breakdown"]["flashcard"] for m in analysis["modules"])
    total_cloze = sum(m["type_breakdown"]["cloze"] for m in analysis["modules"])
    total_mcq = sum(m["type_breakdown"]["mcq"] for m in analysis["modules"])
    total = total_flashcard + total_cloze + total_mcq

    print(f"  Flashcards: {total_flashcard} ({100 * total_flashcard / total:.1f}%)")
    print(f"  Cloze: {total_cloze} ({100 * total_cloze / total:.1f}%)")
    print(f"  MCQ: {total_mcq} ({100 * total_mcq / total:.1f}%)")

    # Ideal ratio based on learning science
    print("\n  IDEAL RATIO (based on knowledge type coverage):")
    print("    Factual (flashcard/cloze): 40-50%")
    print("    Conceptual (MCQ/compare): 30-40%")
    print("    Procedural (sequence/parsons): 20-30%")


def main():
    parser = argparse.ArgumentParser(
        description="Compute optimal flashcard counts per concept/module"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    with session_scope() as session:
        analysis = analyze_atoms(session)

        if args.json:
            import json

            print(json.dumps(analysis, indent=2))
        else:
            print_analysis(analysis)

    return 0


if __name__ == "__main__":
    sys.exit(main())
