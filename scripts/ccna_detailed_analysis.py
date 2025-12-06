"""
Detailed CCNA Card Analysis - Find hallucinations and gaps.
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import engine
from sqlalchemy import text


def analyze_cards():
    """Detailed analysis of existing cards."""

    with engine.connect() as conn:
        # Sample of Grade F cards (likely hallucinations)
        print("\n" + "=" * 80)
        print("GRADE F CARDS (Likely Need Regeneration) - Sample of 20")
        print("=" * 80)

        result = conn.execute(text("""
            SELECT card_id, front, back, quality_grade
            FROM stg_anki_cards
            WHERE quality_grade = 'F'
            LIMIT 20
        """))

        for i, row in enumerate(result, 1):
            front = (row[1] or "")[:80].replace('\n', ' ')
            back = (row[2] or "")[:60].replace('\n', ' ')
            print(f"\n{i}. [{row[0]}]")
            print(f"   Q: {front}...")
            print(f"   A: {back}...")

        # Sample of Grade A cards (good quality)
        print("\n" + "=" * 80)
        print("GRADE A CARDS (Good Quality) - Sample of 10")
        print("=" * 80)

        result = conn.execute(text("""
            SELECT card_id, front, back
            FROM stg_anki_cards
            WHERE quality_grade = 'A'
            LIMIT 10
        """))

        for i, row in enumerate(result, 1):
            front = (row[1] or "")[:80].replace('\n', ' ')
            back = (row[2] or "")[:60].replace('\n', ' ')
            print(f"\n{i}. [{row[0]}]")
            print(f"   Q: {front}")
            print(f"   A: {back}")

        # Find cards with empty or very short backs
        print("\n" + "=" * 80)
        print("CARDS WITH PROBLEMATIC ANSWERS")
        print("=" * 80)

        result = conn.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE LENGTH(back) < 5) as very_short,
                COUNT(*) FILTER (WHERE LENGTH(back) < 10) as short,
                COUNT(*) FILTER (WHERE back IS NULL OR back = '') as empty,
                COUNT(*) FILTER (WHERE LENGTH(back) > 500) as too_long
            FROM stg_anki_cards
        """))

        row = result.fetchone()
        print(f"Empty answers: {row[2]}")
        print(f"Very short (<5 chars): {row[0]}")
        print(f"Short (<10 chars): {row[1]}")
        print(f"Too long (>500 chars): {row[3]}")

        # Find patterns in card_ids to detect module grouping
        print("\n" + "=" * 80)
        print("CARD ID PATTERNS (for module detection)")
        print("=" * 80)

        result = conn.execute(text("""
            SELECT card_id FROM stg_anki_cards LIMIT 100
        """))

        card_ids = [row[0] for row in result]
        prefixes = Counter()
        for cid in card_ids:
            if cid:
                parts = cid.split('-')
                if len(parts) >= 2:
                    prefixes[f"{parts[0]}-{parts[1]}"] += 1
                else:
                    prefixes[cid[:10]] += 1

        print("Common prefixes:")
        for prefix, count in prefixes.most_common(20):
            print(f"  {prefix}: {count}")

        # Check for duplicate fronts (potential duplicates)
        print("\n" + "=" * 80)
        print("DUPLICATE DETECTION")
        print("=" * 80)

        result = conn.execute(text("""
            SELECT front, COUNT(*) as cnt
            FROM stg_anki_cards
            WHERE front IS NOT NULL
            GROUP BY front
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
            LIMIT 10
        """))

        dup_count = 0
        for row in result:
            dup_count += row[1] - 1  # Extra copies
            front = (row[0] or "")[:60].replace('\n', ' ')
            print(f"  [{row[1]}x] {front}...")

        print(f"\nTotal duplicate cards: ~{dup_count}")

        # Content analysis - look for networking terms
        print("\n" + "=" * 80)
        print("CONTENT RELEVANCE CHECK")
        print("=" * 80)

        result = conn.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE LOWER(front) LIKE '%network%' OR LOWER(back) LIKE '%network%') as has_network,
                COUNT(*) FILTER (WHERE LOWER(front) LIKE '%router%' OR LOWER(back) LIKE '%router%') as has_router,
                COUNT(*) FILTER (WHERE LOWER(front) LIKE '%switch%' OR LOWER(back) LIKE '%switch%') as has_switch,
                COUNT(*) FILTER (WHERE LOWER(front) LIKE '%ip%' OR LOWER(back) LIKE '%ip%') as has_ip,
                COUNT(*) FILTER (WHERE LOWER(front) LIKE '%cisco%' OR LOWER(back) LIKE '%cisco%') as has_cisco,
                COUNT(*) FILTER (WHERE LOWER(front) LIKE '%protocol%' OR LOWER(back) LIKE '%protocol%') as has_protocol,
                COUNT(*) FILTER (WHERE LOWER(front) LIKE '%ethernet%' OR LOWER(back) LIKE '%ethernet%') as has_ethernet
            FROM stg_anki_cards
        """))

        row = result.fetchone()
        total = row[0]
        print(f"Total cards: {total}")
        print(f"  Contains 'network': {row[1]} ({row[1]/total*100:.1f}%)")
        print(f"  Contains 'router': {row[2]} ({row[2]/total*100:.1f}%)")
        print(f"  Contains 'switch': {row[3]} ({row[3]/total*100:.1f}%)")
        print(f"  Contains 'ip': {row[4]} ({row[4]/total*100:.1f}%)")
        print(f"  Contains 'cisco': {row[5]} ({row[5]/total*100:.1f}%)")
        print(f"  Contains 'protocol': {row[6]} ({row[6]/total*100:.1f}%)")
        print(f"  Contains 'ethernet': {row[7]} ({row[7]/total*100:.1f}%)")

        # Cards without any networking terms
        result = conn.execute(text("""
            SELECT COUNT(*)
            FROM stg_anki_cards
            WHERE NOT (
                LOWER(front || ' ' || COALESCE(back, '')) ~ '(network|router|switch|ip|cisco|protocol|ethernet|packet|vlan|subnet|tcp|udp|port|mac|osi|layer|interface|bandwidth)'
            )
        """))

        no_network = result.scalar()
        print(f"\nCards with NO networking terms: {no_network} ({no_network/total*100:.1f}%)")
        print("  (These may be hallucinations or unrelated content)")


if __name__ == "__main__":
    analyze_cards()
