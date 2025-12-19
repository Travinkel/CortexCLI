"""
Contrastive Learning Data Fetcher.

Fetches and formats concept data for side-by-side comparisons
when discrimination errors are detected.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text

from src.db.database import get_session


class ContrastiveDataFetcher:
    """
    Fetches concept details for side-by-side comparison.

    Used when the NCDE detects discrimination errors (confusing similar concepts).
    Retrieves definitions, key facts, and examples for both concepts.
    """

    def fetch_pair(
        self,
        concept_a_id: str,
        concept_b_id: str,
    ) -> tuple[dict, dict, str | None]:
        """
        Fetch contrastive data for two concepts.

        Args:
            concept_a_id: First concept ID (usually the correct one)
            concept_b_id: Second concept ID (the confused one)

        Returns:
            Tuple of (concept_a_dict, concept_b_dict, confusion_evidence)
            Each dict has: name, definition, key_facts (list), example
        """
        concept_a = self._fetch_concept(concept_a_id)
        concept_b = self._fetch_concept(concept_b_id)

        # Generate confusion evidence if we have both concepts
        evidence = None
        if concept_a.get("name") and concept_b.get("name"):
            evidence = self._generate_confusion_evidence(concept_a, concept_b)

        return concept_a, concept_b, evidence

    def _fetch_concept(self, concept_id: str) -> dict:
        """Fetch concept details from the database."""
        try:
            with next(get_session()) as session:
                # Try concepts table first
                result = session.execute(text("""
                    SELECT name, definition
                    FROM concepts
                    WHERE id = :id
                """), {"id": concept_id}).fetchone()

                if result:
                    return self._build_concept_dict(
                        concept_id,
                        result[0],  # name
                        result[1],  # definition
                    )

                # Fallback: try learning_atoms table
                result = session.execute(text("""
                    SELECT front, back
                    FROM learning_atoms
                    WHERE id = :id
                """), {"id": concept_id}).fetchone()

                if result:
                    return self._build_concept_dict_from_atom(
                        concept_id,
                        result[0],  # front
                        result[1],  # back
                    )

        except Exception:
            pass

        # Return placeholder if not found
        return {
            "name": f"Concept {concept_id[:8]}...",
            "definition": "Definition not available",
            "key_facts": [],
            "example": "",
        }

    def _build_concept_dict(
        self,
        concept_id: str,
        name: str,
        definition: str | None,
    ) -> dict:
        """Build concept dict from concepts table data."""
        # Extract key facts from definition
        key_facts = self._extract_key_facts(definition or "")

        return {
            "name": name or f"Concept {concept_id[:8]}",
            "definition": definition or "No definition available",
            "key_facts": key_facts,
            "example": "",  # Could be enhanced with examples table
        }

    def _build_concept_dict_from_atom(
        self,
        concept_id: str,
        front: str,
        back: str | None,
    ) -> dict:
        """Build concept dict from learning_atoms data."""
        import json

        # Try to parse JSON back
        definition = back or ""
        if back and back.strip().startswith("{"):
            try:
                data = json.loads(back)
                definition = data.get("explanation", back)
            except json.JSONDecodeError:
                pass

        # Extract concept name from front (usually the question/prompt)
        name = self._extract_concept_name(front)
        key_facts = self._extract_key_facts(definition)

        return {
            "name": name,
            "definition": definition[:200] if definition else "No definition",
            "key_facts": key_facts,
            "example": "",
        }

    def _extract_concept_name(self, front: str) -> str:
        """Extract a concept name from atom front text."""
        if not front:
            return "Unknown Concept"

        # Try to extract key terms (usually in quotes or bold)
        import re

        # Look for quoted terms
        quotes = re.findall(r'"([^"]+)"', front)
        if quotes:
            return quotes[0]

        # Look for terms in asterisks (markdown bold)
        bold = re.findall(r'\*\*([^*]+)\*\*', front)
        if bold:
            return bold[0]

        # Take first sentence or first 50 chars
        first_sentence = front.split('.')[0].split('?')[0]
        return first_sentence[:50] if len(first_sentence) > 50 else first_sentence

    def _extract_key_facts(self, text: str) -> list[str]:
        """Extract key facts/bullet points from text."""
        facts = []

        if not text:
            return facts

        # Look for bullet points
        import re

        bullets = re.findall(r'[-•*]\s*(.+?)(?:\n|$)', text)
        facts.extend(bullets[:4])  # Max 4 facts

        # If no bullets, try sentences
        if not facts:
            sentences = text.split('.')
            facts = [s.strip() for s in sentences[:3] if s.strip() and len(s.strip()) > 10]

        return facts[:4]

    def _generate_confusion_evidence(self, concept_a: dict, concept_b: dict) -> str:
        """Generate explanation of why concepts might be confused."""
        name_a = concept_a.get("name", "")
        name_b = concept_b.get("name", "")

        # Check for similar names
        if name_a and name_b:
            # Simple similarity check
            words_a = set(name_a.lower().split())
            words_b = set(name_b.lower().split())
            common = words_a & words_b

            if common:
                return f"Both involve: {', '.join(common)}"

        return "These concepts share similar characteristics or contexts"


# Module-level instance for convenience
_fetcher: ContrastiveDataFetcher | None = None


def get_contrastive_data(concept_a_id: str, concept_b_id: str) -> tuple[dict, dict, str | None]:
    """
    Convenience function to get contrastive data.

    Returns:
        Tuple of (concept_a_dict, concept_b_dict, confusion_evidence)
    """
    global _fetcher
    if _fetcher is None:
        _fetcher = ContrastiveDataFetcher()

    return _fetcher.fetch_pair(concept_a_id, concept_b_id)
