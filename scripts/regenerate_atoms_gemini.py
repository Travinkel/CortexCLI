#!/usr/bin/env python3
"""
Regenerate Low-Quality Learning Atoms Using Gemini

Uses Google Gemini to regenerate flagged/low-quality atoms:
- Flashcards with quality_score < 70
- True/False atoms with poor patterns
- MCQs that need better distractors

Maintains concept linkage and section assignments.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from config import get_settings
from loguru import logger

# Try to import Google Generative AI
try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    logger.warning("google-generativeai not installed. Run: pip install google-generativeai")


FLASHCARD_PROMPT = """You are an expert instructional designer creating high-quality flashcards for CCNA certification.

Given this context about a networking concept:
- Section: {section_title}
- Concept: {concept_name}
- Original (low quality) question: {original_front}
- Original answer: {original_back}

Create a clear, unambiguous flashcard that:
1. Has a specific, answerable question (not "What is X?")
2. Tests one fact or concept
3. Has a complete, self-contained answer (not truncated)
4. Uses proper networking terminology
5. Is factually accurate for CCNA

Return JSON:
{{
    "front": "The question",
    "back": "The complete answer",
    "quality_notes": "Why this is better"
}}
"""

TRUE_FALSE_PROMPT = """You are an expert instructional designer creating True/False statements for CCNA certification.

Given this context:
- Section: {section_title}
- Concept: {concept_name}
- Original (low quality) statement: {original_front}
- Original answer: {original_answer}

Create a clear, unambiguous True/False statement that:
1. Is a complete, standalone statement (not "X is defined as Y")
2. Tests a specific, verifiable fact
3. Has a clear True or False answer
4. Is factually accurate for CCNA
5. Does NOT start with "True or False:" (we add that in the UI)

Return JSON:
{{
    "front": "The complete statement to evaluate",
    "answer": true or false,
    "explanation": "Brief explanation of why this is true/false"
}}
"""

MCQ_PROMPT = """You are an expert instructional designer creating Multiple Choice Questions for CCNA certification.

Given this context:
- Section: {section_title}
- Concept: {concept_name}
- Topic: {topic}

Create a discriminative MCQ that:
1. Tests understanding, not just memorization
2. Has one clearly correct answer
3. Has 3 plausible but incorrect distractors
4. Distractors should test common misconceptions

Return JSON:
{{
    "front": "The question",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct": "The correct option (exact text)",
    "explanation": "Why this is correct and why distractors are wrong"
}}
"""


class AtomRegenerator:
    """Regenerates low-quality atoms using Gemini."""

    def __init__(self, api_key: Optional[str] = None):
        if not HAS_GENAI:
            raise RuntimeError("google-generativeai package not installed")

        settings = get_settings()
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or settings.gemini_api_key

        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not found in environment or config")

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(
            model_name=settings.ai_model or "gemini-2.0-flash",
            generation_config={
                "temperature": 0.3,
                "top_p": 0.9,
                "response_mime_type": "application/json",
            }
        )

        logger.info(f"Using Gemini model: {settings.ai_model or 'gemini-2.0-flash'}")

    def regenerate_flashcard(
        self,
        original_front: str,
        original_back: str,
        section_title: str = "",
        concept_name: str = "",
    ) -> Optional[dict]:
        """Regenerate a single flashcard."""
        prompt = FLASHCARD_PROMPT.format(
            section_title=section_title or "CCNA",
            concept_name=concept_name or "General Networking",
            original_front=original_front[:500],
            original_back=original_back[:300] if original_back else "No answer provided",
        )

        try:
            response = self.model.generate_content(prompt)
            data = json.loads(response.text)
            return data
        except Exception as e:
            logger.warning(f"Failed to regenerate flashcard: {e}")
            return None

    def regenerate_true_false(
        self,
        original_front: str,
        original_answer: bool,
        section_title: str = "",
        concept_name: str = "",
    ) -> Optional[dict]:
        """Regenerate a single True/False atom."""
        prompt = TRUE_FALSE_PROMPT.format(
            section_title=section_title or "CCNA",
            concept_name=concept_name or "General Networking",
            original_front=original_front[:500],
            original_answer="True" if original_answer else "False",
        )

        try:
            response = self.model.generate_content(prompt)
            data = json.loads(response.text)
            return data
        except Exception as e:
            logger.warning(f"Failed to regenerate T/F: {e}")
            return None

    def regenerate_mcq(
        self,
        topic: str,
        section_title: str = "",
        concept_name: str = "",
    ) -> Optional[dict]:
        """Generate a new MCQ for a topic."""
        prompt = MCQ_PROMPT.format(
            section_title=section_title or "CCNA",
            concept_name=concept_name or "General Networking",
            topic=topic,
        )

        try:
            response = self.model.generate_content(prompt)
            data = json.loads(response.text)
            return data
        except Exception as e:
            logger.warning(f"Failed to generate MCQ: {e}")
            return None


def regenerate_flagged_atoms(
    conn,
    regenerator: AtomRegenerator,
    atom_type: str,
    limit: int = 10,
    dry_run: bool = True,
) -> dict:
    """
    Regenerate flagged atoms of a given type.

    Args:
        conn: Database connection
        regenerator: AtomRegenerator instance
        atom_type: 'flashcard' or 'true_false'
        limit: Max atoms to process
        dry_run: If True, don't write to database

    Returns:
        Stats dict with counts
    """
    # Find flagged atoms
    if atom_type == "flashcard":
        flag_pattern = "%_flagged%"
    else:
        flag_pattern = "%_tf_flagged%"

    result = conn.execute(text("""
        SELECT
            ca.id, ca.card_id, ca.front, ca.back, ca.atom_type,
            ca.concept_id, ca.ccna_section_id,
            cc.name as concept_name,
            cs.title as section_title
        FROM clean_atoms ca
        LEFT JOIN clean_concepts cc ON ca.concept_id = cc.id
        LEFT JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
        WHERE ca.atom_type = :atom_type
          AND (ca.source LIKE :flag_pattern OR ca.quality_score < 50)
        ORDER BY ca.quality_score ASC
        LIMIT :limit
    """), {"atom_type": atom_type, "flag_pattern": flag_pattern, "limit": limit})

    rows = result.fetchall()
    logger.info(f"Found {len(rows)} flagged {atom_type} atoms to regenerate")

    stats = {"processed": 0, "regenerated": 0, "failed": 0}

    for row in rows:
        stats["processed"] += 1

        if atom_type == "flashcard":
            new_data = regenerator.regenerate_flashcard(
                original_front=row.front,
                original_back=row.back,
                section_title=row.section_title,
                concept_name=row.concept_name,
            )

            if new_data and "front" in new_data and "back" in new_data:
                logger.info(f"Regenerated: {new_data['front'][:50]}...")

                if not dry_run:
                    conn.execute(text("""
                        UPDATE clean_atoms
                        SET front = :front,
                            back = :back,
                            quality_score = 80.0,
                            source = 'gemini_regenerated'
                        WHERE id = :id
                    """), {
                        "id": str(row.id),
                        "front": new_data["front"],
                        "back": new_data["back"],
                    })

                stats["regenerated"] += 1
            else:
                stats["failed"] += 1

        elif atom_type == "true_false":
            # Parse original answer
            try:
                orig_data = json.loads(row.back)
                orig_answer = orig_data.get("answer", True)
            except:
                orig_answer = True

            new_data = regenerator.regenerate_true_false(
                original_front=row.front,
                original_answer=orig_answer,
                section_title=row.section_title,
                concept_name=row.concept_name,
            )

            if new_data and "front" in new_data and "answer" in new_data:
                logger.info(f"Regenerated T/F: {new_data['front'][:50]}...")

                new_back = json.dumps({
                    "answer": new_data["answer"],
                    "explanation": new_data.get("explanation", ""),
                })

                if not dry_run:
                    conn.execute(text("""
                        UPDATE clean_atoms
                        SET front = :front,
                            back = :back,
                            quality_score = 80.0,
                            source = 'gemini_regenerated'
                        WHERE id = :id
                    """), {
                        "id": str(row.id),
                        "front": new_data["front"],
                        "back": new_back,
                    })

                stats["regenerated"] += 1
            else:
                stats["failed"] += 1

        # Rate limiting
        time.sleep(0.5)

    if not dry_run:
        conn.commit()

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Regenerate low-quality atoms with Gemini")
    parser.add_argument("--type", choices=["flashcard", "true_false", "mcq"], required=True,
                        help="Atom type to regenerate")
    parser.add_argument("--limit", type=int, default=10, help="Max atoms to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to database")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.database_url)

    regenerator = AtomRegenerator()

    with engine.connect() as conn:
        if args.type in ("flashcard", "true_false"):
            stats = regenerate_flagged_atoms(
                conn,
                regenerator,
                atom_type=args.type,
                limit=args.limit,
                dry_run=args.dry_run,
            )
        else:
            logger.error("MCQ regeneration not yet implemented")
            return

        logger.info("\n" + "=" * 50)
        logger.info("REGENERATION SUMMARY")
        logger.info("=" * 50)
        logger.info(f"  Processed: {stats['processed']}")
        logger.info(f"  Regenerated: {stats['regenerated']}")
        logger.info(f"  Failed: {stats['failed']}")
        if args.dry_run:
            logger.info("  [DRY RUN - no changes written]")


if __name__ == "__main__":
    main()
