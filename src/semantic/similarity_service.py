"""
Semantic Similarity Service - Find semantically similar cards using embeddings.

Since pgvector is not available, this version performs similarity calculations
in Python using numpy. While slower than database-level operations, this provides
full functionality without the pgvector extension.

Default threshold: cosine similarity > 0.85 for duplicates.

References:
- all-MiniLM-L6-v2 embeddings: 384 dimensions
- Cosine similarity: measures angle between vectors (higher = more similar)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from uuid import UUID

import numpy as np
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import get_settings
from src.semantic.embedding_service import EmbeddingService, EmbeddingResult


@dataclass
class SimilarityMatch:
    """A pair of similar atoms with their similarity score."""

    atom_id_1: UUID
    atom_id_2: UUID
    front_1: str
    front_2: str
    similarity_score: float

    @property
    def is_duplicate(self) -> bool:
        """Check if this pair qualifies as a duplicate (>0.85 similarity)."""
        return self.similarity_score > 0.85


class SemanticSimilarityService:
    """
    Detect semantically similar cards using vector embeddings.

    Since pgvector is not installed, similarity is calculated in Python
    using numpy. This is slower for large datasets but works without
    any database extensions.

    Example:
        >>> service = SemanticSimilarityService(db_session)
        >>> duplicates = service.find_semantic_duplicates(threshold=0.85)
        >>> for dup in duplicates:
        ...     print(f"{dup.front_1} <-> {dup.front_2}: {dup.similarity_score:.2f}")
    """

    DEFAULT_DUPLICATE_THRESHOLD = 0.85

    def __init__(
        self,
        db_session: Session,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        """
        Initialize the similarity service.

        Args:
            db_session: SQLAlchemy database session.
            embedding_service: Optional embedding service for generating new embeddings.
        """
        self.db = db_session
        self.embedding_service = embedding_service or EmbeddingService()
        self.settings = get_settings()

    def _deserialize_embedding(self, data: bytes) -> np.ndarray:
        """Deserialize embedding from BYTEA storage."""
        return np.frombuffer(data, dtype=np.float32)

    def _cosine_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings."""
        dot_product = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def _load_embeddings(
        self,
        concept_id: Optional[UUID] = None,
    ) -> Dict[UUID, Tuple[str, np.ndarray]]:
        """
        Load all embeddings from database.

        Args:
            concept_id: Optional filter by concept.

        Returns:
            Dictionary mapping atom_id to (front_text, embedding).
        """
        concept_filter = ""
        params = {}

        if concept_id:
            concept_filter = "AND concept_id = :concept_id"
            params["concept_id"] = str(concept_id)

        query = text(f"""
            SELECT id, front, embedding
            FROM learning_atoms
            WHERE embedding IS NOT NULL
            {concept_filter}
        """)

        results = self.db.execute(query, params).fetchall()

        embeddings = {}
        for row in results:
            if row.embedding:
                emb = self._deserialize_embedding(row.embedding)
                embeddings[row.id] = (row.front, emb)

        logger.debug(f"Loaded {len(embeddings)} embeddings from database")
        return embeddings

    def find_semantic_duplicates(
        self,
        threshold: Optional[float] = None,
        limit: int = 100,
        concept_id: Optional[UUID] = None,
    ) -> List[SimilarityMatch]:
        """
        Find semantically similar cards above threshold.

        Computes pairwise cosine similarity in Python.

        Args:
            threshold: Minimum similarity score (default: 0.85).
            limit: Maximum number of pairs to return.
            concept_id: Optional filter to search within a concept.

        Returns:
            List of SimilarityMatch objects sorted by similarity (descending).
        """
        threshold = threshold or self.settings.semantic_duplicate_threshold

        logger.info(f"Finding semantic duplicates with threshold {threshold}")

        # Load all embeddings
        embeddings = self._load_embeddings(concept_id)

        if len(embeddings) < 2:
            logger.info("Not enough embeddings to find duplicates")
            return []

        # Compute pairwise similarities
        matches = []
        atom_ids = list(embeddings.keys())

        for i, id1 in enumerate(atom_ids):
            front1, emb1 = embeddings[id1]

            for id2 in atom_ids[i + 1:]:  # Only compare with atoms after this one
                front2, emb2 = embeddings[id2]

                similarity = self._cosine_similarity(emb1, emb2)

                if similarity > threshold:
                    matches.append(SimilarityMatch(
                        atom_id_1=id1,
                        atom_id_2=id2,
                        front_1=front1,
                        front_2=front2,
                        similarity_score=similarity,
                    ))

        # Sort by similarity descending and limit
        matches.sort(key=lambda m: m.similarity_score, reverse=True)
        matches = matches[:limit]

        logger.info(f"Found {len(matches)} semantic duplicate pairs above {threshold}")
        return matches

    def find_similar_to_atom(
        self,
        atom_id: UUID,
        threshold: float = 0.7,
        limit: int = 10,
    ) -> List[SimilarityMatch]:
        """
        Find atoms similar to a specific atom.

        Args:
            atom_id: UUID of the source atom.
            threshold: Minimum similarity score.
            limit: Maximum number of results.

        Returns:
            List of SimilarityMatch objects.
        """
        logger.debug(f"Finding atoms similar to {atom_id}")

        # Get the source atom's embedding
        query = text("""
            SELECT front, embedding
            FROM learning_atoms
            WHERE id = :atom_id
        """)

        result = self.db.execute(query, {"atom_id": str(atom_id)}).fetchone()

        if not result or not result.embedding:
            logger.warning(f"Atom {atom_id} not found or has no embedding")
            return []

        source_front = result.front
        source_emb = self._deserialize_embedding(result.embedding)

        # Load all other embeddings
        embeddings = self._load_embeddings()

        matches = []
        for other_id, (other_front, other_emb) in embeddings.items():
            if other_id == atom_id:
                continue

            similarity = self._cosine_similarity(source_emb, other_emb)

            if similarity > threshold:
                matches.append(SimilarityMatch(
                    atom_id_1=atom_id,
                    atom_id_2=other_id,
                    front_1=source_front,
                    front_2=other_front,
                    similarity_score=similarity,
                ))

        # Sort by similarity descending and limit
        matches.sort(key=lambda m: m.similarity_score, reverse=True)
        return matches[:limit]

    def find_similar_to_text(
        self,
        text: str,
        threshold: float = 0.7,
        limit: int = 10,
    ) -> List[SimilarityMatch]:
        """
        Find atoms similar to arbitrary text (not in database).

        Useful for finding related content for new cards or queries.

        Args:
            text: Text to find similar atoms for.
            threshold: Minimum similarity score.
            limit: Maximum number of results.

        Returns:
            List of SimilarityMatch objects.
        """
        # Generate embedding for the query text
        result = self.embedding_service.generate_embedding(text)
        query_emb = result.embedding

        # Load all embeddings
        embeddings = self._load_embeddings()

        matches = []
        placeholder_id = UUID("00000000-0000-0000-0000-000000000000")

        for atom_id, (front, emb) in embeddings.items():
            similarity = self._cosine_similarity(query_emb, emb)

            if similarity > threshold:
                matches.append(SimilarityMatch(
                    atom_id_1=placeholder_id,
                    atom_id_2=atom_id,
                    front_1=text,
                    front_2=front,
                    similarity_score=similarity,
                ))

        # Sort by similarity descending and limit
        matches.sort(key=lambda m: m.similarity_score, reverse=True)
        return matches[:limit]

    def store_duplicate_pairs(
        self,
        matches: List[SimilarityMatch],
        detection_method: str = "embedding",
    ) -> int:
        """
        Store detected duplicate pairs in database.

        Uses upsert to update similarity scores for existing pairs.

        Args:
            matches: List of SimilarityMatch objects to store.
            detection_method: Method used for detection (embedding, fuzzy, exact).

        Returns:
            Number of pairs stored/updated.
        """
        if not matches:
            return 0

        insert_query = text("""
            INSERT INTO semantic_duplicates (atom_id_1, atom_id_2, similarity_score, detection_method)
            VALUES (
                LEAST(:atom_id_1::uuid, :atom_id_2::uuid),
                GREATEST(:atom_id_1::uuid, :atom_id_2::uuid),
                :similarity_score,
                :detection_method
            )
            ON CONFLICT (atom_id_1, atom_id_2) DO UPDATE
            SET similarity_score = EXCLUDED.similarity_score,
                detection_method = EXCLUDED.detection_method,
                updated_at = now()
        """)

        for match in matches:
            self.db.execute(
                insert_query,
                {
                    "atom_id_1": str(match.atom_id_1),
                    "atom_id_2": str(match.atom_id_2),
                    "similarity_score": match.similarity_score,
                    "detection_method": detection_method,
                },
            )

        self.db.commit()
        logger.info(f"Stored {len(matches)} duplicate pairs")
        return len(matches)

    def get_duplicate_stats(self) -> dict:
        """
        Get statistics about detected duplicates.

        Returns:
            Dictionary with duplicate counts by status.
        """
        query = text("""
            SELECT
                status,
                COUNT(*) as count,
                AVG(similarity_score) as avg_similarity
            FROM semantic_duplicates
            GROUP BY status
        """)

        results = self.db.execute(query).fetchall()

        stats = {
            "total": 0,
            "by_status": {},
        }

        for row in results:
            stats["by_status"][row.status] = {
                "count": row.count,
                "avg_similarity": float(row.avg_similarity) if row.avg_similarity else 0,
            }
            stats["total"] += row.count

        return stats

    def dismiss_duplicate(self, duplicate_id: UUID, notes: Optional[str] = None) -> bool:
        """
        Mark a duplicate pair as dismissed (not actually duplicates).

        Args:
            duplicate_id: UUID of the semantic_duplicates record.
            notes: Optional notes about why this was dismissed.

        Returns:
            True if updated, False if not found.
        """
        query = text("""
            UPDATE semantic_duplicates
            SET status = 'dismissed',
                reviewed_at = now(),
                review_notes = :notes
            WHERE id = :duplicate_id
        """)

        result = self.db.execute(
            query,
            {"duplicate_id": str(duplicate_id), "notes": notes},
        )
        self.db.commit()

        return result.rowcount > 0
