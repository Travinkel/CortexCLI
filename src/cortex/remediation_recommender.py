"""
Remediation Recommender: Cross-topic content recommendations.

When Socratic dialogue reveals prerequisite knowledge gaps,
this component finds appropriate atoms to fill those gaps.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger
from sqlalchemy import text

from src.db.database import engine


class RemediationRecommender:
    """
    Recommends remediation atoms based on detected knowledge gaps.

    Uses:
    - Topic matching from gap keywords
    - CCNA section relationships
    - Prior struggle patterns
    """

    # Topic to section mapping for CCNA content
    TOPIC_SECTION_MAP = {
        "binary": ["11.4", "11.5", "11.6"],
        "subnet": ["11.4", "11.5", "11.6", "11.7", "11.8"],
        "subnetting": ["11.4", "11.5", "11.6", "11.7", "11.8"],
        "mask": ["11.4", "11.5"],
        "broadcast": ["11.4", "11.6"],
        "network address": ["11.4", "11.6"],
        "host": ["11.4", "11.5", "11.6"],
        "ip address": ["11.1", "11.2", "11.3", "11.4"],
        "ipv4": ["11.1", "11.2", "11.3", "11.4"],
        "ipv6": ["12.1", "12.2", "12.3", "12.4"],
        "osi": ["3.1", "3.2", "3.3", "3.4"],
        "layer": ["3.1", "3.2", "3.3", "3.4"],
        "tcp": ["14.1", "14.2", "14.3"],
        "udp": ["14.1", "14.4"],
        "port": ["14.1", "14.2"],
        "ethernet": ["4.1", "4.2", "4.3", "4.4"],
        "mac": ["4.3", "4.4", "6.1"],
        "switch": ["6.1", "6.2", "6.3", "6.4"],
        "router": ["16.1", "16.2", "16.3"],
        "routing": ["16.1", "16.2", "16.3", "16.4"],
        "vlan": ["6.1", "6.2", "6.3"],
        "arp": ["9.1", "9.2", "9.3"],
        "dhcp": ["10.1", "10.2", "10.3"],
        "dns": ["10.1", "10.2"],
        "nat": ["9.2", "16.3"],
        "acl": ["17.1", "17.2", "17.3"],
        "firewall": ["17.1", "17.2"],
        "security": ["17.1", "17.2", "17.3", "17.4"],
        "ssh": ["17.4", "2.4"],
        "console": ["2.1", "2.2", "2.3"],
        "ios": ["2.1", "2.2", "2.3", "2.4"],
        "cli": ["2.1", "2.2", "2.3"],
        "configure": ["2.3", "2.4"],
    }

    def __init__(self):
        pass

    def recommend(
        self,
        gaps: list[str],
        current_atom_id: str | None = None,
        limit_per_gap: int = 3,
    ) -> list[dict]:
        """
        Recommend atoms to fill prerequisite gaps.

        Args:
            gaps: List of detected gap topics
            current_atom_id: ID of current atom (to exclude)
            limit_per_gap: Maximum recommendations per gap

        Returns:
            List of recommendations with structure:
            {
                "gap": "topic name",
                "reason": "explanation",
                "atoms": [{"id": ..., "front": ..., "atom_type": ...}, ...]
            }
        """
        recommendations = []

        for gap in gaps:
            gap_lower = gap.lower()

            # Find relevant sections for this gap
            sections = self._find_sections_for_topic(gap_lower)

            if sections:
                atoms = self._query_atoms_by_sections(
                    sections, current_atom_id, limit_per_gap
                )
            else:
                # Fallback to keyword search
                atoms = self._query_atoms_by_keyword(
                    gap_lower, current_atom_id, limit_per_gap
                )

            if atoms:
                recommendations.append({
                    "gap": gap,
                    "reason": f"Your responses suggest reviewing {gap}",
                    "atoms": atoms,
                })

        return recommendations

    def recommend_from_struggle_history(
        self,
        learner_id: str = "default",
        limit: int = 5,
    ) -> list[dict]:
        """
        Recommend based on historical struggle patterns.

        Queries the dialogue recorder for frequently struggled atoms
        and recommends related remediation content.
        """
        try:
            with engine.connect() as conn:
                # Get atoms with high scaffold levels
                result = conn.execute(
                    text("""
                        SELECT DISTINCT atom_id
                        FROM socratic_dialogues
                        WHERE learner_id = :learner_id
                          AND scaffold_level_reached >= 2
                        ORDER BY scaffold_level_reached DESC
                        LIMIT :limit
                    """),
                    {"learner_id": learner_id, "limit": limit}
                )

                struggle_atom_ids = [row[0] for row in result.fetchall()]

                if not struggle_atom_ids:
                    return []

                # Get sections for struggled atoms
                sections = set()
                for atom_id in struggle_atom_ids:
                    atom_sections = self._get_atom_sections(atom_id)
                    sections.update(atom_sections)

                if not sections:
                    return []

                # Find prerequisite atoms for those sections
                prereq_atoms = self._query_prerequisite_atoms(
                    list(sections), struggle_atom_ids, limit
                )

                if prereq_atoms:
                    return [{
                        "gap": "Historical struggle areas",
                        "reason": "Based on your past learning sessions",
                        "atoms": prereq_atoms,
                    }]

                return []

        except Exception as e:
            logger.error(f"Failed to get struggle recommendations: {e}")
            return []

    def _find_sections_for_topic(self, topic: str) -> list[str]:
        """Map a topic keyword to CCNA section IDs."""
        sections = []

        for keyword, section_list in self.TOPIC_SECTION_MAP.items():
            if keyword in topic or topic in keyword:
                sections.extend(section_list)

        return list(set(sections))

    def _query_atoms_by_sections(
        self,
        sections: list[str],
        exclude_id: str | None,
        limit: int,
    ) -> list[dict]:
        """Query atoms from specific CCNA sections."""
        try:
            # Build section pattern for LIKE queries
            section_patterns = [f"{s}%" for s in sections]

            with engine.connect() as conn:
                # Build dynamic query with OR conditions for sections
                query = """
                    SELECT id, card_id, front, atom_type, ccna_section_id
                    FROM learning_atoms
                    WHERE (
                """
                params = {"exclude_id": exclude_id, "limit": limit}

                conditions = []
                for i, pattern in enumerate(section_patterns):
                    param_name = f"section_{i}"
                    conditions.append(f"ccna_section_id LIKE :{param_name}")
                    params[param_name] = pattern

                query += " OR ".join(conditions)
                query += ") AND atom_type IN ('flashcard', 'cloze', 'mcq', 'true_false', 'parsons', 'matching', 'numeric')"

                if exclude_id:
                    query += " AND id != :exclude_id AND card_id != :exclude_id"

                query += " ORDER BY RANDOM() LIMIT :limit"

                result = conn.execute(text(query), params)

                return [
                    {
                        "id": str(row[0]),
                        "card_id": row[1],
                        "front": row[2],  # Full text - let display layer handle wrapping
                        "atom_type": row[3],
                        "section": row[4],
                    }
                    for row in result.fetchall()
                ]

        except Exception as e:
            logger.error(f"Failed to query atoms by sections: {e}")
            return []

    def _query_atoms_by_keyword(
        self,
        keyword: str,
        exclude_id: str | None,
        limit: int,
    ) -> list[dict]:
        """Query atoms matching a keyword in front field."""
        try:
            with engine.connect() as conn:
                query = """
                    SELECT id, card_id, front, atom_type, ccna_section_id
                    FROM learning_atoms
                    WHERE LOWER(front) LIKE :pattern
                      AND atom_type IN ('flashcard', 'cloze', 'mcq', 'true_false', 'parsons', 'matching', 'numeric')
                """
                params = {
                    "pattern": f"%{keyword}%",
                    "limit": limit,
                }

                if exclude_id:
                    query += " AND id != :exclude_id AND card_id != :exclude_id"
                    params["exclude_id"] = exclude_id

                query += " ORDER BY RANDOM() LIMIT :limit"

                result = conn.execute(text(query), params)

                return [
                    {
                        "id": str(row[0]),
                        "card_id": row[1],
                        "front": row[2],  # Full text - let display layer handle wrapping
                        "atom_type": row[3],
                        "section": row[4],
                    }
                    for row in result.fetchall()
                ]

        except Exception as e:
            logger.error(f"Failed to query atoms by keyword: {e}")
            return []

    def _get_atom_sections(self, atom_id: str) -> list[str]:
        """Get CCNA sections for an atom."""
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT ccna_section_id
                        FROM learning_atoms
                        WHERE id = :id OR card_id = :id
                    """),
                    {"id": atom_id}
                )
                row = result.fetchone()
                if row and row[0]:
                    # Return section prefix (e.g., "11.4" from "11.4.1")
                    section = row[0]
                    parts = section.split(".")
                    if len(parts) >= 2:
                        return [f"{parts[0]}.{parts[1]}"]
                    return [section]
                return []

        except Exception as e:
            logger.error(f"Failed to get atom sections: {e}")
            return []

    def _query_prerequisite_atoms(
        self,
        sections: list[str],
        exclude_ids: list[str],
        limit: int,
    ) -> list[dict]:
        """Query atoms from earlier sections (prerequisites)."""
        try:
            # Find lower section numbers
            prereq_sections = []
            for section in sections:
                parts = section.split(".")
                if len(parts) >= 2:
                    module = int(parts[0])
                    # Get sections from earlier modules
                    for m in range(max(1, module - 2), module):
                        prereq_sections.append(f"{m}.")

            if not prereq_sections:
                return []

            with engine.connect() as conn:
                query = """
                    SELECT id, card_id, front, atom_type, ccna_section_id
                    FROM learning_atoms
                    WHERE (
                """
                params = {"limit": limit}

                conditions = []
                for i, prefix in enumerate(prereq_sections):
                    param_name = f"prereq_{i}"
                    conditions.append(f"ccna_section_id LIKE :{param_name}")
                    params[param_name] = f"{prefix}%"

                query += " OR ".join(conditions)
                query += ") AND atom_type IN ('flashcard', 'cloze', 'mcq', 'true_false', 'parsons', 'matching', 'numeric')"

                if exclude_ids:
                    placeholders = ", ".join(f":ex_{i}" for i in range(len(exclude_ids)))
                    query += f" AND id NOT IN ({placeholders}) AND card_id NOT IN ({placeholders})"
                    for i, ex_id in enumerate(exclude_ids):
                        params[f"ex_{i}"] = ex_id

                query += " ORDER BY RANDOM() LIMIT :limit"

                result = conn.execute(text(query), params)

                return [
                    {
                        "id": str(row[0]),
                        "card_id": row[1],
                        "front": row[2],  # Full text - let display layer handle wrapping
                        "atom_type": row[3],
                        "section": row[4],
                    }
                    for row in result.fetchall()
                ]

        except Exception as e:
            logger.error(f"Failed to query prerequisite atoms: {e}")
            return []
