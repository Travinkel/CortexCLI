"""
Prerequisite Inference Service - Infer missing prerequisites using embeddings.

Uses embedding similarity to suggest prerequisite relationships between
atoms and concepts. Confidence levels are based on similarity thresholds.

Thresholds:
- High confidence: similarity > 0.85
- Medium confidence: similarity > 0.75
- Low confidence: similarity > 0.70
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import get_settings
from src.semantic.embedding_service import EmbeddingService


@dataclass
class PrerequisiteSuggestion:
    """A suggested prerequisite relationship."""

    source_atom_id: UUID
    target_concept_id: UUID
    concept_name: str
    concept_definition: str | None
    similarity_score: float
    confidence: str  # low, medium, high

    @property
    def is_strong_suggestion(self) -> bool:
        """Check if this is a high-confidence suggestion."""
        return self.confidence == "high"


class PrerequisiteInferenceService:
    """
    Infer missing prerequisite relationships using semantic similarity.

    Strategy:
    1. For each atom, find semantically similar concepts
    2. Concepts with similarity > threshold are suggested as prerequisites
    3. Confidence levels help prioritize suggestions for review

    Example:
        >>> service = PrerequisiteInferenceService(db_session)
        >>> suggestions = service.infer_prerequisites_for_atom(atom_id)
        >>> for s in suggestions:
        ...     print(f"Atom needs '{s.concept_name}' ({s.confidence})")
    """

    def __init__(
        self,
        db_session: Session,
        embedding_service: EmbeddingService | None = None,
    ):
        """
        Initialize the prerequisite inference service.

        Args:
            db_session: SQLAlchemy database session.
            embedding_service: Optional embedding service for generating new embeddings.
        """
        self.db = db_session
        self.embedding_service = embedding_service or EmbeddingService()
        self.settings = get_settings()

        # Load thresholds from config
        self.base_threshold = self.settings.prerequisite_similarity_threshold
        self.high_confidence = self.settings.prerequisite_high_confidence
        self.medium_confidence = self.settings.prerequisite_medium_confidence

    def _get_confidence_level(self, similarity: float) -> str:
        """
        Determine confidence level based on similarity score.

        Args:
            similarity: Cosine similarity score (0-1).

        Returns:
            Confidence level: 'high', 'medium', or 'low'.
        """
        if similarity >= self.high_confidence:
            return "high"
        elif similarity >= self.medium_confidence:
            return "medium"
        else:
            return "low"

    def infer_prerequisites_for_atom(
        self,
        atom_id: UUID,
        threshold: float | None = None,
        limit: int = 5,
        exclude_current_concept: bool = True,
    ) -> list[PrerequisiteSuggestion]:
        """
        Infer prerequisite concepts for a specific atom.

        Compares atom embedding to concept definition embeddings.

        Args:
            atom_id: UUID of the atom to find prerequisites for.
            threshold: Minimum similarity threshold (default from config).
            limit: Maximum number of suggestions.
            exclude_current_concept: Exclude the atom's current concept from suggestions.

        Returns:
            List of PrerequisiteSuggestion objects sorted by similarity.
        """
        threshold = threshold or self.base_threshold

        # Build exclusion clause
        exclude_clause = ""
        if exclude_current_concept:
            exclude_clause = "AND c.id != COALESCE((SELECT concept_id FROM learning_atoms WHERE id = :atom_id::uuid), '00000000-0000-0000-0000-000000000000'::uuid)"

        query = text(f"""
            SELECT
                c.id as concept_id,
                c.name as concept_name,
                c.definition as concept_definition,
                1 - (c.embedding <=> (SELECT embedding FROM learning_atoms WHERE id = :atom_id::uuid)) as similarity
            FROM concepts c
            WHERE c.embedding IS NOT NULL
              {exclude_clause}
              AND 1 - (c.embedding <=> (SELECT embedding FROM learning_atoms WHERE id = :atom_id::uuid)) > :threshold
            ORDER BY similarity DESC
            LIMIT :limit
        """)

        results = self.db.execute(
            query,
            {"atom_id": str(atom_id), "threshold": threshold, "limit": limit},
        ).fetchall()

        suggestions = []
        for row in results:
            similarity = float(row.similarity)
            suggestions.append(
                PrerequisiteSuggestion(
                    source_atom_id=atom_id,
                    target_concept_id=row.concept_id,
                    concept_name=row.concept_name,
                    concept_definition=row.concept_definition,
                    similarity_score=similarity,
                    confidence=self._get_confidence_level(similarity),
                )
            )

        return suggestions

    def infer_all_missing_prerequisites(
        self,
        batch_size: int = 100,
        threshold: float | None = None,
        max_suggestions_per_atom: int = 3,
    ) -> int:
        """
        Infer prerequisites for all atoms that don't have explicit prerequisites.

        Processes atoms in batches and stores suggestions in the database.

        Args:
            batch_size: Number of atoms to process per batch.
            threshold: Minimum similarity threshold.
            max_suggestions_per_atom: Maximum suggestions per atom.

        Returns:
            Total count of suggestions generated.
        """
        threshold = threshold or self.base_threshold
        logger.info(f"Starting bulk prerequisite inference (threshold={threshold})")

        # Find atoms without prerequisites
        atoms_query = text("""
            SELECT id, front, back
            FROM learning_atoms
            WHERE embedding IS NOT NULL
              AND concept_id IS NULL
              AND id NOT IN (
                  SELECT DISTINCT source_atom_id
                  FROM inferred_prerequisites
                  WHERE status != 'rejected'
              )
            LIMIT :batch_size
        """)

        atoms = self.db.execute(atoms_query, {"batch_size": batch_size}).fetchall()

        total_suggestions = 0
        for atom in atoms:
            suggestions = self.infer_prerequisites_for_atom(
                atom_id=atom.id,
                threshold=threshold,
                limit=max_suggestions_per_atom,
            )
            if suggestions:
                self._store_suggestions(suggestions)
                total_suggestions += len(suggestions)

        logger.info(f"Generated {total_suggestions} prerequisite suggestions")
        return total_suggestions

    def _store_suggestions(self, suggestions: list[PrerequisiteSuggestion]) -> None:
        """
        Store prerequisite suggestions in database.

        Uses ON CONFLICT DO NOTHING to avoid duplicates.

        Args:
            suggestions: List of PrerequisiteSuggestion objects.
        """
        insert_query = text("""
            INSERT INTO inferred_prerequisites
            (source_atom_id, target_concept_id, similarity_score, confidence, inference_method)
            VALUES (:source_atom_id, :target_concept_id, :similarity_score, :confidence, 'embedding')
            ON CONFLICT (source_atom_id, target_concept_id) DO UPDATE
            SET similarity_score = EXCLUDED.similarity_score,
                confidence = EXCLUDED.confidence,
                updated_at = now()
        """)

        for suggestion in suggestions:
            self.db.execute(
                insert_query,
                {
                    "source_atom_id": str(suggestion.source_atom_id),
                    "target_concept_id": str(suggestion.target_concept_id),
                    "similarity_score": suggestion.similarity_score,
                    "confidence": suggestion.confidence,
                },
            )

        self.db.commit()

    def get_suggestions_for_review(
        self,
        min_confidence: str = "medium",
        limit: int = 50,
    ) -> list[PrerequisiteSuggestion]:
        """
        Get pending prerequisite suggestions for manual review.

        Args:
            min_confidence: Minimum confidence level to include.
            limit: Maximum number of suggestions to return.

        Returns:
            List of PrerequisiteSuggestion objects.
        """
        # Map confidence to numeric for filtering
        confidence_order = {"low": 1, "medium": 2, "high": 3}
        confidence_order.get(min_confidence, 2)

        confidence_filter = ""
        if min_confidence == "medium":
            confidence_filter = "AND ip.confidence IN ('medium', 'high')"
        elif min_confidence == "high":
            confidence_filter = "AND ip.confidence = 'high'"

        query = text(f"""
            SELECT
                ip.source_atom_id,
                ip.target_concept_id,
                ip.similarity_score,
                ip.confidence,
                c.name as concept_name,
                c.definition as concept_definition
            FROM inferred_prerequisites ip
            JOIN concepts c ON ip.target_concept_id = c.id
            WHERE ip.status = 'suggested'
              {confidence_filter}
            ORDER BY
                CASE ip.confidence
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                END,
                ip.similarity_score DESC
            LIMIT :limit
        """)

        results = self.db.execute(query, {"limit": limit}).fetchall()

        return [
            PrerequisiteSuggestion(
                source_atom_id=row.source_atom_id,
                target_concept_id=row.target_concept_id,
                concept_name=row.concept_name,
                concept_definition=row.concept_definition,
                similarity_score=float(row.similarity_score),
                confidence=row.confidence,
            )
            for row in results
        ]

    def accept_suggestion(self, atom_id: UUID, concept_id: UUID) -> bool:
        """
        Accept a prerequisite suggestion and apply it.

        Updates the inferred_prerequisites status and sets the atom's concept_id.

        Args:
            atom_id: UUID of the source atom.
            concept_id: UUID of the target concept.

        Returns:
            True if updated, False if not found.
        """
        # Update suggestion status
        update_query = text("""
            UPDATE inferred_prerequisites
            SET status = 'accepted',
                reviewed_at = now()
            WHERE source_atom_id = :atom_id
              AND target_concept_id = :concept_id
        """)

        result = self.db.execute(
            update_query,
            {"atom_id": str(atom_id), "concept_id": str(concept_id)},
        )

        if result.rowcount == 0:
            return False

        # Optionally update the atom's concept_id
        # This could also be done separately in a different workflow
        self.db.commit()
        return True

    def reject_suggestion(
        self,
        atom_id: UUID,
        concept_id: UUID,
        notes: str | None = None,
    ) -> bool:
        """
        Reject a prerequisite suggestion.

        Args:
            atom_id: UUID of the source atom.
            concept_id: UUID of the target concept.
            notes: Optional notes about why this was rejected.

        Returns:
            True if updated, False if not found.
        """
        query = text("""
            UPDATE inferred_prerequisites
            SET status = 'rejected',
                reviewed_at = now(),
                review_notes = :notes
            WHERE source_atom_id = :atom_id
              AND target_concept_id = :concept_id
        """)

        result = self.db.execute(
            query,
            {
                "atom_id": str(atom_id),
                "concept_id": str(concept_id),
                "notes": notes,
            },
        )
        self.db.commit()

        return result.rowcount > 0

    def get_suggestion_stats(self) -> dict:
        """
        Get statistics about prerequisite suggestions.

        Returns:
            Dictionary with suggestion counts by status and confidence.
        """
        query = text("""
            SELECT
                status,
                confidence,
                COUNT(*) as count
            FROM inferred_prerequisites
            GROUP BY status, confidence
        """)

        results = self.db.execute(query).fetchall()

        stats = {
            "total": 0,
            "by_status": {},
            "by_confidence": {"high": 0, "medium": 0, "low": 0},
        }

        for row in results:
            # By status
            if row.status not in stats["by_status"]:
                stats["by_status"][row.status] = 0
            stats["by_status"][row.status] += row.count

            # By confidence (for suggested only)
            if row.status == "suggested":
                stats["by_confidence"][row.confidence] += row.count

            stats["total"] += row.count

        return stats
