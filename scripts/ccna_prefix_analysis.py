"""
Analyze card distribution by prefix to understand content categories.
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import engine
from sqlalchemy import text


def analyze_prefixes():
    """Analyze cards by prefix."""

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT card_id, quality_grade FROM stg_anki_cards
        """))

        prefixes = Counter()
        prefix_quality = {}

        for row in result:
            card_id = row[0] or ""
            grade = row[1]

            # Extract prefix (e.g., NET-M2, ART-VDF, SEC-SSF)
            parts = card_id.split('-')
            if len(parts) >= 2:
                prefix = f"{parts[0]}-{parts[1]}"
            else:
                prefix = card_id[:8] if card_id else "UNKNOWN"

            prefixes[prefix] += 1

            if prefix not in prefix_quality:
                prefix_quality[prefix] = Counter()
            prefix_quality[prefix][grade] += 1

        print("\n" + "=" * 90)
        print("CARD DISTRIBUTION BY PREFIX")
        print("=" * 90)
        print(f"{'Prefix':<15} {'Count':>8} {'A':>6} {'B':>6} {'C':>6} {'D':>6} {'F':>6} {'Description':<25}")
        print("-" * 90)

        # Known prefix descriptions
        descriptions = {
            "NET-M1": "CCNA Module 1",
            "NET-M2": "CCNA Module 2",
            "NET-M3": "CCNA Module 3",
            "NET-M4": "CCNA Module 4",
            "NET-M5": "CCNA Module 5",
            "NET-M6": "CCNA Module 6",
            "NET-M7": "CCNA Module 7",
            "NET-M8": "CCNA Module 8",
            "NET-M9": "CCNA Module 9",
            "NET-M10": "CCNA Module 10",
            "NET-M11": "CCNA Module 11",
            "NET-M12": "CCNA Module 12",
            "NET-M13": "CCNA Module 13",
            "NET-M14": "CCNA Module 14",
            "NET-M15": "CCNA Module 15",
            "NET-M16": "CCNA Module 16",
            "NET-M17": "CCNA Module 17",
            "ART-VDF": "Art/Visual Design",
            "SEC-SSF": "Security",
            "GAME-CBM": "Game (Danish)",
            "Card ID": "Template/Test",
        }

        net_total = 0
        other_total = 0

        for prefix, count in prefixes.most_common():
            qual = prefix_quality[prefix]
            desc = descriptions.get(prefix, "Unknown")
            print(f"{prefix:<15} {count:>8} {qual.get('A', 0):>6} {qual.get('B', 0):>6} "
                  f"{qual.get('C', 0):>6} {qual.get('D', 0):>6} {qual.get('F', 0):>6} {desc:<25}")

            if prefix.startswith("NET-"):
                net_total += count
            else:
                other_total += count

        print("-" * 90)
        print(f"\nNET-* (CCNA-related): {net_total}")
        print(f"Other prefixes: {other_total}")
        print(f"Percentage CCNA: {net_total / (net_total + other_total) * 100:.1f}%")

        # Detailed look at NET- prefixes
        print("\n" + "=" * 90)
        print("CCNA MODULE COVERAGE DETAIL")
        print("=" * 90)

        for i in range(1, 18):
            prefix = f"NET-M{i}"
            if prefix in prefixes:
                count = prefixes[prefix]
                qual = prefix_quality[prefix]
                good = qual.get('A', 0) + qual.get('B', 0)
                bad = qual.get('D', 0) + qual.get('F', 0)
                print(f"Module {i:2}: {count:4} cards (Good: {good:3}, Needs work: {bad:3})")
            else:
                print(f"Module {i:2}:    0 cards ** MISSING **")


if __name__ == "__main__":
    analyze_prefixes()
