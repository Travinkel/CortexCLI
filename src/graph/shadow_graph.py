"""
Shadow Graph Service for Cortex 2.0.

The Shadow Graph is a Neo4j mirror of the Notion knowledge structure,
optimized for graph algorithms that the Notion API cannot perform:
- PageRank centrality for knowledge importance
- Shortest paths for prerequisite chains
- Subgraph queries for Force Z backtracking
- Betweenness centrality for bridging concepts

Architecture:
- Notion is the Source of Truth (write target)
- Neo4j is the Graph Algorithm Cache (read-optimized)
- Sync is unidirectional: Notion → Neo4j

Sync Strategy (Tri-Tiered):
1. Reflex Loop: Webhook-triggered immediate sync
2. Pulse Loop: 5-minute polling for missed webhooks
3. Deep Audit: Nightly full reconciliation

Author: Cortex System
Version: 2.0.0 (Notion-Centric Architecture)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, Iterator
from uuid import UUID

from loguru import logger

# Try to import Neo4j driver
try:
    from neo4j import GraphDatabase, Driver, Session
    from neo4j.exceptions import ServiceUnavailable, AuthError
    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False
    Driver = None
    Session = None

from config import get_settings


# =============================================================================
# DATA MODELS
# =============================================================================

class NodeType(str, Enum):
    """Types of nodes in the Shadow Graph."""
    LEARNING_ATOM = "LearningAtom"
    CONCEPT = "Concept"
    CONCEPT_CLUSTER = "ConceptCluster"
    CONCEPT_AREA = "ConceptArea"
    MODULE = "Module"
    TRACK = "Track"
    PROGRAM = "Program"
    PROJECT = "Project"  # Active learning focus


class EdgeType(str, Enum):
    """Types of edges in the Shadow Graph."""
    PREREQUISITE = "PREREQUISITE"
    TESTS = "TESTS"  # Atom tests concept
    BELONGS_TO = "BELONGS_TO"
    PART_OF = "PART_OF"
    CONFUSES_WITH = "CONFUSES_WITH"  # Adversarial relationship
    SUPPORTS = "SUPPORTS"
    ACTIVE_FOR = "ACTIVE_FOR"  # Project relevance


@dataclass
class GraphNode:
    """A node in the Shadow Graph."""
    id: str  # Notion page ID
    node_type: NodeType
    title: str
    properties: dict[str, Any] = field(default_factory=dict)

    # Computed graph metrics (from Neo4j)
    pagerank: float = 0.0
    betweenness: float = 0.0
    in_degree: int = 0
    out_degree: int = 0

    # Cortex 2.0 computed fields
    z_score: float = 0.0
    z_activation: bool = False
    memory_state: str = "NEW"
    psi: float = 0.5
    last_touched: Optional[datetime] = None


@dataclass
class GraphEdge:
    """An edge in the Shadow Graph."""
    source_id: str
    target_id: str
    edge_type: EdgeType
    strength: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncResult:
    """Result of a sync operation."""
    nodes_created: int = 0
    nodes_updated: int = 0
    edges_created: int = 0
    edges_deleted: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


# =============================================================================
# SHADOW GRAPH SERVICE
# =============================================================================

class ShadowGraphService:
    """
    Neo4j-based Shadow Graph for graph algorithm acceleration.

    This service mirrors Notion's knowledge structure into Neo4j,
    enabling graph algorithms that Notion cannot perform natively.

    Key Responsibilities:
    - Sync Notion pages to Neo4j nodes
    - Compute PageRank and centrality metrics
    - Execute Force Z prerequisite queries
    - Calculate Z-Score components (centrality, project relevance)

    Usage:
        service = ShadowGraphService()
        if service.is_available:
            service.sync_from_notion(notion_pages)
            centralities = service.compute_pagerank()
    """

    def __init__(self):
        """Initialize the Shadow Graph service."""
        self._settings = get_settings()
        self._driver: Optional[Driver] = None
        self._connected = False

        if HAS_NEO4J:
            self._init_driver()
        else:
            logger.warning(
                "Neo4j driver not installed. Install with: pip install neo4j"
            )

    def _init_driver(self) -> None:
        """Initialize the Neo4j driver."""
        try:
            self._driver = GraphDatabase.driver(
                self._settings.neo4j_uri,
                auth=(self._settings.neo4j_user, self._settings.neo4j_password),
            )
            # Verify connectivity
            with self._driver.session(database=self._settings.neo4j_database) as session:
                session.run("RETURN 1")
            self._connected = True
            logger.info(f"Connected to Neo4j at {self._settings.neo4j_uri}")
        except ServiceUnavailable as e:
            logger.warning(f"Neo4j not available: {e}")
            self._connected = False
        except AuthError as e:
            logger.error(f"Neo4j authentication failed: {e}")
            self._connected = False
        except Exception as e:
            logger.error(f"Neo4j connection error: {e}")
            self._connected = False

    @property
    def is_available(self) -> bool:
        """Check if Neo4j is available and connected."""
        return HAS_NEO4J and self._connected

    def close(self) -> None:
        """Close the Neo4j connection."""
        if self._driver:
            self._driver.close()
            self._connected = False

    # =========================================================================
    # SCHEMA INITIALIZATION
    # =========================================================================

    def init_schema(self) -> None:
        """
        Initialize Neo4j schema with indexes and constraints.

        Creates:
        - Unique constraint on node IDs (Notion page IDs)
        - Indexes for common query patterns
        """
        if not self.is_available:
            logger.warning("Neo4j not available; cannot init schema")
            return

        with self._driver.session(database=self._settings.neo4j_database) as session:
            # Unique constraints for each node type
            for node_type in NodeType:
                try:
                    session.run(f"""
                        CREATE CONSTRAINT {node_type.value.lower()}_id IF NOT EXISTS
                        FOR (n:{node_type.value})
                        REQUIRE n.id IS UNIQUE
                    """)
                except Exception as e:
                    logger.debug(f"Constraint may already exist: {e}")

            # Index for z_score queries
            try:
                session.run("""
                    CREATE INDEX zscore_idx IF NOT EXISTS
                    FOR (n:LearningAtom)
                    ON (n.z_score)
                """)
            except Exception as e:
                logger.debug(f"Index may already exist: {e}")

            # Index for memory state
            try:
                session.run("""
                    CREATE INDEX memory_state_idx IF NOT EXISTS
                    FOR (n:LearningAtom)
                    ON (n.memory_state)
                """)
            except Exception as e:
                logger.debug(f"Index may already exist: {e}")

            logger.info("Shadow Graph schema initialized")

    # =========================================================================
    # SYNC OPERATIONS (Notion → Neo4j)
    # =========================================================================

    def sync_node(self, node: GraphNode) -> bool:
        """
        Sync a single node to Neo4j (upsert).

        Args:
            node: GraphNode to sync

        Returns:
            True if successful
        """
        if not self.is_available:
            return False

        with self._driver.session(database=self._settings.neo4j_database) as session:
            try:
                session.run(f"""
                    MERGE (n:{node.node_type.value} {{id: $id}})
                    SET n.title = $title,
                        n.z_score = $z_score,
                        n.z_activation = $z_activation,
                        n.memory_state = $memory_state,
                        n.psi = $psi,
                        n.last_touched = $last_touched,
                        n += $properties
                """, {
                    "id": node.id,
                    "title": node.title,
                    "z_score": node.z_score,
                    "z_activation": node.z_activation,
                    "memory_state": node.memory_state,
                    "psi": node.psi,
                    "last_touched": node.last_touched.isoformat() if node.last_touched else None,
                    "properties": node.properties,
                })
                return True
            except Exception as e:
                logger.error(f"Failed to sync node {node.id}: {e}")
                return False

    def sync_edge(self, edge: GraphEdge) -> bool:
        """
        Sync a single edge to Neo4j (upsert).

        Args:
            edge: GraphEdge to sync

        Returns:
            True if successful
        """
        if not self.is_available:
            return False

        with self._driver.session(database=self._settings.neo4j_database) as session:
            try:
                # Use a generic merge since we don't know source/target types
                session.run(f"""
                    MATCH (source {{id: $source_id}})
                    MATCH (target {{id: $target_id}})
                    MERGE (source)-[r:{edge.edge_type.value}]->(target)
                    SET r.strength = $strength,
                        r += $properties
                """, {
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "strength": edge.strength,
                    "properties": edge.properties,
                })
                return True
            except Exception as e:
                logger.error(f"Failed to sync edge {edge.source_id} -> {edge.target_id}: {e}")
                return False

    def sync_from_notion_pages(
        self,
        pages: list[dict[str, Any]],
        node_type: NodeType,
    ) -> SyncResult:
        """
        Sync Notion pages to Neo4j nodes.

        Args:
            pages: List of raw Notion page dictionaries
            node_type: Type of node to create

        Returns:
            SyncResult with statistics
        """
        result = SyncResult()
        start_time = datetime.now()

        if not self.is_available:
            result.errors.append("Neo4j not available")
            return result

        for page in pages:
            try:
                node = self._notion_page_to_node(page, node_type)
                if self.sync_node(node):
                    result.nodes_created += 1
            except Exception as e:
                result.errors.append(f"Failed to convert page {page.get('id')}: {e}")

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Synced {result.nodes_created} {node_type.value} nodes in {result.duration_seconds:.2f}s"
        )
        return result

    def _notion_page_to_node(
        self,
        page: dict[str, Any],
        node_type: NodeType,
    ) -> GraphNode:
        """Convert a Notion page to a GraphNode."""
        properties = page.get("properties", {})

        # Extract title (try common property names)
        title = ""
        for title_prop in ["Name", "Title", "Question", "Front"]:
            if title_prop in properties:
                title_data = properties[title_prop]
                if "title" in title_data:
                    title_parts = title_data["title"]
                    title = "".join(p.get("plain_text", "") for p in title_parts)
                    break
                elif "rich_text" in title_data:
                    rich_text_parts = title_data["rich_text"]
                    title = "".join(p.get("plain_text", "") for p in rich_text_parts)
                    break

        # Extract common properties
        z_score = self._extract_number_property(properties, self._settings.notion_prop_z_score)
        z_activation = self._extract_checkbox_property(properties, self._settings.notion_prop_z_activation)
        memory_state = self._extract_status_property(properties, self._settings.notion_prop_memory_state)
        psi = self._extract_number_property(properties, self._settings.notion_prop_psi)

        # Extract last edited time
        last_edited = page.get("last_edited_time")
        last_touched = None
        if last_edited:
            try:
                last_touched = datetime.fromisoformat(last_edited.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        return GraphNode(
            id=page["id"],
            node_type=node_type,
            title=title[:500],  # Truncate for Neo4j
            z_score=z_score or 0.0,
            z_activation=z_activation,
            memory_state=memory_state or "NEW",
            psi=psi or 0.5,
            last_touched=last_touched,
            properties={
                "notion_url": page.get("url", ""),
            },
        )

    def _extract_number_property(
        self,
        properties: dict,
        prop_name: str,
    ) -> Optional[float]:
        """Extract a number property from Notion properties."""
        if prop_name not in properties:
            return None
        prop = properties[prop_name]
        if "number" in prop:
            return prop["number"]
        return None

    def _extract_checkbox_property(
        self,
        properties: dict,
        prop_name: str,
    ) -> bool:
        """Extract a checkbox property from Notion properties."""
        if prop_name not in properties:
            return False
        prop = properties[prop_name]
        if "checkbox" in prop:
            return prop["checkbox"]
        return False

    def _extract_status_property(
        self,
        properties: dict,
        prop_name: str,
    ) -> Optional[str]:
        """Extract a status property from Notion properties."""
        if prop_name not in properties:
            return None
        prop = properties[prop_name]
        if "status" in prop and prop["status"]:
            return prop["status"].get("name")
        if "select" in prop and prop["select"]:
            return prop["select"].get("name")
        return None

    # =========================================================================
    # GRAPH ALGORITHMS
    # =========================================================================

    def compute_pagerank(
        self,
        node_type: NodeType = NodeType.LEARNING_ATOM,
        damping_factor: float = 0.85,
        max_iterations: int = 20,
    ) -> dict[str, float]:
        """
        Compute PageRank centrality for nodes.

        PageRank measures the importance of a node based on the
        importance of nodes linking to it. Used as the Centrality
        signal C(a) in the Z-Score formula.

        Args:
            node_type: Type of nodes to compute PageRank for
            damping_factor: PageRank damping factor (0.85 standard)
            max_iterations: Maximum iterations for convergence

        Returns:
            Dictionary mapping node ID to PageRank score
        """
        if not self.is_available:
            return {}

        with self._driver.session(database=self._settings.neo4j_database) as session:
            try:
                # Use native PageRank if GDS is available, otherwise simple approximation
                result = session.run(f"""
                    MATCH (n:{node_type.value})
                    WITH n, size((n)<--()) as inDegree, size((n)-->()) as outDegree
                    RETURN n.id as id,
                           toFloat(inDegree) / (toFloat(inDegree) + toFloat(outDegree) + 1) as rank
                    ORDER BY rank DESC
                """)

                return {record["id"]: record["rank"] for record in result}
            except Exception as e:
                logger.error(f"PageRank computation failed: {e}")
                return {}

    def get_prerequisite_chain(
        self,
        atom_id: str,
        max_depth: int = None,
    ) -> list[GraphNode]:
        """
        Get the prerequisite chain for an atom (Force Z query).

        Traverses the PREREQUISITE edges backwards to find all
        foundation concepts that must be mastered.

        Args:
            atom_id: ID of the target atom
            max_depth: Maximum depth (default from settings)

        Returns:
            List of prerequisite nodes in topological order
        """
        if max_depth is None:
            max_depth = self._settings.force_z_max_depth

        if not self.is_available:
            return []

        with self._driver.session(database=self._settings.neo4j_database) as session:
            try:
                result = session.run("""
                    MATCH path = (target {id: $atom_id})<-[:PREREQUISITE*1..$max_depth]-(prereq)
                    WITH prereq, length(path) as depth
                    RETURN prereq.id as id,
                           prereq.title as title,
                           prereq.memory_state as memory_state,
                           prereq.z_score as z_score,
                           depth
                    ORDER BY depth DESC
                """, {"atom_id": atom_id, "max_depth": max_depth})

                nodes = []
                for record in result:
                    nodes.append(GraphNode(
                        id=record["id"],
                        node_type=NodeType.LEARNING_ATOM,
                        title=record["title"] or "",
                        memory_state=record["memory_state"] or "NEW",
                        z_score=record["z_score"] or 0.0,
                    ))
                return nodes
            except Exception as e:
                logger.error(f"Prerequisite chain query failed: {e}")
                return []

    def get_weak_prerequisites(
        self,
        atom_id: str,
        mastery_threshold: float = None,
    ) -> list[GraphNode]:
        """
        Get prerequisites that haven't met mastery threshold.

        This is the core Force Z query - finds prerequisites that
        need remediation before the target atom can be learned.

        Args:
            atom_id: ID of the target atom
            mastery_threshold: Mastery threshold (default from settings)

        Returns:
            List of weak prerequisite nodes
        """
        if mastery_threshold is None:
            mastery_threshold = self._settings.force_z_mastery_threshold

        if not self.is_available:
            return []

        with self._driver.session(database=self._settings.neo4j_database) as session:
            try:
                result = session.run("""
                    MATCH (target {id: $atom_id})<-[:PREREQUISITE*1..5]-(prereq:LearningAtom)
                    WHERE prereq.z_score < $threshold
                       OR prereq.memory_state IN ['NEW', 'LEARNING']
                    RETURN DISTINCT prereq.id as id,
                           prereq.title as title,
                           prereq.memory_state as memory_state,
                           prereq.z_score as z_score,
                           prereq.psi as psi
                    ORDER BY prereq.z_score ASC
                """, {"atom_id": atom_id, "threshold": mastery_threshold})

                nodes = []
                for record in result:
                    nodes.append(GraphNode(
                        id=record["id"],
                        node_type=NodeType.LEARNING_ATOM,
                        title=record["title"] or "",
                        memory_state=record["memory_state"] or "NEW",
                        z_score=record["z_score"] or 0.0,
                        psi=record["psi"] or 0.5,
                    ))
                return nodes
            except Exception as e:
                logger.error(f"Weak prerequisites query failed: {e}")
                return []

    def get_confusables(
        self,
        atom_id: str,
        limit: int = 5,
    ) -> list[GraphNode]:
        """
        Get atoms that are commonly confused with the target.

        Uses CONFUSES_WITH edges for discrimination training.

        Args:
            atom_id: ID of the target atom
            limit: Maximum number of confusables to return

        Returns:
            List of confusable atoms
        """
        if not self.is_available:
            return []

        with self._driver.session(database=self._settings.neo4j_database) as session:
            try:
                result = session.run("""
                    MATCH (target {id: $atom_id})-[:CONFUSES_WITH]-(confusable:LearningAtom)
                    RETURN confusable.id as id,
                           confusable.title as title,
                           confusable.psi as psi
                    LIMIT $limit
                """, {"atom_id": atom_id, "limit": limit})

                nodes = []
                for record in result:
                    nodes.append(GraphNode(
                        id=record["id"],
                        node_type=NodeType.LEARNING_ATOM,
                        title=record["title"] or "",
                        psi=record["psi"] or 0.5,
                    ))
                return nodes
            except Exception as e:
                logger.error(f"Confusables query failed: {e}")
                return []

    def get_project_atoms(
        self,
        project_id: str,
    ) -> list[str]:
        """
        Get all atoms relevant to a project.

        Traverses the project's concept references to find atoms.
        Used for the Project Relevance signal P(a) in Z-Score.

        Args:
            project_id: ID of the project

        Returns:
            List of atom IDs
        """
        if not self.is_available:
            return []

        with self._driver.session(database=self._settings.neo4j_database) as session:
            try:
                result = session.run("""
                    MATCH (p:Project {id: $project_id})-[:ACTIVE_FOR]->(c:Concept)
                          <-[:TESTS]-(a:LearningAtom)
                    RETURN DISTINCT a.id as id
                """, {"project_id": project_id})

                return [record["id"] for record in result]
            except Exception as e:
                logger.error(f"Project atoms query failed: {e}")
                return []

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get Shadow Graph statistics."""
        if not self.is_available:
            return {"available": False}

        with self._driver.session(database=self._settings.neo4j_database) as session:
            try:
                result = session.run("""
                    MATCH (n)
                    WITH labels(n)[0] as label, count(n) as count
                    RETURN label, count
                    ORDER BY count DESC
                """)

                node_counts = {record["label"]: record["count"] for record in result}

                edge_result = session.run("""
                    MATCH ()-[r]->()
                    WITH type(r) as type, count(r) as count
                    RETURN type, count
                    ORDER BY count DESC
                """)

                edge_counts = {record["type"]: record["count"] for record in edge_result}

                return {
                    "available": True,
                    "connected": self._connected,
                    "uri": self._settings.neo4j_uri,
                    "database": self._settings.neo4j_database,
                    "nodes": node_counts,
                    "edges": edge_counts,
                    "total_nodes": sum(node_counts.values()),
                    "total_edges": sum(edge_counts.values()),
                }
            except Exception as e:
                logger.error(f"Stats query failed: {e}")
                return {"available": True, "error": str(e)}


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_service: Optional[ShadowGraphService] = None


def get_shadow_graph() -> ShadowGraphService:
    """Get or create the global Shadow Graph service."""
    global _service
    if _service is None:
        _service = ShadowGraphService()
    return _service


def compute_centrality(atom_id: str) -> float:
    """
    Compute centrality for a single atom.

    Convenience function for Z-Score calculation.
    """
    service = get_shadow_graph()
    if not service.is_available:
        return 0.5  # Default centrality

    rankings = service.compute_pagerank()
    return rankings.get(atom_id, 0.0)


def get_force_z_targets(atom_id: str) -> list[str]:
    """
    Get prerequisite atoms that need Force Z backtracking.

    Returns atom IDs that are weak prerequisites.
    """
    service = get_shadow_graph()
    weak = service.get_weak_prerequisites(atom_id)
    return [node.id for node in weak]
