"""
Socratic Tutor: LLM-powered Learning Assistance.

Provides Socratic tutoring interventions when users struggle
with high-quality atoms. Uses guiding questions instead of
direct answers to promote deeper understanding.

Triggered when:
- Atom quality_score >= 90 (high-value content)
- User fails the card
"""

from __future__ import annotations

import os
import difflib
from types import SimpleNamespace
from typing import Iterable

from loguru import logger

from .atom_deck import Atom
from src.adaptive.pedagogy import (
    InterventionResponse,
    LearningState,
    PedagogicalEngine,
    Remediation,
)

# Lightweight proxy to connect pedagogy engine to CLI/tutor flows


class AdaptiveTutor:
    """Route learner responses through the pedagogical engine."""

    def __init__(self, deck: list[Atom] | None = None):
        self.engine = PedagogicalEngine()
        self.deck = deck or []
        self._history: dict[str, list[dict]] = {}

    def submit_response(
        self,
        atom: Atom,
        is_correct: bool,
        response_ms: int,
        grade: int | None = None,
        recent_times: list[int] | None = None,
    ) -> InterventionResponse:
        """Evaluate a learner response and return an intervention plan."""
        history = self._history.setdefault(atom.id, [])
        history.append(
            {
                "result": "correct" if is_correct else "incorrect",
                "latency": response_ms,
                "confidence": "high" if (grade or 0) >= 4 else "low",
            }
        )

        state = LearningState(
            stability=float(max(atom.difficulty, 1)),
            review_count=len(history),
            psi_index=0.0,
            visual_load=1.0
            if getattr(atom, "derived_from_visual", False)
            or getattr(atom, "media_type", "") == "mermaid"
            else 0.5,
            symbolic_load=0.5,
            recent_response_times=(recent_times or [])[-5:],
        )

        hints_available = bool(atom.hints or (atom.content_json or {}).get("hints"))
        response = self.engine.evaluate(
            event=SimpleNamespace(is_correct=is_correct, response_time_ms=response_ms),
            state=state,
            history=history,
            card_type=atom.knowledge_type,
            is_new_topic=bool(atom.module_number == 0),
            hints_available=hints_available,
        )

        # Attach a confusable/lure atom if contrastive remediation requested
        if response.remediation == Remediation.CONTRASTIVE:
            response.lure_atom = self._find_confusable_atom(atom)

        return response

    def _find_confusable_atom(self, atom: Atom) -> Atom | None:
        """Find a likely confusable atom using simple text similarity as a fallback."""
        candidates: Iterable[Atom] = (c for c in self.deck if c.id != atom.id)
        best: tuple[float, Atom | None] = (0.0, None)
        for candidate in candidates:
            ratio = difflib.SequenceMatcher(
                None, atom.front.lower(), candidate.front.lower()
            ).ratio()
            if ratio > best[0]:
                best = (ratio, candidate)
        return best[1]

# =============================================================================
# Prompts
# =============================================================================

SOCRATIC_SYSTEM_PROMPT = """You are a Socratic tutor helping a student learn CCNA networking concepts.

Your role is to guide the student toward understanding through carefully crafted questions,
NOT by providing direct answers. The student just failed a flashcard and needs help.

## Guidelines

1. **Never give the answer directly** - Instead, ask questions that lead to understanding
2. **Start simple** - Begin with foundational questions
3. **Build progressively** - Each question should build on the previous
4. **Use analogies** - Relate networking concepts to real-world examples when helpful
5. **Be encouraging** - Learning is a process, failure is normal

## Question Techniques

- **Clarifying**: "What do you already know about X?"
- **Connecting**: "How does X relate to Y that we learned earlier?"
- **Hypothetical**: "What would happen if we didn't have X?"
- **Application**: "In what situation would you use X?"
- **Comparison**: "How is X different from Y?"

## Format

Provide 2-3 Socratic questions that will guide the student toward the correct answer.
Keep each question concise (1-2 sentences).
"""

SOCRATIC_USER_TEMPLATE = """The student failed this flashcard:

**Question**: {front}

**Correct Answer**: {back}

**Source Context**: {source_fact}

**Topic Tags**: {tags}

Generate 2-3 Socratic guiding questions to help the student understand this concept.
Do NOT reveal the answer directly.
"""


# =============================================================================
# Socratic Tutor
# =============================================================================


class SocraticTutor:
    """
    Provides Socratic tutoring using Gemini API.

    When a student fails a high-quality atom, this generates
    guiding questions to help them discover the answer.
    """

    QUALITY_THRESHOLD = 90.0  # Only trigger for high-quality atoms

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-2.0-flash",
    ):
        """
        Initialize the tutor.

        Args:
            api_key: Gemini API key (uses GEMINI_API_KEY env var if not provided)
            model_name: Model to use for generation
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self._client = None

        if not self.api_key:
            logger.warning("No Gemini API key - Socratic tutor disabled")

    @property
    def is_available(self) -> bool:
        """Check if tutor is available (has API key)."""
        return self.api_key is not None

    def should_intervene(self, atom: Atom, grade: int) -> bool:
        """
        Determine if Socratic intervention is appropriate.

        Args:
            atom: The atom that was reviewed
            grade: The grade received (0-5)

        Returns:
            True if intervention should be offered
        """
        if not self.is_available:
            return False

        # Only for failed cards
        if grade >= 3:
            return False

        # Only for high-quality atoms (worth the intervention)
        return not atom.quality_score < self.QUALITY_THRESHOLD

    def generate_guidance(self, atom: Atom) -> str | None:
        """
        Generate Socratic guiding questions for an atom.

        Args:
            atom: The atom the student failed

        Returns:
            Generated questions or None if generation fails
        """
        if not self.is_available:
            logger.warning("Cannot generate guidance - no API key")
            return None

        try:
            # Lazy import to avoid dependency if not used
            import google.generativeai as genai

            if self._client is None:
                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=SOCRATIC_SYSTEM_PROMPT,
                )

            # Build context
            source_fact = atom.source_fact_basis or "Not available"
            if not source_fact and atom.source_refs:
                ref = atom.source_refs[0]
                source_fact = ref.get("source_text_excerpt", "Not available")

            prompt = SOCRATIC_USER_TEMPLATE.format(
                front=atom.front,
                back=atom.back,
                source_fact=source_fact,
                tags=", ".join(atom.tags) if atom.tags else "N/A",
            )

            # Generate
            response = self._client.generate_content(prompt)
            return response.text

        except ImportError:
            logger.error("google-generativeai not installed. Run: pip install google-generativeai")
            return None
        except Exception as e:
            logger.error(f"Socratic generation failed: {e}")
            return None

    def format_guidance(self, guidance: str) -> str:
        """
        Format guidance for terminal display.

        Args:
            guidance: Raw generated guidance

        Returns:
            Formatted string for Rich console
        """
        return f"[bold cyan]Let's think through this:[/bold cyan]\n\n{guidance}"


# =============================================================================
# Quick Access Function
# =============================================================================


def get_socratic_guidance(atom: Atom) -> str | None:
    """
    Quick access function for generating Socratic guidance.

    Args:
        atom: The atom to generate guidance for

    Returns:
        Formatted guidance or None
    """
    tutor = SocraticTutor()

    if not tutor.is_available:
        return None

    guidance = tutor.generate_guidance(atom)

    if guidance:
        return tutor.format_guidance(guidance)

    return None
