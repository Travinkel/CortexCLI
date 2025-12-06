#!/usr/bin/env python3
"""
MCQ Regeneration Pipeline

Generates discriminative MCQs from concept definitions and atom text.
Uses Google Gemini API to create proper distractors.

Per atom-regeneration-design.md:
- Each MCQ tests ONE specific fact
- Exactly 1 correct answer (unambiguous)
- 3 plausible distractors (misconceptions, related terms, inverses)
- No generic "which is correct for X" stems
"""

import asyncio
import json
import os
import re
import sys
import uuid
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from config import get_settings
from loguru import logger

# Google Generative AI client
try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    logger.warning("google-generativeai package not installed - run: pip install google-generativeai")


@dataclass
class GeneratedMCQ:
    """Generated MCQ structure."""
    question: str
    correct: str
    distractors: list[dict]  # [{"text": str, "strategy": str}]
    rationale: str
    source_atom_id: Optional[str] = None
    concept_id: Optional[str] = None


MCQ_SYSTEM_PROMPT = """You are a test item designer with expertise in creating discriminative multiple choice questions for networking and IT certification exams.

Your MCQs must have exactly ONE correct answer that a domain expert can identify unambiguously.

RULES:
1. Question stem must test a SPECIFIC fact, not ask "which is correct for X"
2. Correct answer must be unambiguously correct
3. Each distractor must be:
   - Related to the topic (plausible to a learner)
   - Definitively incorrect (not partially correct)
   - Based on: common misconceptions, related-but-wrong terms, or inverse relationships
4. All options must be complete sentences without truncation
5. Options should be similar in length and structure
6. For networking topics, use accurate technical terminology"""


MCQ_USER_TEMPLATE = """Generate a multiple choice question for this learning concept.

CONCEPT: {concept_name}
DOMAIN: Networking / CCNA
FACTUAL STATEMENT: {atom_text}

Respond ONLY with valid JSON (no markdown, no explanation):
{{
  "question": "The specific question testing this fact",
  "correct": "The unambiguously correct answer",
  "distractors": [
    {{"text": "Distractor 1", "strategy": "misconception"}},
    {{"text": "Distractor 2", "strategy": "related_term"}},
    {{"text": "Distractor 3", "strategy": "inverse"}}
  ],
  "rationale": "Brief explanation of why this tests the stated fact"
}}"""


class MCQGenerator:
    """Generates discriminative MCQs using Google Gemini API."""

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()

        # Try: explicit arg > env var > config file
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or settings.gemini_api_key
        self.model_name = settings.ai_model or "gemini-2.0-flash"

        if HAS_GENAI and self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=MCQ_SYSTEM_PROMPT
            )
            logger.info(f"Using Gemini API with model: {self.model_name}")
        else:
            self.model = None
            if not HAS_GENAI:
                logger.error("google-generativeai not installed. Run: pip install google-generativeai")
            else:
                logger.error("No Gemini API key found. Set GEMINI_API_KEY or gemini_api_key in .env")

    def generate(self, concept_name: str, atom_text: str) -> Optional[GeneratedMCQ]:
        """Generate a single MCQ from concept and atom text."""
        if not self.model:
            logger.error("No LLM model available - cannot generate MCQ")
            return None
        return self._generate_with_llm(concept_name, atom_text)

    def _generate_with_llm(self, concept_name: str, atom_text: str) -> Optional[GeneratedMCQ]:
        """Generate MCQ using Gemini API."""
        try:
            prompt = MCQ_USER_TEMPLATE.format(
                concept_name=concept_name,
                atom_text=atom_text
            )

            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=1024,
                )
            )

            # Parse JSON response
            content = response.text.strip()
            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = re.sub(r'^```(?:json)?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)

            data = json.loads(content)

            return GeneratedMCQ(
                question=data["question"],
                correct=data["correct"],
                distractors=data["distractors"],
                rationale=data.get("rationale", "")
            )

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return None


def validate_mcq(mcq: GeneratedMCQ) -> tuple[bool, list[str]]:
    """
    Validate MCQ meets discriminative quality standards.

    Returns (is_valid, issues)
    """
    issues = []

    # Check for generic question stems
    generic_patterns = [
        r"which of the following is correct",
        r"which.*is true for",
        r"select the correct.*for",
        r"what is correct for"
    ]
    for pattern in generic_patterns:
        if re.search(pattern, mcq.question.lower()):
            issues.append("REJECT: Generic question stem")
            break

    # Check correct answer length
    if len(mcq.correct) < 5:
        issues.append("REJECT: Correct answer too short")
    if len(mcq.correct) > 300:
        issues.append("WARN: Correct answer very long")

    # Check distractors
    if len(mcq.distractors) != 3:
        issues.append(f"REJECT: Expected 3 distractors, got {len(mcq.distractors)}")

    for d in mcq.distractors:
        if len(d.get("text", "")) < 5:
            issues.append(f"REJECT: Distractor too short: {d.get('text', '')[:20]}")

    # Check for duplicate options
    all_options = [mcq.correct] + [d["text"] for d in mcq.distractors]
    if len(all_options) != len(set(all_options)):
        issues.append("REJECT: Duplicate options detected")

    is_valid = not any(i.startswith("REJECT") for i in issues)
    return is_valid, issues


def get_atoms_for_mcq_generation(conn, limit: int = 100) -> list[dict]:
    """
    Get atoms that can be used to generate MCQs.

    Selects flashcard atoms with concept associations.
    """
    result = conn.execute(text('''
        SELECT
            ca.id,
            ca.card_id,
            ca.front,
            ca.back,
            ca.concept_id,
            cc.name as concept_name,
            cs.module_number,
            cs.title as section_title
        FROM learning_atoms ca
        LEFT JOIN concepts cc ON ca.concept_id = cc.id
        LEFT JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
        WHERE ca.atom_type = 'flashcard'
          AND ca.front IS NOT NULL
          AND ca.back IS NOT NULL
          AND LENGTH(ca.back) > 30
          AND ca.back NOT LIKE '%|%'  -- Skip malformed table data
          AND ca.front NOT LIKE '%What is This%'  -- Skip malformed questions
        ORDER BY cs.module_number, RANDOM()
        LIMIT :limit
    '''), {'limit': limit})

    atoms = []
    for row in result:
        atoms.append({
            'id': str(row.id),
            'card_id': row.card_id,
            'front': row.front,
            'back': row.back,
            'concept_id': str(row.concept_id) if row.concept_id else None,
            'concept_name': row.concept_name or 'Networking Concept',
            'module': row.module_number,
            'section': row.section_title
        })

    return atoms


def insert_mcq(conn, mcq: GeneratedMCQ, source_atom: dict) -> Optional[str]:
    """Insert generated MCQ into database."""
    try:
        # Generate new UUID for MCQ
        mcq_id = str(uuid.uuid4())

        # Build card_id
        module = source_atom.get('module', 0)
        card_id = f"NET-M{module}-MCQ-{mcq_id[:8].upper()}"

        # Build back JSON
        back_json = json.dumps({
            "correct": mcq.correct,
            "options": [mcq.correct] + [d["text"] for d in mcq.distractors],
            "distractors": mcq.distractors,
            "rationale": mcq.rationale
        })

        conn.execute(text('''
            INSERT INTO learning_atoms (
                id, card_id, front, back, atom_type, concept_id,
                ccna_section_id, source, quality_score
            )
            SELECT
                :id::uuid,
                :card_id,
                :front,
                :back,
                'mcq',
                :concept_id::uuid,
                ca.ccna_section_id,
                'regenerated',
                80.0  -- Default quality score for new MCQs
            FROM learning_atoms ca
            WHERE ca.id = :source_id::uuid
        '''), {
            'id': mcq_id,
            'card_id': card_id,
            'front': mcq.question,
            'back': back_json,
            'concept_id': source_atom.get('concept_id'),
            'source_id': source_atom['id']
        })

        return mcq_id

    except Exception as e:
        logger.error(f"Failed to insert MCQ: {e}")
        return None


def main():
    """Main MCQ regeneration pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate discriminative MCQs using Gemini")
    parser.add_argument("--limit", type=int, default=10, help="Number of MCQs to generate")
    parser.add_argument("--dry-run", action="store_true", help="Don't insert into database")
    parser.add_argument("--api-key", help="Gemini API key (or set GEMINI_API_KEY)")
    parser.add_argument("--batch-delay", type=float, default=0.5, help="Delay between API calls (rate limiting)")
    args = parser.parse_args()

    logger.info(f"Starting MCQ regeneration (limit={args.limit}, dry_run={args.dry_run})")

    settings = get_settings()
    engine = create_engine(settings.database_url)

    generator = MCQGenerator(api_key=args.api_key)

    if not generator.model:
        logger.error("Cannot proceed without LLM. Exiting.")
        sys.exit(1)

    with engine.connect() as conn:
        # Get source atoms
        atoms = get_atoms_for_mcq_generation(conn, limit=args.limit * 2)  # Get extra for failures
        logger.info(f"Found {len(atoms)} candidate atoms for MCQ generation")

        generated = 0
        failed = 0
        validated = 0

        for atom in atoms:
            if generated >= args.limit:
                break

            logger.info(f"Generating MCQ from: {atom['front'][:50]}...")

            # Generate MCQ
            mcq = generator.generate(
                concept_name=atom['concept_name'],
                atom_text=atom['back']
            )

            if not mcq:
                failed += 1
                continue

            # Validate
            is_valid, issues = validate_mcq(mcq)

            if not is_valid:
                logger.warning(f"MCQ validation failed: {issues}")
                failed += 1
                continue

            validated += 1

            # Log the generated MCQ
            logger.info(f"  Q: {mcq.question[:80]}...")
            logger.info(f"  A: {mcq.correct[:60]}...")
            for d in mcq.distractors[:2]:
                logger.info(f"  D ({d['strategy']}): {d['text'][:50]}...")

            # Insert if not dry run
            if not args.dry_run:
                mcq_id = insert_mcq(conn, mcq, atom)
                if mcq_id:
                    generated += 1
                    logger.info(f"  Inserted MCQ: {mcq_id}")
                else:
                    failed += 1
            else:
                generated += 1

            # Rate limiting
            if args.batch_delay > 0:
                time.sleep(args.batch_delay)

        if not args.dry_run:
            conn.commit()

        logger.info(f"\n=== MCQ REGENERATION SUMMARY ===")
        logger.info(f"  Generated: {generated}")
        logger.info(f"  Validated: {validated}")
        logger.info(f"  Failed: {failed}")

        # Show current MCQ count
        result = conn.execute(text("SELECT COUNT(*) FROM learning_atoms WHERE atom_type = 'mcq'"))
        total = result.scalar()
        logger.info(f"  Total MCQs in database: {total}")


if __name__ == "__main__":
    main()
