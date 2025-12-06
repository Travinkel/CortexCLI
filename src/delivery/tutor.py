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
from typing import Optional

from loguru import logger

from .atom_deck import Atom


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
        api_key: Optional[str] = None,
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
        if atom.quality_score < self.QUALITY_THRESHOLD:
            return False

        return True

    def generate_guidance(self, atom: Atom) -> Optional[str]:
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

def get_socratic_guidance(atom: Atom) -> Optional[str]:
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
