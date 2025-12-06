#!/usr/bin/env python3
"""
Batch Regenerate and Generate Learning Atoms Using Gemini

Handles:
1. Regenerating flagged T/F atoms (trick questions, confusing patterns)
2. Regenerating flagged flashcards (truncated, malformed)
3. Generating NEW MCQ, Matching, and Parsons atoms for sections

Uses Google Gemini 2.0 Flash with batch processing and rate limiting.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional, List
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from config import get_settings
from loguru import logger

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    logger.error("google-generativeai not installed. Run: pip install google-generativeai")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

TRUE_FALSE_REGEN_PROMPT = """You are an expert instructional designer for CCNA certification.

Given this poorly-formed True/False question:
- Section: {section_title}
- Original statement: {original_front}
- Original answer was: {original_answer}

The original is low quality because: {quality_issue}

Create a BETTER True/False statement that:
1. Tests real CCNA knowledge (not just attention to detail)
2. Is factually accurate
3. Has a clear True or False answer with meaningful explanation
4. Does NOT use "trick" wording (inserting "not", swapping similar terms)
5. Does NOT start with "True or False:" (UI adds that)

Return ONLY valid JSON:
{{"front": "Clear statement about networking concept", "answer": true, "explanation": "Why this is true/false based on CCNA material"}}
"""

FLASHCARD_REGEN_PROMPT = """You are an expert instructional designer for CCNA certification.

Given this poorly-formed flashcard:
- Section: {section_title}
- Original question: {original_front}
- Original answer: {original_back}

Create a BETTER flashcard that:
1. Has a specific, clear question (avoid "What is X?")
2. Tests one concept/fact
3. Has complete, self-contained answer
4. Uses proper CCNA terminology
5. Is factually accurate

Return ONLY valid JSON:
{{"front": "Clear question", "back": "Complete answer"}}
"""

MCQ_GENERATE_PROMPT = """You are an expert instructional designer creating MCQs for CCNA certification.

Create {count} multiple-choice questions for this CCNA section:
- Section: {section_title}
- Topics to cover: {topics}

Each MCQ must:
1. Test understanding, not memorization
2. Have ONE clearly correct answer
3. Have 3 plausible but incorrect distractors based on common misconceptions
4. Be factually accurate for CCNA

Return ONLY a valid JSON array:
[
  {{"front": "Question text?", "options": ["A", "B", "C", "D"], "correct": "The correct option text", "explanation": "Why correct and why others are wrong"}},
  ...
]
"""

MATCHING_GENERATE_PROMPT = """You are an expert instructional designer creating matching exercises for CCNA certification.

Create a matching exercise for this CCNA section:
- Section: {section_title}
- Topics: {topics}

Create 4-6 term-definition pairs that:
1. Test understanding of key concepts
2. Have clear, unambiguous matches
3. Use proper CCNA terminology
4. Terms should be related but distinct (not too easy)

Return ONLY valid JSON:
{{"front": "Match the networking terms with their definitions:", "pairs": [["Term1", "Definition1"], ["Term2", "Definition2"], ...]}}
"""

PARSONS_GENERATE_PROMPT = """You are an expert instructional designer creating Parsons problems for CCNA certification.

Create a procedure ordering exercise for this CCNA section:
- Section: {section_title}
- Topics: {topics}

Create a problem where the learner must put steps in correct order:
1. Should be a real networking procedure (config, troubleshooting, etc.)
2. 4-6 steps that have a logical order
3. Steps should be atomic and clear
4. Include distractor steps if appropriate

Return ONLY valid JSON:
{{"front": "Put these steps in the correct order to [procedure]:", "steps": ["Step 1", "Step 2", "Step 3", "Step 4"], "explanation": "Why this order is correct"}}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# GENERATOR CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class BatchGenerator:
    """Batch generate/regenerate atoms using Gemini."""

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or settings.gemini_api_key

        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not found")

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(
            model_name=settings.ai_model or "gemini-2.0-flash",
            generation_config={
                "temperature": 0.4,
                "top_p": 0.9,
                "response_mime_type": "application/json",
            }
        )
        self.requests_per_minute = 15  # Rate limit
        self.last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request_time
        min_interval = 60.0 / self.requests_per_minute
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_request_time = time.time()

    def _call_gemini(self, prompt: str) -> Optional[dict]:
        """Call Gemini with rate limiting and error handling."""
        self._rate_limit()
        try:
            response = self.model.generate_content(prompt)
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            return None
        except Exception as e:
            logger.warning(f"Gemini error: {e}")
            return None

    def regenerate_true_false(
        self,
        original_front: str,
        original_answer: bool,
        section_title: str,
        quality_issue: str = "confusing wording",
    ) -> Optional[dict]:
        """Regenerate a single T/F atom."""
        prompt = TRUE_FALSE_REGEN_PROMPT.format(
            section_title=section_title or "CCNA",
            original_front=original_front[:400],
            original_answer="True" if original_answer else "False",
            quality_issue=quality_issue,
        )
        return self._call_gemini(prompt)

    def regenerate_flashcard(
        self,
        original_front: str,
        original_back: str,
        section_title: str,
    ) -> Optional[dict]:
        """Regenerate a single flashcard."""
        prompt = FLASHCARD_REGEN_PROMPT.format(
            section_title=section_title or "CCNA",
            original_front=original_front[:400],
            original_back=original_back[:300] if original_back else "No answer",
        )
        return self._call_gemini(prompt)

    def generate_mcqs(
        self,
        section_title: str,
        topics: str,
        count: int = 3,
    ) -> Optional[List[dict]]:
        """Generate new MCQs for a section."""
        prompt = MCQ_GENERATE_PROMPT.format(
            section_title=section_title,
            topics=topics,
            count=count,
        )
        result = self._call_gemini(prompt)
        if isinstance(result, list):
            return result
        return None

    def generate_matching(
        self,
        section_title: str,
        topics: str,
    ) -> Optional[dict]:
        """Generate a matching exercise."""
        prompt = MATCHING_GENERATE_PROMPT.format(
            section_title=section_title,
            topics=topics,
        )
        return self._call_gemini(prompt)

    def generate_parsons(
        self,
        section_title: str,
        topics: str,
    ) -> Optional[dict]:
        """Generate a Parsons problem."""
        prompt = PARSONS_GENERATE_PROMPT.format(
            section_title=section_title,
            topics=topics,
        )
        return self._call_gemini(prompt)


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH PROCESSING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def batch_regenerate_tf(conn, generator: BatchGenerator, limit: int, dry_run: bool) -> dict:
    """Regenerate flagged T/F atoms."""
    # Find flagged atoms - prioritize trick questions
    result = conn.execute(text("""
        SELECT
            ca.id, ca.front, ca.back, ca.ccna_section_id,
            cs.title as section_title,
            CASE
                WHEN ca.back LIKE '%modified to be false%' THEN 'trick question'
                WHEN ca.front LIKE '%is defined as:%' THEN 'confusing defined-as pattern'
                ELSE 'other quality issue'
            END as quality_issue
        FROM clean_atoms ca
        LEFT JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
        WHERE ca.atom_type = 'true_false'
          AND (
            ca.back LIKE '%modified to be false%'
            OR ca.source LIKE '%_tf_flagged%'
            OR ca.quality_score < 50
          )
        ORDER BY
            CASE WHEN ca.back LIKE '%modified to be false%' THEN 0 ELSE 1 END,
            ca.quality_score ASC
        LIMIT :limit
    """), {"limit": limit})

    rows = result.fetchall()
    logger.info(f"Found {len(rows)} T/F atoms to regenerate")

    stats = {"processed": 0, "regenerated": 0, "failed": 0}

    for row in rows:
        stats["processed"] += 1

        # Parse original answer
        try:
            orig_data = json.loads(row.back) if row.back else {}
            orig_answer = orig_data.get("answer", True)
        except:
            orig_answer = True

        new_data = generator.regenerate_true_false(
            original_front=row.front,
            original_answer=orig_answer,
            section_title=row.section_title,
            quality_issue=row.quality_issue,
        )

        if new_data and "front" in new_data and "answer" in new_data:
            logger.info(f"[{stats['processed']}/{len(rows)}] Regenerated: {new_data['front'][:60]}...")

            new_back = json.dumps({
                "answer": new_data["answer"],
                "explanation": new_data.get("explanation", ""),
            })

            if not dry_run:
                conn.execute(text("""
                    UPDATE clean_atoms
                    SET front = :front,
                        back = :back,
                        quality_score = 8.5,
                        source = 'gemini_regenerated'
                    WHERE id = :id
                """), {
                    "id": str(row.id),
                    "front": new_data["front"],
                    "back": new_back,
                })

            stats["regenerated"] += 1
        else:
            logger.warning(f"[{stats['processed']}/{len(rows)}] Failed to regenerate")
            stats["failed"] += 1

        # Progress commit every 50
        if not dry_run and stats["processed"] % 50 == 0:
            conn.commit()
            logger.info(f"Committed batch of 50...")

    if not dry_run:
        conn.commit()

    return stats


def batch_regenerate_flashcards(conn, generator: BatchGenerator, limit: int, dry_run: bool) -> dict:
    """Regenerate flagged flashcards."""
    result = conn.execute(text("""
        SELECT
            ca.id, ca.front, ca.back, ca.ccna_section_id,
            cs.title as section_title
        FROM clean_atoms ca
        LEFT JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
        WHERE ca.atom_type = 'flashcard'
          AND (ca.source LIKE '%_flagged%' OR ca.quality_score < 50)
        ORDER BY ca.quality_score ASC
        LIMIT :limit
    """), {"limit": limit})

    rows = result.fetchall()
    logger.info(f"Found {len(rows)} flashcards to regenerate")

    stats = {"processed": 0, "regenerated": 0, "failed": 0}

    for row in rows:
        stats["processed"] += 1

        new_data = generator.regenerate_flashcard(
            original_front=row.front,
            original_back=row.back,
            section_title=row.section_title,
        )

        if new_data and "front" in new_data and "back" in new_data:
            logger.info(f"[{stats['processed']}/{len(rows)}] Regenerated: {new_data['front'][:60]}...")

            if not dry_run:
                conn.execute(text("""
                    UPDATE clean_atoms
                    SET front = :front,
                        back = :back,
                        quality_score = 8.5,
                        source = 'gemini_regenerated'
                    WHERE id = :id
                """), {
                    "id": str(row.id),
                    "front": new_data["front"],
                    "back": new_data["back"],
                })

            stats["regenerated"] += 1
        else:
            logger.warning(f"[{stats['processed']}/{len(rows)}] Failed to regenerate")
            stats["failed"] += 1

        if not dry_run and stats["processed"] % 50 == 0:
            conn.commit()
            logger.info(f"Committed batch of 50...")

    if not dry_run:
        conn.commit()

    return stats


def batch_generate_quiz_atoms(conn, generator: BatchGenerator, limit: int, dry_run: bool) -> dict:
    """Generate new MCQ, Matching, and Parsons atoms for sections lacking them."""
    # Find sections with few MCQ/matching/parsons
    result = conn.execute(text("""
        WITH section_counts AS (
            SELECT
                cs.section_id,
                cs.title,
                cs.module_number,
                COUNT(*) FILTER (WHERE ca.atom_type = 'mcq') as mcq_count,
                COUNT(*) FILTER (WHERE ca.atom_type = 'matching') as matching_count,
                COUNT(*) FILTER (WHERE ca.atom_type = 'parsons') as parsons_count,
                COUNT(*) FILTER (WHERE ca.atom_type IN ('flashcard', 'cloze')) as content_count,
                STRING_AGG(DISTINCT SUBSTRING(ca.front, 1, 50), '; ') as sample_topics
            FROM ccna_sections cs
            LEFT JOIN clean_atoms ca ON cs.section_id = ca.ccna_section_id
            GROUP BY cs.section_id, cs.title, cs.module_number
        )
        SELECT *
        FROM section_counts
        WHERE content_count > 5
          AND (mcq_count < 3 OR matching_count < 1 OR parsons_count < 1)
        ORDER BY content_count DESC
        LIMIT :limit
    """), {"limit": limit})

    rows = result.fetchall()
    logger.info(f"Found {len(rows)} sections needing quiz atoms")

    stats = {"sections": 0, "mcqs_created": 0, "matching_created": 0, "parsons_created": 0, "failed": 0}

    for row in rows:
        stats["sections"] += 1
        logger.info(f"[{stats['sections']}/{len(rows)}] Processing: {row.title}")

        # Generate MCQs if needed
        if row.mcq_count < 3:
            mcqs = generator.generate_mcqs(
                section_title=row.title,
                topics=row.sample_topics or row.title,
                count=3 - row.mcq_count,
            )

            if mcqs:
                for mcq in mcqs:
                    if not dry_run:
                        conn.execute(text("""
                            INSERT INTO clean_atoms (
                                id, card_id, atom_type, front, back,
                                ccna_section_id, quality_score, source
                            ) VALUES (
                                gen_random_uuid(), :card_id, 'mcq', :front, :back,
                                :section_id, 8.5, 'gemini_generated'
                            )
                        """), {
                            "card_id": f"mcq-{uuid4().hex[:8]}",
                            "front": mcq["front"],
                            "back": json.dumps({
                                "options": mcq["options"],
                                "correct": mcq["correct"],
                                "explanation": mcq.get("explanation", ""),
                            }),
                            "section_id": row.section_id,
                        })
                    stats["mcqs_created"] += 1
                    logger.info(f"  + MCQ: {mcq['front'][:50]}...")
            else:
                stats["failed"] += 1

        # Generate matching if needed
        if row.matching_count < 1:
            matching = generator.generate_matching(
                section_title=row.title,
                topics=row.sample_topics or row.title,
            )

            if matching and "pairs" in matching:
                if not dry_run:
                    conn.execute(text("""
                        INSERT INTO clean_atoms (
                            id, card_id, atom_type, front, back,
                            ccna_section_id, quality_score, source
                        ) VALUES (
                            gen_random_uuid(), :card_id, 'matching', :front, :back,
                            :section_id, 8.5, 'gemini_generated'
                        )
                    """), {
                        "card_id": f"match-{uuid4().hex[:8]}",
                        "front": matching["front"],
                        "back": json.dumps(matching["pairs"]),
                        "section_id": row.section_id,
                    })
                stats["matching_created"] += 1
                logger.info(f"  + Matching: {len(matching['pairs'])} pairs")
            else:
                stats["failed"] += 1

        # Generate parsons if needed
        if row.parsons_count < 1:
            parsons = generator.generate_parsons(
                section_title=row.title,
                topics=row.sample_topics or row.title,
            )

            if parsons and "steps" in parsons:
                if not dry_run:
                    conn.execute(text("""
                        INSERT INTO clean_atoms (
                            id, card_id, atom_type, front, back,
                            ccna_section_id, quality_score, source
                        ) VALUES (
                            gen_random_uuid(), :card_id, 'parsons', :front, :back,
                            :section_id, 8.5, 'gemini_generated'
                        )
                    """), {
                        "card_id": f"parsons-{uuid4().hex[:8]}",
                        "front": parsons["front"],
                        "back": json.dumps({
                            "steps": parsons["steps"],
                            "explanation": parsons.get("explanation", ""),
                        }),
                        "section_id": row.section_id,
                    })
                stats["parsons_created"] += 1
                logger.info(f"  + Parsons: {len(parsons['steps'])} steps")
            else:
                stats["failed"] += 1

        if not dry_run and stats["sections"] % 10 == 0:
            conn.commit()
            logger.info(f"Committed batch...")

    if not dry_run:
        conn.commit()

    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Batch regenerate/generate learning atoms")
    parser.add_argument("--tf", type=int, default=0, help="Regenerate N True/False atoms")
    parser.add_argument("--flashcards", type=int, default=0, help="Regenerate N flashcards")
    parser.add_argument("--quiz", type=int, default=0, help="Generate MCQ/matching/parsons for N sections")
    parser.add_argument("--all", type=int, default=0, help="Do all types with this limit each")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to database")
    args = parser.parse_args()

    if args.all > 0:
        args.tf = args.flashcards = args.quiz = args.all

    if args.tf == 0 and args.flashcards == 0 and args.quiz == 0:
        logger.error("Specify --tf N, --flashcards N, --quiz N, or --all N")
        sys.exit(1)

    settings = get_settings()
    engine = create_engine(settings.database_url)
    generator = BatchGenerator()

    total_stats = {}

    with engine.connect() as conn:
        if args.tf > 0:
            logger.info(f"\n{'='*60}\nREGENERATING TRUE/FALSE ATOMS\n{'='*60}")
            stats = batch_regenerate_tf(conn, generator, args.tf, args.dry_run)
            total_stats["true_false"] = stats
            logger.info(f"T/F: {stats['regenerated']}/{stats['processed']} regenerated, {stats['failed']} failed")

        if args.flashcards > 0:
            logger.info(f"\n{'='*60}\nREGENERATING FLASHCARDS\n{'='*60}")
            stats = batch_regenerate_flashcards(conn, generator, args.flashcards, args.dry_run)
            total_stats["flashcards"] = stats
            logger.info(f"Flashcards: {stats['regenerated']}/{stats['processed']} regenerated, {stats['failed']} failed")

        if args.quiz > 0:
            logger.info(f"\n{'='*60}\nGENERATING QUIZ ATOMS (MCQ/MATCHING/PARSONS)\n{'='*60}")
            stats = batch_generate_quiz_atoms(conn, generator, args.quiz, args.dry_run)
            total_stats["quiz"] = stats
            logger.info(f"Quiz: {stats['mcqs_created']} MCQs, {stats['matching_created']} matching, {stats['parsons_created']} parsons")

    # Final summary
    logger.info(f"\n{'='*60}\nFINAL SUMMARY\n{'='*60}")
    for category, stats in total_stats.items():
        logger.info(f"\n{category.upper()}:")
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")

    if args.dry_run:
        logger.info("\n[DRY RUN - No changes written to database]")


if __name__ == "__main__":
    main()
