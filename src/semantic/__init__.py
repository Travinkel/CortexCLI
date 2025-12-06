"""
Semantic analysis module for embedding-based similarity and clustering.

Phase 2.5 implementation providing:
- Semantic duplicate detection (cosine similarity > 0.85)
- Prerequisite inference using embedding similarity
- Knowledge state clustering for adaptive learning

Technology:
- sentence-transformers (all-MiniLM-L6-v2, 384-dim)
- PostgreSQL pgvector for vector storage
- HNSW indexing for fast similarity search
"""
from src.semantic.embedding_service import EmbeddingService, EmbeddingResult
from src.semantic.similarity_service import SemanticSimilarityService, SimilarityMatch
from src.semantic.prerequisite_inference import PrerequisiteInferenceService, PrerequisiteSuggestion
from src.semantic.clustering_service import ClusteringService, ClusterResult
from src.semantic.batch_embedding import BatchEmbeddingProcessor

__all__ = [
    # Embedding
    "EmbeddingService",
    "EmbeddingResult",
    "BatchEmbeddingProcessor",
    # Similarity
    "SemanticSimilarityService",
    "SimilarityMatch",
    # Prerequisites
    "PrerequisiteInferenceService",
    "PrerequisiteSuggestion",
    # Clustering
    "ClusteringService",
    "ClusterResult",
]
