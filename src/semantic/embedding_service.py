"""
Embedding Service - Generate semantic embeddings using sentence-transformers.

Uses all-MiniLM-L6-v2 model (384 dimensions) for efficient similarity search.
This model provides a good balance between quality and speed, with embeddings
optimized for semantic similarity tasks.

References:
- https://www.sbert.net/docs/pretrained_models.html
- https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
from loguru import logger
from sentence_transformers import SentenceTransformer

from config import get_settings


@dataclass
class EmbeddingResult:
    """Result of embedding generation for a single text."""

    text: str
    embedding: np.ndarray
    model_name: str
    generated_at: datetime

    def to_list(self) -> list[float]:
        """Convert embedding to list for database storage."""
        return self.embedding.tolist()

    def to_bytes(self) -> bytes:
        """Convert embedding to bytes for BYTEA database storage."""
        return self.embedding.astype(np.float32).tobytes()

    @staticmethod
    def from_bytes(data: bytes) -> np.ndarray:
        """Deserialize embedding from BYTEA database storage."""
        return np.frombuffer(data, dtype=np.float32)

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        return len(self.embedding)


class EmbeddingService:
    """
    Generate semantic embeddings for flashcard content.

    Uses all-MiniLM-L6-v2 model which produces 384-dimensional embeddings.
    The model is lazy-loaded on first use to avoid startup delays.

    Example:
        >>> service = EmbeddingService()
        >>> result = service.generate_embedding("What is TCP?")
        >>> print(result.embedding.shape)  # (384,)
        >>> print(result.to_list()[:5])  # First 5 values
    """

    def __init__(self, model_name: str | None = None):
        """
        Initialize the embedding service.

        Args:
            model_name: Sentence transformer model to use.
                        Defaults to config value (all-MiniLM-L6-v2).
        """
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self.expected_dimension = settings.embedding_dimension
        self.batch_size = settings.embedding_batch_size
        self.show_progress = settings.embedding_show_progress
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        """
        Lazy load the model on first use.

        The model is downloaded from HuggingFace Hub on first run (~90MB).
        Subsequent runs use the cached version.
        """
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            logger.info(
                f"Embedding model loaded: {self.model_name} ({self.expected_dimension}-dim)"
            )
        return self._model

    def generate_embedding(self, text: str) -> EmbeddingResult:
        """
        Generate embedding for a single text.

        Args:
            text: The text to generate an embedding for.

        Returns:
            EmbeddingResult containing the embedding vector and metadata.
        """
        embedding = self.model.encode(text, convert_to_numpy=True)

        return EmbeddingResult(
            text=text,
            embedding=embedding,
            model_name=self.model_name,
            generated_at=datetime.utcnow(),
        )

    def generate_embeddings_batch(
        self,
        texts: list[str],
        batch_size: int | None = None,
        show_progress: bool | None = None,
    ) -> list[EmbeddingResult]:
        """
        Generate embeddings for multiple texts efficiently.

        Uses batched processing for better GPU/CPU utilization.

        Args:
            texts: List of texts to generate embeddings for.
            batch_size: Override default batch size.
            show_progress: Override default progress bar setting.

        Returns:
            List of EmbeddingResult objects.
        """
        if not texts:
            return []

        batch_size = batch_size or self.batch_size
        show_progress = show_progress if show_progress is not None else self.show_progress

        logger.info(f"Generating embeddings for {len(texts)} texts (batch_size={batch_size})")

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
        )

        now = datetime.utcnow()
        return [
            EmbeddingResult(
                text=text,
                embedding=emb,
                model_name=self.model_name,
                generated_at=now,
            )
            for text, emb in zip(texts, embeddings)
        ]

    def combine_front_back(self, front: str, back: str, separator: str = " [SEP] ") -> str:
        """
        Combine front and back text for embedding generation.

        The [SEP] token helps the model understand the text has two parts.

        Args:
            front: Question/prompt text.
            back: Answer text.
            separator: Separator between front and back.

        Returns:
            Combined text string.
        """
        front = front.strip() if front else ""
        back = back.strip() if back else ""

        if not front and not back:
            return ""
        if not back:
            return front
        if not front:
            return back

        return f"{front}{separator}{back}"

    @staticmethod
    def cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            emb1: First embedding vector.
            emb2: Second embedding vector.

        Returns:
            Cosine similarity score between -1 and 1.
            Higher values indicate more similar texts.
        """
        dot_product = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    @staticmethod
    def cosine_distance(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Calculate cosine distance between two embeddings.

        Args:
            emb1: First embedding vector.
            emb2: Second embedding vector.

        Returns:
            Cosine distance (1 - similarity), between 0 and 2.
            Lower values indicate more similar texts.
        """
        return 1.0 - EmbeddingService.cosine_similarity(emb1, emb2)

    def preload_model(self) -> None:
        """
        Preload the model into memory.

        Call this during application startup to avoid latency on first request.
        """
        _ = self.model
        logger.info("Embedding model preloaded")

    def get_model_info(self) -> dict:
        """
        Get information about the loaded model.

        Returns:
            Dictionary with model name, dimension, and load status.
        """
        return {
            "model_name": self.model_name,
            "dimension": self.expected_dimension,
            "is_loaded": self._model is not None,
            "batch_size": self.batch_size,
        }
