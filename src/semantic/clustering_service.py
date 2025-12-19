"""
Knowledge State Clustering Service - Group related learning atoms by semantic similarity.

Uses K-means clustering on embeddings to discover natural groupings in
the knowledge space. This helps with:
- Identifying knowledge domains/themes
- Finding representative examples (exemplars)
- Adaptive learning path recommendations

References:
- Silhouette score: https://scikit-learn.org/stable/modules/clustering.html#silhouette-coefficient
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import numpy as np
from loguru import logger
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import get_settings
from src.semantic.embedding_service import EmbeddingService


@dataclass
class ClusterResult:
    """Result of clustering a set of atoms."""

    cluster_id: int
    centroid: np.ndarray
    atom_ids: list[UUID]
    size: int
    exemplar_id: UUID | None = None

    @property
    def centroid_list(self) -> list[float]:
        """Convert centroid to list for database storage."""
        return self.centroid.tolist()


@dataclass
class ClusterInfo:
    """Information about a knowledge cluster."""

    cluster_db_id: UUID
    name: str
    size: int
    silhouette_score: float | None
    sample_fronts: list[str]


class ClusteringService:
    """
    Group related learning atoms into semantic clusters.

    Uses K-means clustering on embeddings for knowledge state grouping.
    Clusters can be used to:
    - Identify related content for adaptive learning
    - Find exemplar atoms for each topic
    - Analyze knowledge distribution

    Example:
        >>> service = ClusteringService(db_session)
        >>> clusters = service.cluster_atoms(n_clusters=10)
        >>> for c in clusters:
        ...     print(f"Cluster {c.cluster_id}: {c.size} atoms")
    """

    def __init__(
        self,
        db_session: Session,
        embedding_service: EmbeddingService | None = None,
    ):
        """
        Initialize the clustering service.

        Args:
            db_session: SQLAlchemy database session.
            embedding_service: Optional embedding service.
        """
        self.db = db_session
        self.embedding_service = embedding_service or EmbeddingService()
        self.settings = get_settings()

    def cluster_atoms(
        self,
        n_clusters: int = 10,
        concept_area_id: UUID | None = None,
        max_atoms: int = 10000,
        random_state: int = 42,
    ) -> list[ClusterResult]:
        """
        Cluster atoms into semantic groups.

        Args:
            n_clusters: Number of clusters to create.
            concept_area_id: Optional filter to cluster within a concept area.
            max_atoms: Maximum atoms to include in clustering.
            random_state: Random seed for reproducibility.

        Returns:
            List of ClusterResult objects.
        """
        logger.info(f"Clustering atoms into {n_clusters} groups")

        # Fetch embeddings
        if concept_area_id:
            query = text("""
                SELECT a.id, a.embedding
                FROM learning_atoms a
                JOIN concepts c ON a.concept_id = c.id
                JOIN clean_concept_clusters cc ON c.cluster_id = cc.id
                WHERE a.embedding IS NOT NULL
                  AND cc.concept_area_id = :concept_area_id
                LIMIT :max_atoms
            """)
            results = self.db.execute(
                query,
                {"concept_area_id": str(concept_area_id), "max_atoms": max_atoms},
            ).fetchall()
        else:
            query = text("""
                SELECT id, embedding
                FROM learning_atoms
                WHERE embedding IS NOT NULL
                LIMIT :max_atoms
            """)
            results = self.db.execute(query, {"max_atoms": max_atoms}).fetchall()

        if len(results) < n_clusters:
            logger.warning(f"Not enough atoms ({len(results)}) for {n_clusters} clusters")
            n_clusters = max(1, len(results) // 2)

        if len(results) < 2:
            logger.warning("Not enough atoms for clustering")
            return []

        # Convert to numpy arrays
        atom_ids = [row.id for row in results]
        embeddings = np.array([row.embedding for row in results])

        # Perform K-means clustering
        logger.info(f"Running K-means with {n_clusters} clusters on {len(embeddings)} atoms")
        kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
        labels = kmeans.fit_predict(embeddings)
        centroids = kmeans.cluster_centers_

        # Build cluster results
        cluster_results = []
        for cluster_id in range(n_clusters):
            mask = labels == cluster_id
            cluster_atom_ids = [atom_ids[i] for i in range(len(atom_ids)) if mask[i]]
            cluster_embeddings = embeddings[mask]

            # Find exemplar (closest to centroid)
            exemplar_id = None
            if len(cluster_embeddings) > 0:
                distances = np.linalg.norm(cluster_embeddings - centroids[cluster_id], axis=1)
                exemplar_idx = np.argmin(distances)
                exemplar_id = cluster_atom_ids[exemplar_idx]

            cluster_results.append(
                ClusterResult(
                    cluster_id=cluster_id,
                    centroid=centroids[cluster_id],
                    atom_ids=cluster_atom_ids,
                    size=len(cluster_atom_ids),
                    exemplar_id=exemplar_id,
                )
            )

        logger.info(f"Created {len(cluster_results)} clusters")
        return cluster_results

    def compute_silhouette_score(
        self,
        embeddings: np.ndarray,
        labels: np.ndarray,
    ) -> float:
        """
        Compute silhouette score for cluster quality.

        Args:
            embeddings: Array of embedding vectors.
            labels: Cluster labels for each embedding.

        Returns:
            Silhouette score between -1 and 1 (higher is better).
        """
        if len(np.unique(labels)) < 2:
            return 0.0

        return float(silhouette_score(embeddings, labels))

    def store_clusters(
        self,
        clusters: list[ClusterResult],
        cluster_name_prefix: str = "Auto-Cluster",
        concept_area_id: UUID | None = None,
        cluster_method: str = "kmeans",
    ) -> list[UUID]:
        """
        Store clusters in database.

        Args:
            clusters: List of ClusterResult objects.
            cluster_name_prefix: Prefix for auto-generated cluster names.
            concept_area_id: Optional concept area to associate with.
            cluster_method: Clustering method used.

        Returns:
            List of database UUIDs for the created clusters.
        """
        cluster_db_ids = []

        for cluster in clusters:
            # Insert cluster
            insert_cluster = text("""
                INSERT INTO knowledge_clusters
                (name, centroid, cluster_method, concept_area_id)
                VALUES (:name, :centroid::vector, :cluster_method, :concept_area_id)
                RETURNING id
            """)

            result = self.db.execute(
                insert_cluster,
                {
                    "name": f"{cluster_name_prefix}-{cluster.cluster_id}",
                    "centroid": str(cluster.centroid_list),
                    "cluster_method": cluster_method,
                    "concept_area_id": str(concept_area_id) if concept_area_id else None,
                },
            ).fetchone()

            cluster_db_id = result.id
            cluster_db_ids.append(cluster_db_id)

            # Insert cluster members
            for i, atom_id in enumerate(cluster.atom_ids):
                # Calculate distance to centroid for this atom
                is_exemplar = atom_id == cluster.exemplar_id

                insert_member = text("""
                    INSERT INTO knowledge_cluster_members
                    (cluster_id, atom_id, is_exemplar)
                    VALUES (:cluster_id, :atom_id, :is_exemplar)
                """)

                self.db.execute(
                    insert_member,
                    {
                        "cluster_id": str(cluster_db_id),
                        "atom_id": str(atom_id),
                        "is_exemplar": is_exemplar,
                    },
                )

        self.db.commit()
        logger.info(f"Stored {len(cluster_db_ids)} clusters in database")
        return cluster_db_ids

    def list_clusters(
        self,
        active_only: bool = True,
        limit: int = 50,
    ) -> list[ClusterInfo]:
        """
        List existing knowledge clusters.

        Args:
            active_only: Only include active clusters.
            limit: Maximum clusters to return.

        Returns:
            List of ClusterInfo objects.
        """
        active_filter = "WHERE kc.is_active = true" if active_only else ""

        query = text(f"""
            SELECT
                kc.id,
                kc.name,
                kc.silhouette_score,
                COUNT(kcm.atom_id) as member_count
            FROM knowledge_clusters kc
            LEFT JOIN knowledge_cluster_members kcm ON kc.id = kcm.cluster_id
            {active_filter}
            GROUP BY kc.id, kc.name, kc.silhouette_score
            ORDER BY member_count DESC
            LIMIT :limit
        """)

        results = self.db.execute(query, {"limit": limit}).fetchall()

        cluster_infos = []
        for row in results:
            # Get sample fronts for this cluster
            samples_query = text("""
                SELECT a.front
                FROM learning_atoms a
                JOIN knowledge_cluster_members kcm ON a.id = kcm.atom_id
                WHERE kcm.cluster_id = :cluster_id
                LIMIT 3
            """)
            samples = self.db.execute(
                samples_query,
                {"cluster_id": str(row.id)},
            ).fetchall()

            cluster_infos.append(
                ClusterInfo(
                    cluster_db_id=row.id,
                    name=row.name or "Unnamed",
                    size=row.member_count,
                    silhouette_score=float(row.silhouette_score) if row.silhouette_score else None,
                    sample_fronts=[s.front for s in samples],
                )
            )

        return cluster_infos

    def get_cluster_members(
        self,
        cluster_id: UUID,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get atoms belonging to a cluster.

        Args:
            cluster_id: UUID of the cluster.
            limit: Maximum members to return.

        Returns:
            List of atom dictionaries.
        """
        query = text("""
            SELECT
                a.id,
                a.card_id,
                a.front,
                a.back,
                kcm.distance_to_centroid,
                kcm.is_exemplar
            FROM learning_atoms a
            JOIN knowledge_cluster_members kcm ON a.id = kcm.atom_id
            WHERE kcm.cluster_id = :cluster_id
            ORDER BY kcm.is_exemplar DESC, kcm.distance_to_centroid ASC
            LIMIT :limit
        """)

        results = self.db.execute(
            query,
            {"cluster_id": str(cluster_id), "limit": limit},
        ).fetchall()

        return [
            {
                "id": str(row.id),
                "card_id": row.card_id,
                "front": row.front,
                "back": row.back,
                "distance_to_centroid": float(row.distance_to_centroid)
                if row.distance_to_centroid
                else None,
                "is_exemplar": row.is_exemplar,
            }
            for row in results
        ]

    def deactivate_cluster(self, cluster_id: UUID) -> bool:
        """
        Deactivate a cluster (soft delete).

        Args:
            cluster_id: UUID of the cluster.

        Returns:
            True if updated, False if not found.
        """
        query = text("""
            UPDATE knowledge_clusters
            SET is_active = false,
                updated_at = now()
            WHERE id = :cluster_id
        """)

        result = self.db.execute(query, {"cluster_id": str(cluster_id)})
        self.db.commit()

        return result.rowcount > 0

    def recluster(
        self,
        n_clusters: int = 10,
        deactivate_existing: bool = True,
    ) -> list[UUID]:
        """
        Re-run clustering and replace existing clusters.

        Args:
            n_clusters: Number of clusters to create.
            deactivate_existing: Deactivate all existing clusters first.

        Returns:
            List of new cluster UUIDs.
        """
        if deactivate_existing:
            deactivate_query = text("""
                UPDATE knowledge_clusters
                SET is_active = false
                WHERE is_active = true
            """)
            self.db.execute(deactivate_query)
            self.db.commit()
            logger.info("Deactivated existing clusters")

        # Create new clusters
        clusters = self.cluster_atoms(n_clusters=n_clusters)
        cluster_ids = self.store_clusters(clusters)

        return cluster_ids
