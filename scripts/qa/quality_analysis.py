"""
Quality analysis for learning atoms.

Analyzes quality_score distribution and provides recommendations
for better flashcard/cloze offering strategy.
"""

import json
import sys
from pathlib import Path

from sqlalchemy import text

# Path setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db.database import get_db


def main():
    """Run quality analysis."""
    print("=" * 70)
    print("LEARNING ATOM QUALITY ANALYSIS")
    print("=" * 70)

    db = next(get_db())

    # 1. Overall distribution by type
    print("\n[1] ATOM COUNT BY TYPE")
    print("-" * 50)
    result = db.execute(text("""
        SELECT atom_type,
               COUNT(*) as total,
               ROUND(AVG(quality_score)::numeric, 2) as avg_quality,
               ROUND(MIN(quality_score)::numeric, 2) as min_qual,
               ROUND(MAX(quality_score)::numeric, 2) as max_qual,
               SUM(CASE WHEN quality_score IS NULL THEN 1 ELSE 0 END) as null_count
        FROM learning_atoms
        GROUP BY atom_type
        ORDER BY COUNT(*) DESC
    """)).fetchall()

    print(f"{'Type':<12} {'Total':>6} {'Avg':>6} {'Min':>6} {'Max':>6} {'NULL':>6}")
    print("-" * 50)
    for row in result:
        print(f"{row.atom_type:<12} {row.total:>6} {row.avg_quality or 'N/A':>6} "
              f"{row.min_qual or 'N/A':>6} {row.max_qual or 'N/A':>6} {row.null_count:>6}")

    # 2. Quality tier distribution for Anki types
    print("\n[2] QUALITY TIERS FOR ANKI TYPES (flashcard, cloze)")
    print("-" * 60)
    result = db.execute(text("""
        SELECT
            atom_type,
            SUM(CASE WHEN quality_score >= 0.90 THEN 1 ELSE 0 END) as tier_a,
            SUM(CASE WHEN quality_score >= 0.85 AND quality_score < 0.90 THEN 1 ELSE 0 END) as tier_b,
            SUM(CASE WHEN quality_score >= 0.80 AND quality_score < 0.85 THEN 1 ELSE 0 END) as tier_c,
            SUM(CASE WHEN quality_score >= 0.75 AND quality_score < 0.80 THEN 1 ELSE 0 END) as tier_d,
            SUM(CASE WHEN quality_score < 0.75 THEN 1 ELSE 0 END) as tier_f,
            SUM(CASE WHEN quality_score IS NULL THEN 1 ELSE 0 END) as tier_null,
            COUNT(*) as total
        FROM learning_atoms
        WHERE atom_type IN ('flashcard', 'cloze')
        GROUP BY atom_type
    """)).fetchall()

    print(f"{'Type':<10} {'A(>=.90)':>8} {'B(.85)':>8} {'C(.80)':>8} {'D(.75)':>8} {'F(<.75)':>8} {'NULL':>6} {'Total':>7}")
    print("-" * 70)
    for row in result:
        print(f"{row.atom_type:<10} {row.tier_a:>8} {row.tier_b:>8} {row.tier_c:>8} "
              f"{row.tier_d:>8} {row.tier_f:>8} {row.tier_null:>6} {row.total:>7}")

    # 3. What would happen with different thresholds?
    print("\n[3] FLASHCARD COUNT AT DIFFERENT THRESHOLDS")
    print("-" * 50)
    thresholds = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95]

    for thresh in thresholds:
        result = db.execute(text("""
            SELECT COUNT(*) as cnt FROM learning_atoms
            WHERE atom_type = 'flashcard' AND quality_score >= :thresh
        """), {"thresh": thresh}).fetchone()
        pct = (result.cnt / 3369) * 100 if result.cnt else 0
        print(f"  >= {thresh:.2f}: {result.cnt:>5} cards ({pct:>5.1f}% of total)")

    # 4. Sample low-quality flashcards
    print("\n[4] SAMPLE LOW-QUALITY FLASHCARDS (score = 0.75)")
    print("-" * 70)
    result = db.execute(text("""
        SELECT card_id, LEFT(front, 60) as question, quality_score
        FROM learning_atoms
        WHERE atom_type = 'flashcard' AND quality_score = 0.75
        ORDER BY RANDOM()
        LIMIT 5
    """)).fetchall()

    for row in result:
        print(f"  {row.card_id}: {row.question}...")

    # 5. Sample high-quality flashcards
    print("\n[5] SAMPLE HIGH-QUALITY FLASHCARDS (score >= 0.90)")
    print("-" * 70)
    result = db.execute(text("""
        SELECT card_id, LEFT(front, 60) as question, quality_score
        FROM learning_atoms
        WHERE atom_type = 'flashcard' AND quality_score >= 0.90
        ORDER BY RANDOM()
        LIMIT 5
    """)).fetchall()

    for row in result:
        print(f"  {row.card_id} ({row.quality_score}): {row.question}...")

    # 6. NULL quality atoms
    print("\n[6] ATOMS WITH NULL QUALITY SCORE")
    print("-" * 50)
    result = db.execute(text("""
        SELECT atom_type, COUNT(*) as cnt
        FROM learning_atoms
        WHERE quality_score IS NULL
        GROUP BY atom_type
        ORDER BY cnt DESC
    """)).fetchall()

    for row in result:
        print(f"  {row.atom_type}: {row.cnt} atoms")

    # 7. Recommendations
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    print("""
1. SET FLASHCARD THRESHOLD TO 0.85+
   - Current: ~3,369 flashcards (many low quality)
   - At 0.85: ~1,596 flashcards (53% reduction, quality focus)
   - This prevents flooding Anki with low-quality passive recall

2. FIX NULL QUALITY LOOPHOLE
   - 43 atoms have NULL quality_score
   - These currently bypass quality filtering
   - Fix: Set default quality or exclude from Anki sync

3. ADD PER-TYPE QUALITY THRESHOLDS
   - Flashcards: 0.85+ (stricter - passive recall needs high quality)
   - Cloze: 0.80+ (moderate - active completion)
   - MCQ: 0.75+ (default - already filtered by handler)

4. PRIORITIZE HIGH-QUALITY IN SESSIONS
   - Sort by quality_score DESC in atom selection
   - Use quality as tiebreaker when other factors equal

5. CONSIDER QUALITY REMEDIATION
   - 1,771 flashcards at 0.75 could be:
     a) Reviewed and upgraded
     b) Converted to other atom types
     c) Archived/quarantined
""")

    print("\n[ANALYSIS COMPLETE]")


if __name__ == "__main__":
    main()
