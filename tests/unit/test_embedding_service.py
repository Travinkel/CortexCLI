"""
Unit tests for the Embedding Service.

Tests embedding generation, similarity calculation, and batch processing.
"""
import numpy as np
import pytest

from src.semantic.embedding_service import EmbeddingService, EmbeddingResult


class TestEmbeddingService:
    """Tests for EmbeddingService class."""

    @pytest.fixture
    def service(self):
        """Create embedding service instance."""
        return EmbeddingService()

    def test_generate_embedding_returns_correct_dimension(self, service):
        """Embedding should be 384-dimensional for all-MiniLM-L6-v2."""
        result = service.generate_embedding("What is TCP?")

        assert isinstance(result, EmbeddingResult)
        assert result.embedding.shape == (384,)
        assert result.dimension == 384
        assert result.model_name == "all-MiniLM-L6-v2"

    def test_similar_texts_have_high_similarity(self, service):
        """Semantically similar texts should have high cosine similarity."""
        emb1 = service.generate_embedding("What is TCP?").embedding
        emb2 = service.generate_embedding("What is the TCP protocol?").embedding

        similarity = EmbeddingService.cosine_similarity(emb1, emb2)

        assert similarity > 0.8  # Should be very similar

    def test_different_texts_have_lower_similarity(self, service):
        """Unrelated texts should have lower similarity."""
        emb1 = service.generate_embedding("What is TCP?").embedding
        emb2 = service.generate_embedding("How do cats purr?").embedding

        similarity = EmbeddingService.cosine_similarity(emb1, emb2)

        assert similarity < 0.5  # Should be dissimilar

    def test_batch_embedding_produces_multiple_results(self, service):
        """Batch processing should return embedding for each input."""
        texts = ["What is TCP?", "How does HTTP work?", "What is a socket?"]

        results = service.generate_embeddings_batch(texts, show_progress=False)

        assert len(results) == 3
        for result in results:
            assert result.embedding.shape == (384,)

    def test_batch_embedding_matches_single(self, service):
        """Batch and single embeddings should be identical for same text."""
        texts = ["What is TCP?", "How does HTTP work?"]

        batch_results = service.generate_embeddings_batch(texts, show_progress=False)
        single_results = [service.generate_embedding(t) for t in texts]

        for batch, single in zip(batch_results, single_results):
            np.testing.assert_array_almost_equal(batch.embedding, single.embedding)

    def test_combine_front_back_with_both(self, service):
        """Combining front and back should use separator."""
        combined = service.combine_front_back("What is TCP?", "Transmission Control Protocol")

        assert "What is TCP?" in combined
        assert "Transmission Control Protocol" in combined
        assert "[SEP]" in combined

    def test_combine_front_back_front_only(self, service):
        """If only front provided, return just front."""
        combined = service.combine_front_back("What is TCP?", "")

        assert combined == "What is TCP?"
        assert "[SEP]" not in combined

    def test_combine_front_back_back_only(self, service):
        """If only back provided, return just back."""
        combined = service.combine_front_back("", "TCP is a protocol")

        assert combined == "TCP is a protocol"
        assert "[SEP]" not in combined

    def test_combine_front_back_both_empty(self, service):
        """If both empty, return empty string."""
        combined = service.combine_front_back("", "")

        assert combined == ""

    def test_cosine_similarity_identical_vectors(self):
        """Identical vectors should have similarity of 1.0."""
        vec = np.array([1.0, 2.0, 3.0])

        similarity = EmbeddingService.cosine_similarity(vec, vec)

        assert similarity == pytest.approx(1.0)

    def test_cosine_similarity_opposite_vectors(self):
        """Opposite vectors should have similarity of -1.0."""
        vec1 = np.array([1.0, 2.0, 3.0])
        vec2 = np.array([-1.0, -2.0, -3.0])

        similarity = EmbeddingService.cosine_similarity(vec1, vec2)

        assert similarity == pytest.approx(-1.0)

    def test_cosine_distance_identical_vectors(self):
        """Identical vectors should have distance of 0.0."""
        vec = np.array([1.0, 2.0, 3.0])

        distance = EmbeddingService.cosine_distance(vec, vec)

        assert distance == pytest.approx(0.0)

    def test_embedding_result_to_list(self, service):
        """EmbeddingResult.to_list() should return a Python list."""
        result = service.generate_embedding("Test")

        as_list = result.to_list()

        assert isinstance(as_list, list)
        assert len(as_list) == 384
        assert all(isinstance(x, float) for x in as_list)

    def test_get_model_info(self, service):
        """Model info should contain expected keys."""
        info = service.get_model_info()

        assert "model_name" in info
        assert "dimension" in info
        assert "is_loaded" in info
        assert info["model_name"] == "all-MiniLM-L6-v2"
        assert info["dimension"] == 384

    def test_empty_text_handling(self, service):
        """Empty text should still produce an embedding."""
        result = service.generate_embedding("")

        assert result.embedding.shape == (384,)

    def test_long_text_handling(self, service):
        """Long text should be handled (may be truncated by model)."""
        long_text = "This is a test. " * 1000  # Very long text

        result = service.generate_embedding(long_text)

        assert result.embedding.shape == (384,)


class TestEmbeddingResultDataclass:
    """Tests for EmbeddingResult dataclass."""

    def test_embedding_result_attributes(self):
        """EmbeddingResult should have expected attributes."""
        from datetime import datetime

        result = EmbeddingResult(
            text="test",
            embedding=np.zeros(384),
            model_name="test-model",
            generated_at=datetime.utcnow(),
        )

        assert result.text == "test"
        assert result.model_name == "test-model"
        assert result.dimension == 384

    def test_embedding_result_to_list_type(self):
        """to_list should convert numpy array to Python list."""
        result = EmbeddingResult(
            text="test",
            embedding=np.array([1.0, 2.0, 3.0]),
            model_name="test-model",
            generated_at=None,
        )

        as_list = result.to_list()

        assert as_list == [1.0, 2.0, 3.0]
