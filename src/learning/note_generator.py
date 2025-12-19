"""
Remediation Note Generator.

Generates targeted study notes for weak sections using LLM + source materials.
Notes are designed to build understanding before drilling with flashcards.

Based on learning science principles:
- Elaborative interrogation (explain WHY)
- Contrastive learning (compare confusable concepts)
- Worked examples (step-by-step demonstrations)
- Mental models (conceptual frameworks)
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.content.reader import ContentReader
from src.db.database import get_session
from src.db.models import RemediationNote

# Try to import Google Generative AI
try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    logger.warning("google.generativeai not available - note generation disabled")


# Configuration - support multiple API key environment variable names
GENAI_API_KEY = (
    os.environ.get("GOOGLE_API_KEY")
    or os.environ.get("GEMINI_API_KEY")
    or ""
)
DEFAULT_MODEL = "gemini-2.0-flash"  # Current stable Gemini model


class NoteType:
    """Types of remediation notes based on NCDE failure modes."""
    SUMMARY = "summary"           # General review - mental models + memory hooks
    CONTRASTIVE = "contrastive"   # For DISCRIMINATION_ERROR - side-by-side comparison
    PROCEDURAL = "procedural"     # For INTEGRATION_ERROR - worked examples
    ELABORATIVE = "elaborative"   # For ENCODING_ERROR - deep "why" explanations


@dataclass
class NoteGenerationResult:
    """Result of note generation."""
    success: bool
    note_id: str | None = None
    title: str | None = None
    content: str | None = None
    note_type: str = NoteType.SUMMARY
    error: str | None = None


class NoteGenerator:
    """
    Generates study notes for weak sections.

    Uses source materials + LLM to create targeted notes that:
    - Explain concepts in different ways
    - Build mental models
    - Contrast confusable concepts
    - Provide worked examples
    """

    def __init__(
        self,
        content_reader: ContentReader | None = None,
        model_name: str = DEFAULT_MODEL,
    ):
        self.content_reader = content_reader or ContentReader()
        self.model_name = model_name
        self._model = None

        if HAS_GENAI and GENAI_API_KEY:
            genai.configure(api_key=GENAI_API_KEY)
            self._model = genai.GenerativeModel(model_name)

    def generate_note(
        self,
        section_id: str,
        weak_concepts: list[str] | None = None,
        error_patterns: list[str] | None = None,
        note_type: str = NoteType.SUMMARY,
        learner_context: str | None = None,
        db_session: Session | None = None,
    ) -> NoteGenerationResult:
        """
        Generate a study note for a section.

        Args:
            section_id: Section identifier (e.g., "10.1", "11.2.3")
            weak_concepts: Specific concepts the learner struggled with
            error_patterns: Types of errors made (e.g., "confusion", "forgot")
            note_type: Type of note to generate (summary, contrastive, procedural, elaborative)
            learner_context: Optional learner persona context
            db_session: Database session (creates new if not provided)

        Returns:
            NoteGenerationResult with success status and content
        """
        if not self._model:
            return NoteGenerationResult(
                success=False,
                error="LLM not configured. Set GOOGLE_API_KEY environment variable."
            )

        # Parse section_id to get module number
        parts = section_id.split(".")
        try:
            module_num = int(parts[0])
        except (ValueError, IndexError):
            return NoteGenerationResult(
                success=False,
                error=f"Invalid section_id format: {section_id}"
            )

        # Load source material
        section = self.content_reader.get_section(module_num, section_id)
        if not section:
            return NoteGenerationResult(
                success=False,
                error=f"Section {section_id} not found in module {module_num}"
            )

        # Build the prompt based on note type
        prompt = self._build_prompt(section, weak_concepts, error_patterns, note_type, learner_context)

        # Generate with LLM
        try:
            response = self._model.generate_content(prompt)
            content = response.text
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return NoteGenerationResult(
                success=False,
                error=f"LLM generation failed: {str(e)}"
            )

        # Parse response to extract title and content
        title, note_content = self._parse_response(content, section.title)

        # Calculate source hash for staleness tracking
        source_hash = hashlib.sha256(section.content.encode()).hexdigest()[:16]

        # Store in database
        session = db_session or next(get_session())
        try:
            # Check if note already exists
            existing = session.execute(
                text("SELECT id FROM remediation_notes WHERE section_id = :section_id"),
                {"section_id": section_id}
            ).fetchone()

            if existing:
                # Update existing note
                session.execute(
                    text("""
                        UPDATE remediation_notes SET
                            title = :title,
                            content = :content,
                            source_hash = :source_hash,
                            note_type = :note_type,
                            is_stale = FALSE,
                            created_at = NOW(),
                            expires_at = NOW() + INTERVAL '30 days'
                        WHERE section_id = :section_id
                        RETURNING id
                    """),
                    {
                        "section_id": section_id,
                        "title": title,
                        "content": note_content,
                        "source_hash": source_hash,
                        "note_type": note_type,
                    }
                )
                note_id = str(existing.id)
            else:
                # Insert new note
                result = session.execute(
                    text("""
                        INSERT INTO remediation_notes (
                            section_id, module_number, title, content, source_hash, note_type
                        ) VALUES (
                            :section_id, :module_number, :title, :content, :source_hash, :note_type
                        )
                        RETURNING id
                    """),
                    {
                        "section_id": section_id,
                        "module_number": module_num,
                        "title": title,
                        "content": note_content,
                        "source_hash": source_hash,
                        "note_type": note_type,
                    }
                )
                note_id = str(result.fetchone().id)

            session.commit()

            return NoteGenerationResult(
                success=True,
                note_id=note_id,
                title=title,
                content=note_content,
                note_type=note_type,
            )

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store note: {e}")
            return NoteGenerationResult(
                success=False,
                error=f"Database error: {str(e)}"
            )

    def _build_prompt(
        self,
        section,
        weak_concepts: list[str] | None,
        error_patterns: list[str] | None,
        note_type: str = NoteType.SUMMARY,
        learner_context: str | None = None,
    ) -> str:
        """Build the LLM prompt for note generation based on note type."""

        # Base context
        context = f"""You are an expert CCNA instructor creating targeted study notes.

## Source Material
Section: {section.title}
Content:
{section.content[:8000]}
"""

        # Add learner context if available
        if learner_context:
            context += f"\n## Learner Profile\n{learner_context}\n"

        # Type-specific task prompts
        if note_type == NoteType.CONTRASTIVE:
            # For DISCRIMINATION_ERROR - side-by-side comparison
            task = """
## Your Task: CONTRASTIVE NOTE (For Confusion Between Similar Concepts)

Create a comparison note (300-400 words) that:

1. **Side-by-Side Table**: Create a comparison table with columns for:
   - Feature/Aspect | Concept A | Concept B

2. **Key Distinguishing Feature**: Identify THE ONE thing that most clearly separates them
   - "The golden rule: If you see X, it's definitely A, not B"

3. **Common Trap**: Explain the most common confusion
   - "Students often mix these up when..."

4. **Quick Test**: A one-question self-test to check understanding
   - "Q: [Scenario] - Is this A or B? Answer: ..."

5. **Memory Trick**: A mnemonic to remember the difference
"""
        elif note_type == NoteType.PROCEDURAL:
            # For INTEGRATION_ERROR - worked examples
            task = """
## Your Task: PROCEDURAL NOTE (For Step-by-Step Understanding)

Create a worked example note (400-500 words) that:

1. **Goal Statement**: What we're trying to accomplish
   - "Objective: [specific outcome]"

2. **Prerequisites**: What you need to know first
   - List 2-3 prerequisite concepts

3. **Step-by-Step Walkthrough**: Detailed worked example
   - Step 1: [Action] → [Result] (Why: ...)
   - Step 2: [Action] → [Result] (Why: ...)
   - Continue until complete

4. **Verification Check**: How to verify your answer
   - "To check your work: [verification method]"

5. **Common Mistakes**: What can go wrong at each step
   - "At step X, don't forget to..."

6. **Practice Problem**: One additional problem with answer
"""
        elif note_type == NoteType.ELABORATIVE:
            # For ENCODING_ERROR - deep "why" explanations
            task = """
## Your Task: ELABORATIVE NOTE (For Deep Understanding)

Create an explanatory note (300-400 words) that answers "WHY":

1. **The Big Picture**: Why does this concept exist?
   - What problem does it solve?
   - What would happen without it?

2. **How It Works**: The underlying mechanism
   - Use an analogy from everyday life
   - "Think of it like [familiar concept]..."

3. **Real-World Connection**: Practical application
   - When would a network engineer use this?
   - What decisions depend on understanding this?

4. **Deeper Insight**: Something not obvious from the surface
   - "What most students miss is..."

5. **Memory Anchor**: Connect to something they already know
   - "This is similar to [other concept] because..."
"""
        else:  # NoteType.SUMMARY (default)
            task = """
## Your Task: SUMMARY NOTE (General Review)

Create concise study notes (300-500 words) that:

1. **Mental Model**: Start with a simple analogy or mental model
   - "Think of [concept] like [familiar thing]..."

2. **Key Concepts**: Explain the most important ideas
   - Focus on the WHY, not just the WHAT
   - Use simple language

3. **Common Confusions**: Address typical misconceptions
   - "Don't confuse X with Y - the key difference is..."

4. **Quick Example**: One worked example if applicable
   - Show step-by-step for calculations

5. **Memory Hook**: End with a memorable summary
   - Acronym, rhyme, or visual cue
"""

        # Combine context and task
        prompt = context + task

        # Add context about learner struggles
        if weak_concepts:
            prompt += f"\n## Learner Struggles With:\n- " + "\n- ".join(weak_concepts)

        if error_patterns:
            prompt += f"\n## Error Patterns Observed:\n- " + "\n- ".join(error_patterns)

        prompt += """

## Format
Start with a clear title, then use markdown formatting.
Keep it focused and actionable - this is for review before practice.
"""

        return prompt

    def _parse_response(self, response: str, default_title: str) -> tuple[str, str]:
        """Parse LLM response to extract title and content."""
        lines = response.strip().split("\n")

        # Look for title (first line starting with # or ##)
        title = default_title
        content_start = 0

        for i, line in enumerate(lines):
            if line.startswith("#"):
                title = line.lstrip("#").strip()
                content_start = i + 1
                break

        content = "\n".join(lines[content_start:]).strip()

        return title, content


def get_qualified_notes(
    section_ids: list[str] | None = None,
    module_number: int | None = None,
    unread_only: bool = False,
    db_session: Session | None = None,
) -> list[dict]:
    """
    Get qualified remediation notes.

    Args:
        section_ids: Filter by specific sections
        module_number: Filter by module
        unread_only: Only return notes that haven't been read
        db_session: Database session

    Returns:
        List of note dictionaries
    """
    session = db_session or next(get_session())

    query = """
        SELECT
            id, section_id, module_number, title, content,
            read_count, user_rating, qualified, is_stale,
            created_at, last_read_at
        FROM remediation_notes
        WHERE qualified = TRUE AND is_stale = FALSE
    """
    params = {}

    if section_ids:
        query += " AND section_id = ANY(:section_ids)"
        params["section_ids"] = section_ids

    if module_number:
        query += " AND module_number = :module_number"
        params["module_number"] = module_number

    if unread_only:
        query += " AND (read_count = 0 OR last_read_at IS NULL)"

    query += " ORDER BY module_number, section_id"

    result = session.execute(text(query), params)

    return [dict(row._mapping) for row in result.fetchall()]


def get_sections_needing_notes(
    min_errors: int = 2,
    db_session: Session | None = None,
) -> list[dict]:
    """
    Get sections that need remediation notes.

    Args:
        min_errors: Minimum number of errors/dont_knows to trigger
        db_session: Database session

    Returns:
        List of section dictionaries with error stats
    """
    session = db_session or next(get_session())

    result = session.execute(
        text("""
            SELECT
                la.ccna_section_id as section_id,
                cs.module_number,
                cs.title as section_title,
                COUNT(*) as total_atoms,
                SUM(COALESCE(la.anki_lapses, 0)) as total_lapses,
                SUM(COALESCE(la.dont_know_count, 0)) as total_dont_knows,
                rn.id as existing_note_id,
                rn.qualified as note_qualified
            FROM learning_atoms la
            JOIN ccna_sections cs ON la.ccna_section_id = cs.section_id
            LEFT JOIN remediation_notes rn ON la.ccna_section_id = rn.section_id
            WHERE la.ccna_section_id IS NOT NULL
            GROUP BY la.ccna_section_id, cs.module_number, cs.title, rn.id, rn.qualified
            HAVING SUM(COALESCE(la.anki_lapses, 0)) + SUM(COALESCE(la.dont_know_count, 0)) >= :min_errors
            ORDER BY SUM(COALESCE(la.anki_lapses, 0)) + SUM(COALESCE(la.dont_know_count, 0)) DESC
        """),
        {"min_errors": min_errors}
    )

    return [dict(row._mapping) for row in result.fetchall()]


def mark_note_read(
    note_id: str,
    rating: int | None = None,
    db_session: Session | None = None,
) -> None:
    """
    Mark a note as read and optionally rate it.

    Args:
        note_id: Note UUID
        rating: Optional 1-5 rating
        db_session: Database session
    """
    session = db_session or next(get_session())

    # Update note
    session.execute(
        text("""
            UPDATE remediation_notes SET
                read_count = read_count + 1,
                last_read_at = NOW(),
                user_rating = COALESCE(:rating, user_rating)
            WHERE id = CAST(:note_id AS uuid)
        """),
        {"note_id": note_id, "rating": rating}
    )

    # Record in history
    session.execute(
        text("""
            INSERT INTO note_read_history (note_id, rating)
            VALUES (CAST(:note_id AS uuid), :rating)
        """),
        {"note_id": note_id, "rating": rating}
    )

    session.commit()


def compute_section_error_rate(
    section_id: str,
    db_session: Session | None = None,
) -> float:
    """
    Compute current error rate for a section.

    Args:
        section_id: Section identifier
        db_session: Database session

    Returns:
        Error rate as float (0.0-1.0)
    """
    session = db_session or next(get_session())

    result = session.execute(
        text("""
            SELECT
                COUNT(*) as total,
                SUM(COALESCE(anki_lapses, 0) + COALESCE(dont_know_count, 0)) as errors
            FROM learning_atoms
            WHERE ccna_section_id = :section_id
        """),
        {"section_id": section_id}
    ).fetchone()

    if not result or not result.total:
        return 0.0

    total = result.total or 1
    errors = result.errors or 0

    return min(errors / total, 1.0)


def update_note_effectiveness(
    note_id: str,
    db_session: Session | None = None,
) -> dict:
    """
    Update note effectiveness based on pre/post error rates.

    Should be called periodically (e.g., after sessions) to track
    whether reading the note improved performance.

    Args:
        note_id: Note UUID
        db_session: Database session

    Returns:
        Dict with effectiveness metrics
    """
    session = db_session or next(get_session())

    # Get note and section info
    note_row = session.execute(
        text("SELECT section_id, pre_error_rate FROM remediation_notes WHERE id = CAST(:note_id AS uuid)"),
        {"note_id": note_id}
    ).fetchone()

    if not note_row:
        return {"error": "Note not found"}

    section_id = note_row.section_id
    pre_rate = note_row.pre_error_rate

    # Compute current error rate
    post_rate = compute_section_error_rate(section_id, session)

    # If no pre_rate, this is first measurement - set it
    if pre_rate is None:
        session.execute(
            text("""
                UPDATE remediation_notes
                SET pre_error_rate = :pre_rate
                WHERE id = CAST(:note_id AS uuid)
            """),
            {"note_id": note_id, "pre_rate": post_rate}
        )
        session.commit()
        return {"pre_error_rate": post_rate, "post_error_rate": None, "improvement": None}

    # Update post rate
    session.execute(
        text("""
            UPDATE remediation_notes
            SET post_error_rate = :post_rate
            WHERE id = CAST(:note_id AS uuid)
        """),
        {"note_id": note_id, "post_rate": post_rate}
    )
    session.commit()

    # Calculate improvement
    improvement = pre_rate - post_rate if pre_rate > 0 else 0.0

    return {
        "pre_error_rate": float(pre_rate),
        "post_error_rate": post_rate,
        "improvement": improvement,
        "improved": improvement > 0,
    }


def evaluate_note_quality(
    note_id: str,
    min_reads: int = 2,
    db_session: Session | None = None,
) -> dict:
    """
    Evaluate note quality based on multiple signals.

    Signals:
    - User rating (1-5)
    - Error rate improvement
    - Read count

    Args:
        note_id: Note UUID
        min_reads: Minimum reads before evaluation
        db_session: Database session

    Returns:
        Quality assessment dict
    """
    session = db_session or next(get_session())

    note_row = session.execute(
        text("""
            SELECT
                id, section_id, read_count, user_rating,
                pre_error_rate, post_error_rate, qualified
            FROM remediation_notes
            WHERE id = CAST(:note_id AS uuid)
        """),
        {"note_id": note_id}
    ).fetchone()

    if not note_row:
        return {"error": "Note not found"}

    # Not enough data yet
    if note_row.read_count < min_reads:
        return {
            "qualified": True,  # Give benefit of doubt
            "reason": "Not enough reads yet",
            "read_count": note_row.read_count,
        }

    # Compute quality score (0-100)
    score = 50  # Base score

    # Rating contribution (0-30)
    if note_row.user_rating:
        score += (note_row.user_rating - 3) * 10  # +/- 20 based on rating

    # Improvement contribution (0-20)
    if note_row.pre_error_rate and note_row.post_error_rate:
        improvement = float(note_row.pre_error_rate) - float(note_row.post_error_rate)
        if improvement > 0.1:
            score += 20
        elif improvement > 0:
            score += 10
        elif improvement < -0.1:
            score -= 20

    # Determine if qualified
    qualified = score >= 40

    # Update qualified status
    session.execute(
        text("""
            UPDATE remediation_notes
            SET qualified = :qualified
            WHERE id = CAST(:note_id AS uuid)
        """),
        {"note_id": note_id, "qualified": qualified}
    )
    session.commit()

    return {
        "qualified": qualified,
        "score": score,
        "read_count": note_row.read_count,
        "user_rating": note_row.user_rating,
        "improvement": (
            float(note_row.pre_error_rate) - float(note_row.post_error_rate)
            if note_row.pre_error_rate and note_row.post_error_rate
            else None
        ),
    }


def get_note_quality_report(
    db_session: Session | None = None,
) -> list[dict]:
    """
    Get quality report for all notes.

    Returns:
        List of note quality assessments
    """
    session = db_session or next(get_session())

    result = session.execute(
        text("""
            SELECT
                id, section_id, title, read_count, user_rating,
                pre_error_rate, post_error_rate, qualified,
                created_at, last_read_at
            FROM remediation_notes
            WHERE read_count > 0
            ORDER BY
                qualified DESC,
                user_rating DESC NULLS LAST,
                read_count DESC
        """)
    )

    report = []
    for row in result.fetchall():
        improvement = None
        if row.pre_error_rate and row.post_error_rate:
            improvement = float(row.pre_error_rate) - float(row.post_error_rate)

        report.append({
            "id": str(row.id),
            "section_id": row.section_id,
            "title": row.title,
            "read_count": row.read_count,
            "user_rating": row.user_rating,
            "improvement": improvement,
            "qualified": row.qualified,
            "last_read_at": row.last_read_at,
        })

    return report
