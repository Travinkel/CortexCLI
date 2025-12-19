"""
Study Service for CCNA Learning Path.

Provides high-level operations for the CLI:
- Get daily study summary
- Get learning path overview
- Get module details
- Sync mastery from Anki
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from loguru import logger
from sqlalchemy import text

from src.adaptive.models import TYPE_QUOTAS, TYPE_MINIMUM
from src.adaptive.neuro_model import CognitiveDiagnosis
from src.study.interleaver import AdaptiveInterleaver
from src.study.mastery_calculator import MasteryCalculator


@dataclass
class ExpandedModuleAtoms:
    """
    Result of cross-module expansion via prerequisite graph.

    When studying Module X, this includes atoms from:
    - The target module itself
    - Prerequisite concepts from earlier modules (up to max_depth hops)
    - Dependent concepts from later modules (up to max_depth hops)
    """

    target_module: int
    max_depth: int

    # Atoms grouped by destination system
    anki_atoms: list[dict] = field(default_factory=list)  # flashcard + cloze → Anki
    quiz_atoms: list[dict] = field(default_factory=list)  # mcq, tf, matching, parsons → NLS

    # Relationship metadata
    modules_touched: list[int] = field(default_factory=list)  # All modules in expansion
    concept_count: int = 0
    prerequisite_chain_depth: int = 0

    # Mastery-weighted priority (higher = focus here first)
    priority_atoms: list[dict] = field(default_factory=list)  # Low mastery atoms


@dataclass
class DailyStudySummary:
    """Summary for daily study session."""

    date: date
    due_reviews: int
    learned_count: int
    total_count: int
    remediation_sections: int
    remediation_atoms: int
    estimated_minutes: int
    current_module: int
    current_section: str
    overall_mastery: float
    streak_days: int


@dataclass
class ModuleSummary:
    """Summary of a module's progress."""

    module_number: int
    title: str
    total_sections: int
    sections_completed: int
    avg_mastery: float
    atoms_total: int
    atoms_mastered: int
    atoms_learning: int
    atoms_struggling: int
    atoms_new: int
    sections_needing_remediation: int


@dataclass
class SectionDetail:
    """Detailed view of a section."""

    section_id: str
    title: str
    level: int
    parent_section_id: str | None
    mastery_score: float
    is_mastered: bool
    needs_remediation: bool
    remediation_reason: str | None
    atoms_total: int
    atoms_mastered: int
    atoms_learning: int
    atoms_struggling: int
    atoms_new: int
    last_review_date: datetime | None
    subsections: list[SectionDetail]


class StudyService:
    """
    High-level service for study operations.

    Coordinates between database, mastery calculator, and interleaver.
    """

    def __init__(self, user_id: str = "default"):
        """
        Initialize study service.

        Args:
            user_id: User identifier (default for now)
        """
        self.user_id = user_id
        self.mastery_calculator = MasteryCalculator()
        self.interleaver = AdaptiveInterleaver()

    def get_daily_summary(self) -> DailyStudySummary:
        """
        Get summary for today's study session.

        Returns:
            DailyStudySummary with all relevant stats
        """
        from src.db.database import engine

        with engine.connect() as conn:
            # Get due reviews count (simplified - would need Anki sync)
            due_result = conn.execute(
                text("""
                SELECT COUNT(*) as cnt
                FROM learning_atoms
                WHERE anki_due_date IS NOT NULL
                  AND anki_due_date <= CURRENT_DATE
            """)
            )
            due_reviews = due_result.fetchone().cnt or 0

            # Get learned/total atom counts
            progress_result = conn.execute(
                text("""
                SELECT
                    COUNT(*) FILTER (WHERE anki_review_count > 0) as learned,
                    COUNT(*) as total
                FROM learning_atoms
                WHERE ccna_section_id IS NOT NULL
            """)
            )
            progress_row = progress_result.fetchone()
            learned_count = progress_row.learned or 0
            total_count = progress_row.total or 0

            # Get remediation stats
            remediation_result = conn.execute(
                text("""
                SELECT
                    COUNT(*) as sections,
                    COALESCE(SUM(atoms_struggling), 0) as atoms
                FROM ccna_section_mastery
                WHERE needs_remediation = TRUE
                  AND user_id = :user_id
            """),
                {"user_id": self.user_id},
            )
            rem_row = remediation_result.fetchone()
            remediation_sections = rem_row.sections or 0
            remediation_atoms = rem_row.atoms or 0

            # Get overall mastery
            mastery_result = conn.execute(
                text("""
                SELECT AVG(mastery_score) as avg_mastery
                FROM ccna_section_mastery
                WHERE user_id = :user_id
            """),
                {"user_id": self.user_id},
            )
            overall_mastery = mastery_result.fetchone().avg_mastery or 0

            # Get current progress (first incomplete section)
            current_result = conn.execute(
                text("""
                SELECT s.module_number, s.section_id
                FROM ccna_sections s
                LEFT JOIN ccna_section_mastery m
                    ON s.section_id = m.section_id AND m.user_id = :user_id
                WHERE COALESCE(m.is_completed, FALSE) = FALSE
                ORDER BY s.display_order
                LIMIT 1
            """),
                {"user_id": self.user_id},
            )
            current_row = current_result.fetchone()
            current_module = current_row.module_number if current_row else 1
            current_section = current_row.section_id if current_row else "1.2"

            # Estimate time (30 sec per card)
            unlearned = max(0, total_count - learned_count)
            total_cards = due_reviews + min(30, unlearned) + min(15, remediation_atoms)
            estimated_minutes = max(1, total_cards // 2)

            # Streak (simplified - count consecutive days with sessions)
            streak_result = conn.execute(
                text("""
                SELECT COUNT(DISTINCT session_date) as streak
                FROM ccna_study_sessions
                WHERE user_id = :user_id
                  AND session_date >= CURRENT_DATE - INTERVAL '30 days'
            """),
                {"user_id": self.user_id},
            )
            streak_days = streak_result.fetchone().streak or 0

        return DailyStudySummary(
            date=date.today(),
            due_reviews=due_reviews,
            learned_count=learned_count,
            total_count=total_count,
            remediation_sections=remediation_sections,
            remediation_atoms=remediation_atoms,
            estimated_minutes=estimated_minutes,
            current_module=current_module,
            current_section=current_section,
            overall_mastery=round(overall_mastery, 1),
            streak_days=streak_days,
        )

    def get_module_summaries(self) -> list[ModuleSummary]:
        """
        Get summary of all modules.

        Returns:
            List of ModuleSummary for modules 1-17
        """
        from src.db.database import engine

        summaries = []

        with engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT
                    s.module_number,
                    COUNT(DISTINCT s.section_id) as total_sections,
                    COUNT(DISTINCT CASE WHEN m.is_completed THEN s.section_id END) as sections_completed,
                    COALESCE(AVG(m.mastery_score), 0) as avg_mastery,
                    COALESCE(SUM(m.atoms_total), 0) as atoms_total,
                    COALESCE(SUM(m.atoms_mastered), 0) as atoms_mastered,
                    COALESCE(SUM(m.atoms_learning), 0) as atoms_learning,
                    COALESCE(SUM(m.atoms_struggling), 0) as atoms_struggling,
                    COALESCE(SUM(m.atoms_new), 0) as atoms_new,
                    COUNT(CASE WHEN m.needs_remediation THEN 1 END) as remediation_count
                FROM ccna_sections s
                LEFT JOIN ccna_section_mastery m
                    ON s.section_id = m.section_id AND m.user_id = :user_id
                WHERE s.level = 2  -- Main sections only for summary
                GROUP BY s.module_number
                ORDER BY s.module_number
            """),
                {"user_id": self.user_id},
            )

            # Module titles
            module_titles = {
                1: "Networking Today",
                2: "Basic Switch and End Device Configuration",
                3: "Protocols and Models",
                4: "Physical Layer",
                5: "Number Systems",
                6: "Data Link Layer",
                7: "Ethernet Switching",
                8: "Network Layer",
                9: "Address Resolution",
                10: "Basic Router Configuration",
                11: "IPv4 Addressing",
                12: "IPv6 Addressing",
                13: "ICMP",
                14: "Transport Layer",
                15: "Application Layer",
                16: "Network Security Fundamentals",
                17: "Build a Small Network",
            }

            for row in result:
                summaries.append(
                    ModuleSummary(
                        module_number=row.module_number,
                        title=module_titles.get(row.module_number, f"Module {row.module_number}"),
                        total_sections=row.total_sections,
                        sections_completed=row.sections_completed or 0,
                        avg_mastery=round(row.avg_mastery or 0, 1),
                        atoms_total=row.atoms_total or 0,
                        atoms_mastered=row.atoms_mastered or 0,
                        atoms_learning=row.atoms_learning or 0,
                        atoms_struggling=row.atoms_struggling or 0,
                        atoms_new=row.atoms_new or 0,
                        sections_needing_remediation=row.remediation_count or 0,
                    )
                )

        return summaries

    def get_section_details(self, module_number: int) -> list[SectionDetail]:
        """
        Get detailed section information for a module.

        Args:
            module_number: Module number (1-17)

        Returns:
            List of SectionDetail with hierarchical structure
        """
        from src.db.database import engine

        with engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT
                    s.section_id,
                    s.title,
                    s.level,
                    s.parent_section_id,
                    COALESCE(m.mastery_score, 0) as mastery_score,
                    COALESCE(m.is_completed, FALSE) as is_completed,
                    COALESCE(m.needs_remediation, FALSE) as needs_remediation,
                    m.remediation_reason,
                    COALESCE(m.atoms_total, 0) as atoms_total,
                    COALESCE(m.atoms_mastered, 0) as atoms_mastered,
                    COALESCE(m.atoms_learning, 0) as atoms_learning,
                    COALESCE(m.atoms_struggling, 0) as atoms_struggling,
                    COALESCE(m.atoms_new, 0) as atoms_new,
                    m.last_review_date
                FROM ccna_sections s
                LEFT JOIN ccna_section_mastery m
                    ON s.section_id = m.section_id AND m.user_id = :user_id
                WHERE s.module_number = :module
                ORDER BY s.display_order
            """),
                {"user_id": self.user_id, "module": module_number},
            )

            # Build hierarchy
            sections_by_id = {}
            main_sections = []

            for row in result:
                detail = SectionDetail(
                    section_id=row.section_id,
                    title=row.title,
                    level=row.level,
                    parent_section_id=row.parent_section_id,
                    mastery_score=round(row.mastery_score, 1),
                    is_mastered=row.is_completed,
                    needs_remediation=row.needs_remediation,
                    remediation_reason=row.remediation_reason,
                    atoms_total=row.atoms_total,
                    atoms_mastered=row.atoms_mastered,
                    atoms_learning=row.atoms_learning,
                    atoms_struggling=row.atoms_struggling,
                    atoms_new=row.atoms_new,
                    last_review_date=row.last_review_date,
                    subsections=[],
                )
                sections_by_id[row.section_id] = detail

                if row.level == 2:
                    main_sections.append(detail)
                elif row.parent_section_id and row.parent_section_id in sections_by_id:
                    sections_by_id[row.parent_section_id].subsections.append(detail)

        return main_sections

    def refresh_mastery(self) -> int:
        """
        Refresh all section mastery scores from atom stats.

        Returns:
            Number of sections updated
        """
        from src.db.database import engine

        with engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT refresh_all_section_mastery(:user_id) as count
            """),
                {"user_id": self.user_id},
            )
            count = result.fetchone().count

            conn.commit()

        logger.info(f"Refreshed mastery for {count} sections")
        return count

    def get_remediation_sections(self) -> list[SectionDetail]:
        """
        Get all sections needing remediation, sorted by priority.

        Returns:
            List of SectionDetail needing remediation
        """
        from src.db.database import engine

        with engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT
                    s.section_id,
                    s.title,
                    s.level,
                    s.parent_section_id,
                    s.module_number,
                    m.mastery_score,
                    m.needs_remediation,
                    m.remediation_reason,
                    m.remediation_priority,
                    m.atoms_total,
                    m.atoms_mastered,
                    m.atoms_learning,
                    m.atoms_struggling,
                    m.atoms_new,
                    m.last_review_date
                FROM ccna_sections s
                JOIN ccna_section_mastery m
                    ON s.section_id = m.section_id AND m.user_id = :user_id
                WHERE m.needs_remediation = TRUE
                ORDER BY m.remediation_priority DESC, m.mastery_score ASC
            """),
                {"user_id": self.user_id},
            )

            sections = []
            for row in result:
                sections.append(
                    SectionDetail(
                        section_id=row.section_id,
                        title=row.title,
                        level=row.level,
                        parent_section_id=row.parent_section_id,
                        mastery_score=round(row.mastery_score or 0, 1),
                        is_mastered=False,
                        needs_remediation=True,
                        remediation_reason=row.remediation_reason,
                        atoms_total=row.atoms_total or 0,
                        atoms_mastered=row.atoms_mastered or 0,
                        atoms_learning=row.atoms_learning or 0,
                        atoms_struggling=row.atoms_struggling or 0,
                        atoms_new=row.atoms_new or 0,
                        last_review_date=row.last_review_date,
                        subsections=[],
                    )
                )

        return sections

    def get_study_stats(self) -> dict:
        """
        Get comprehensive study statistics.

        Returns:
            Dictionary with all stats
        """
        from src.db.database import engine

        with engine.connect() as conn:
            # Overall stats
            overall_result = conn.execute(
                text("""
                SELECT
                    COUNT(*) as total_sections,
                    COUNT(CASE WHEN is_completed THEN 1 END) as completed_sections,
                    AVG(mastery_score) as avg_mastery,
                    SUM(atoms_total) as total_atoms,
                    SUM(atoms_mastered) as atoms_mastered,
                    SUM(atoms_learning) as atoms_learning,
                    SUM(atoms_struggling) as atoms_struggling,
                    SUM(atoms_new) as atoms_new,
                    SUM(total_reviews) as total_reviews
                FROM ccna_section_mastery
                WHERE user_id = :user_id
            """),
                {"user_id": self.user_id},
            )
            overall = overall_result.fetchone()

            # Session history
            sessions_result = conn.execute(
                text("""
                SELECT
                    COUNT(*) as total_sessions,
                    SUM(duration_minutes) as total_minutes,
                    SUM(cards_reviewed) as total_cards,
                    AVG(correct_count::float / NULLIF(correct_count + incorrect_count, 0)) * 100 as avg_accuracy
                FROM ccna_study_sessions
                WHERE user_id = :user_id
            """),
                {"user_id": self.user_id},
            )
            sessions = sessions_result.fetchone()

        return {
            "sections": {
                "total": overall.total_sections or 0,
                "completed": overall.completed_sections or 0,
                "completion_rate": round(
                    (overall.completed_sections or 0) / max(overall.total_sections or 1, 1) * 100, 1
                ),
            },
            "atoms": {
                "total": overall.total_atoms or 0,
                "mastered": overall.atoms_mastered or 0,
                "learning": overall.atoms_learning or 0,
                "struggling": overall.atoms_struggling or 0,
                "new": overall.atoms_new or 0,
            },
            "mastery": {
                "average": round(overall.avg_mastery or 0, 1),
                "total_reviews": overall.total_reviews or 0,
            },
            "sessions": {
                "total": sessions.total_sessions or 0,
                "total_minutes": sessions.total_minutes or 0,
                "total_cards_reviewed": sessions.total_cards or 0,
                "avg_accuracy": round(sessions.avg_accuracy or 0, 1),
            },
        }

    def get_expanded_module_atoms(
        self, module_number: int, max_depth: int = 3
    ) -> ExpandedModuleAtoms:
        """
        Get all atoms for a module PLUS prerequisite-linked atoms (max N hops).

        This implements cross-module expansion via the concept prerequisite graph.
        When you select Module 5, it finds:
        1. All concepts in Module 5
        2. Prerequisites from earlier modules (up to max_depth hops back)
        3. Dependents from later modules (up to max_depth hops forward)

        The result is split by destination:
        - anki_atoms: flashcard + cloze → sync to Anki
        - quiz_atoms: mcq, true_false, matching, parsons → present in NLS

        Args:
            module_number: Target module (1-17)
            max_depth: Maximum hops in prerequisite chain (default 3)

        Returns:
            ExpandedModuleAtoms with grouped atoms and metadata
        """
        from src.db.database import engine

        result = ExpandedModuleAtoms(
            target_module=module_number,
            max_depth=max_depth,
        )

        with engine.connect() as conn:
            # Recursive CTE to expand concept chain up to max_depth hops
            # This traverses both upstream (prerequisites) and downstream (dependents)
            atoms_result = conn.execute(
                text("""
                WITH RECURSIVE concept_chain AS (
                    -- Base case: concepts in the target module (depth 0)
                    SELECT DISTINCT
                        ca.concept_id,
                        0 as depth,
                        'origin' as direction
                    FROM learning_atoms ca
                    JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
                    WHERE cs.module_number = :module
                      AND ca.concept_id IS NOT NULL

                    UNION

                    -- Upstream: follow prerequisites (source → target)
                    SELECT DISTINCT
                        ep.target_concept_id,
                        cc.depth + 1,
                        'upstream'
                    FROM explicit_prerequisites ep
                    JOIN concept_chain cc ON ep.source_concept_id = cc.concept_id
                    WHERE cc.depth < :max_depth

                    UNION

                    -- Downstream: follow dependents (target → source)
                    SELECT DISTINCT
                        ep.source_concept_id,
                        cc.depth + 1,
                        'downstream'
                    FROM explicit_prerequisites ep
                    JOIN concept_chain cc ON ep.target_concept_id = cc.concept_id
                    WHERE cc.depth < :max_depth
                )
                SELECT DISTINCT
                    ca.id,
                    ca.card_id,
                    ca.front,
                    ca.back,
                    ca.atom_type,
                    ca.concept_id,
                    ca.source,
                    ca.bloom_level,
                    ca.clt_load,
                    ca.quality_score,
                    ca.ccna_section_id,
                    cs.module_number,
                    cs.title as section_title,
                    cc_chain.depth,
                    cc_chain.direction,
                    -- Include mastery data for prioritization
                    ca.anki_stability,
                    ca.anki_difficulty,
                    ca.anki_lapses
                FROM concept_chain cc_chain
                JOIN learning_atoms ca ON ca.concept_id = cc_chain.concept_id
                JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
                WHERE ca.front IS NOT NULL AND ca.front != ''
                ORDER BY cc_chain.depth, cs.module_number, ca.atom_type
            """),
                {"module": module_number, "max_depth": max_depth},
            )

            modules_set = set()
            concepts_set = set()
            max_chain_depth = 0

            for row in atoms_result:
                atom_dict = {
                    "id": row.id,
                    "card_id": row.card_id,
                    "front": row.front,
                    "back": row.back,
                    "atom_type": row.atom_type,
                    "concept_id": str(row.concept_id) if row.concept_id else None,
                    "source": row.source,
                    "bloom_level": row.bloom_level,
                    "clt_load": row.clt_load,
                    "quality_score": float(row.quality_score) if row.quality_score else 0,
                    "ccna_section_id": row.ccna_section_id,
                    "module_number": row.module_number,
                    "section_title": row.section_title,
                    "depth": row.depth,
                    "direction": row.direction,
                    "anki_stability": row.anki_stability,
                    "anki_difficulty": row.anki_difficulty,
                    "anki_lapses": row.anki_lapses,
                }

                modules_set.add(row.module_number)
                if row.concept_id:
                    concepts_set.add(row.concept_id)
                max_chain_depth = max(max_chain_depth, row.depth)

                # Route by atom type
                if row.atom_type in ("flashcard", "cloze"):
                    result.anki_atoms.append(atom_dict)
                else:
                    result.quiz_atoms.append(atom_dict)

                # Track low-stability atoms as priority
                stability = row.anki_stability or 0
                lapses = row.anki_lapses or 0
                if stability < 7 or lapses >= 2:
                    result.priority_atoms.append(atom_dict)

            result.modules_touched = sorted(modules_set)
            result.concept_count = len(concepts_set)
            result.prerequisite_chain_depth = max_chain_depth

        logger.info(
            f"Expanded Module {module_number}: "
            f"{len(result.anki_atoms)} Anki atoms, "
            f"{len(result.quiz_atoms)} quiz atoms, "
            f"{result.concept_count} concepts across {len(result.modules_touched)} modules "
            f"(max depth {max_chain_depth})"
        )

        return result

    def get_multi_module_activity_path(self, module_numbers: list[int], max_depth: int = 3) -> dict:
        """
        Get activity path for multiple modules with prerequisite ordering.

        This is the core method for commands like:
            module 1 2 3 --expand

        Returns a structured learning path with:
        - Anki jobs (flashcard + cloze) ordered by prerequisites
        - NLS quiz jobs (mcq, tf, matching, parsons) with CLT metadata
        - Activity suggestions based on current mastery

        Args:
            module_numbers: List of target modules (e.g., [1, 2, 3])
            max_depth: Maximum hops in prerequisite chain

        Returns:
            Dict with activity path, jobs, and suggestions
        """
        from src.db.database import engine

        result = {
            "target_modules": module_numbers,
            "max_depth": max_depth,
            "anki_jobs": [],
            "nls_jobs": [],
            "activity_path": [],
            "modules_touched": [],
            "concept_count": 0,
            "summary": {},
        }

        with engine.connect() as conn:
            # Use simple query - prerequisite expansion requires explicit_prerequisites table
            # which may not be populated yet
            try:
                atoms = self._simple_module_atoms(conn, module_numbers)
            except Exception as e:
                logger.error(f"Module atoms query failed: {e}")
                conn.rollback()
                atoms = []

            if not atoms:
                logger.warning(f"No atoms found for modules {module_numbers}")
                return result

            # Process atoms into jobs and activity path
            modules_set = set()
            concepts_set = set()
            anki_by_module = {}
            nls_by_type = {"mcq": [], "true_false": [], "matching": [], "parsons": []}

            for atom in atoms:
                modules_set.add(atom.get("module_number", 0))
                if atom.get("concept_id"):
                    concepts_set.add(atom["concept_id"])

                activity = {
                    "atom_id": str(atom.get("atom_id", "")),
                    "card_id": atom.get("card_id"),
                    "front": atom.get("front", "")[:100],  # Truncate for display
                    "atom_type": atom.get("atom_type"),
                    "module_number": atom.get("module_number"),
                    "section_id": atom.get("section_id"),
                    "depth": atom.get("depth", 0),
                    "direction": atom.get("direction", "origin"),
                    "destination": atom.get("destination"),
                    "difficulty": atom.get("difficulty"),
                    "clt_intrinsic": atom.get("clt_intrinsic"),
                    "clt_extraneous": atom.get("clt_extraneous"),
                    "clt_germane": atom.get("clt_germane"),
                }

                result["activity_path"].append(activity)

                # Route to appropriate job list
                if atom.get("destination") == "anki" or atom.get("atom_type") in (
                    "flashcard",
                    "cloze",
                ):
                    mod = atom.get("module_number", 0)
                    anki_by_module.setdefault(mod, []).append(atom)
                else:
                    atype = atom.get("atom_type", "mcq")
                    if atype in nls_by_type:
                        nls_by_type[atype].append(atom)

            # Build Anki jobs (grouped by module, ordered by prerequisites)
            for mod in sorted(anki_by_module.keys()):
                atoms_list = anki_by_module[mod]
                fc_count = sum(1 for a in atoms_list if a.get("atom_type") == "flashcard")
                cl_count = sum(1 for a in atoms_list if a.get("atom_type") == "cloze")
                is_target = mod in module_numbers

                result["anki_jobs"].append(
                    {
                        "module": mod,
                        "is_target_module": is_target,
                        "flashcard_count": fc_count,
                        "cloze_count": cl_count,
                        "total": len(atoms_list),
                        "anki_query": f"deck:CCNA* tag:module:{mod}",
                        "note_ids": [
                            a.get("anki_note_id") for a in atoms_list if a.get("anki_note_id")
                        ],
                    }
                )

            # Build NLS quiz jobs (grouped by type with CLT metadata)
            for qtype, atoms_list in nls_by_type.items():
                if atoms_list:
                    avg_clt = sum(
                        (a.get("clt_intrinsic") or 2)
                        + (a.get("clt_extraneous") or 2)
                        + (a.get("clt_germane") or 3)
                        for a in atoms_list
                    ) / (len(atoms_list) * 3)

                    result["nls_jobs"].append(
                        {
                            "quiz_type": qtype,
                            "count": len(atoms_list),
                            "avg_clt_load": round(avg_clt, 1),
                            "modules_included": sorted(
                                set(a.get("module_number", 0) for a in atoms_list)
                            ),
                        }
                    )

            result["modules_touched"] = sorted(modules_set)
            result["concept_count"] = len(concepts_set)

            # Summary statistics
            result["summary"] = {
                "total_atoms": len(atoms),
                "anki_total": sum(j["total"] for j in result["anki_jobs"]),
                "nls_total": sum(j["count"] for j in result["nls_jobs"]),
                "prerequisite_modules": [
                    m for m in result["modules_touched"] if m not in module_numbers
                ],
                "target_modules": module_numbers,
            }

        logger.info(
            f"Activity path for modules {module_numbers}: "
            f"{result['summary']['anki_total']} Anki, {result['summary']['nls_total']} NLS, "
            f"{result['concept_count']} concepts across {len(result['modules_touched'])} modules"
        )

        return result

    def _fallback_multi_module_expansion(
        self, conn, module_numbers: list[int], max_depth: int
    ) -> list[dict]:
        """Fallback expansion using prerequisite graph if available."""
        # Convert module list to SQL-safe format
        modules_str = ",".join(str(m) for m in module_numbers)

        # First check if explicit_prerequisites table exists
        try:
            check = conn.execute(
                text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'explicit_prerequisites'
                )
            """)
            )
            has_prereqs = check.scalar()
        except Exception:
            has_prereqs = False

        if not has_prereqs or max_depth == 0:
            # No prerequisite table or no expansion requested - use simple query
            return self._simple_module_atoms(conn, module_numbers)

        # Full recursive expansion with prerequisites
        result = conn.execute(
            text(f"""
            WITH RECURSIVE concept_chain AS (
                SELECT DISTINCT
                    ca.concept_id,
                    0 as depth,
                    'origin'::text as direction
                FROM learning_atoms ca
                JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
                WHERE cs.module_number IN ({modules_str})
                  AND ca.concept_id IS NOT NULL

                UNION

                SELECT DISTINCT
                    ep.target_concept_id,
                    cc.depth + 1,
                    'upstream'::text
                FROM explicit_prerequisites ep
                JOIN concept_chain cc ON ep.source_concept_id = cc.concept_id
                WHERE cc.depth < :max_depth

                UNION

                SELECT DISTINCT
                    ep.source_concept_id,
                    cc.depth + 1,
                    'downstream'::text
                FROM explicit_prerequisites ep
                JOIN concept_chain cc ON ep.target_concept_id = cc.concept_id
                WHERE cc.depth < :max_depth
            )
            SELECT
                ca.id as atom_id,
                ca.card_id,
                ca.front,
                ca.back,
                ca.atom_type,
                ca.concept_id,
                cs.module_number,
                cs.section_id,
                cc_chain.depth,
                cc_chain.direction,
                CASE WHEN ca.atom_type IN ('flashcard', 'cloze') THEN 'anki' ELSE 'nls' END as destination,
                NULL::smallint as clt_intrinsic,
                NULL::smallint as clt_extraneous,
                NULL::smallint as clt_germane,
                NULL::smallint as difficulty,
                ca.anki_note_id
            FROM concept_chain cc_chain
            JOIN learning_atoms ca ON ca.concept_id = cc_chain.concept_id
            JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
            WHERE ca.front IS NOT NULL AND ca.front != ''
            ORDER BY cc_chain.depth DESC, cs.module_number, ca.atom_type
        """),
            {"max_depth": max_depth},
        )

        return [dict(row._mapping) for row in result.fetchall()]

    def _simple_module_atoms(self, conn, module_numbers: list[int]) -> list[dict]:
        """Simple query to get all atoms for modules without prerequisite expansion."""
        modules_str = ",".join(str(m) for m in module_numbers)

        result = conn.execute(
            text(f"""
            SELECT
                ca.id as atom_id,
                ca.card_id,
                ca.front,
                ca.back,
                ca.atom_type,
                ca.concept_id,
                cs.module_number,
                cs.section_id,
                0 as depth,
                'origin'::text as direction,
                CASE WHEN ca.atom_type IN ('flashcard', 'cloze') THEN 'anki' ELSE 'nls' END as destination,
                NULL::smallint as clt_intrinsic,
                NULL::smallint as clt_extraneous,
                NULL::smallint as clt_germane,
                NULL::smallint as difficulty,
                ca.anki_note_id
            FROM learning_atoms ca
            JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
            WHERE cs.module_number IN ({modules_str})
              AND ca.front IS NOT NULL
              AND ca.front != ''
            ORDER BY cs.module_number, ca.atom_type
        """)
        )

        return [dict(row._mapping) for row in result.fetchall()]

    def generate_learning_suggestions(self, activity_path: dict) -> list[dict]:
        """
        Generate learning activity suggestions based on the activity path.

        Returns ordered suggestions like:
        1. "Review 45 flashcards in Module 3 (prerequisites for Module 5)"
        2. "Complete 20 MCQ questions covering Network Layer concepts"
        3. "Do 15 True/False on IPv4 basics before advancing"
        """
        suggestions = []

        # Anki suggestions (prerequisites first)
        prereq_modules = activity_path.get("summary", {}).get("prerequisite_modules", [])
        target_modules = activity_path.get("summary", {}).get("target_modules", [])

        for job in activity_path.get("anki_jobs", []):
            if job["module"] in prereq_modules:
                suggestions.append(
                    {
                        "priority": 1,
                        "type": "anki",
                        "action": f"Review {job['total']} cards in Module {job['module']}",
                        "reason": f"Prerequisites for Module(s) {target_modules}",
                        "query": job["anki_query"],
                        "count": job["total"],
                    }
                )
            elif job["is_target_module"]:
                suggestions.append(
                    {
                        "priority": 2,
                        "type": "anki",
                        "action": f"Learn {job['total']} new cards in Module {job['module']}",
                        "reason": "Target module content",
                        "query": job["anki_query"],
                        "count": job["total"],
                    }
                )

        # NLS quiz suggestions (CLT-balanced)
        for job in activity_path.get("nls_jobs", []):
            clt_desc = "moderate" if job["avg_clt_load"] < 3 else "challenging"
            suggestions.append(
                {
                    "priority": 3,
                    "type": "nls_quiz",
                    "action": f"Complete {job['count']} {job['quiz_type'].upper()} questions",
                    "reason": f"{clt_desc.title()} CLT load ({job['avg_clt_load']}), covers modules {job['modules_included']}",
                    "quiz_type": job["quiz_type"],
                    "count": job["count"],
                }
            )

        # Sort by priority
        suggestions.sort(key=lambda x: x["priority"])

        return suggestions

    # =========================================================================
    # SESSION METHODS FOR CORTEX CLI
    # =========================================================================

    def get_war_session(
        self,
        modules: list[int],
        limit: int = 50,
        prioritize_types: list[str] | None = None,
    ) -> list[dict]:
        """
        Get atoms for War Mode - aggressive mastery, ignores FSRS due dates.

        War Mode prioritizes:
        1. NUMERIC and PARSONS (highest cognitive load)
        2. MCQ and TRUE_FALSE
        3. Low stability / high lapse atoms (weakest areas)
        4. Specified modules only (typically 11-17 for CCNA exam prep)

        Args:
            modules: List of module numbers to include
            limit: Maximum atoms to return
            prioritize_types: Atom types to prioritize (default: numeric, parsons, mcq)

        Returns:
            List of atom dicts ready for presentation
        """
        from src.db.database import engine

        if prioritize_types is None:
            prioritize_types = ["numeric", "parsons", "mcq", "true_false"]

        modules_str = ",".join(str(m) for m in modules)
        types_list = prioritize_types

        with engine.connect() as conn:
            result = conn.execute(
                text(f"""
                SELECT
                    ca.id,
                    ca.card_id,
                    ca.atom_type,
                    ca.front,
                    ca.back,
                    ca.concept_id,
                    ca.ccna_section_id,
                    cs.module_number,
                    cs.title as section_title,
                    cc.name as concept_name,
                    COALESCE(ca.anki_difficulty, 0.5) as difficulty,
                    COALESCE(ca.anki_stability, 0) as stability,
                    COALESCE(ca.anki_lapses, 0) as lapses,
                    COALESCE(ca.anki_review_count, 0) as review_count
                FROM learning_atoms ca
                JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
                LEFT JOIN concepts cc ON ca.concept_id = cc.id
                WHERE cs.module_number IN ({modules_str})
                  AND ca.atom_type = ANY(:types)
                  AND ca.front IS NOT NULL
                  AND ca.front != ''
                ORDER BY
                    -- Prioritize by type order (numeric > parsons > mcq > tf)
                    CASE ca.atom_type
                        WHEN 'numeric' THEN 1
                        WHEN 'parsons' THEN 2
                        WHEN 'mcq' THEN 3
                        WHEN 'true_false' THEN 4
                        ELSE 5
                    END,
                    -- Then by weakness (low stability, high lapses)
                    COALESCE(ca.anki_stability, 0) ASC,
                    COALESCE(ca.anki_lapses, 0) DESC,
                    -- Finally randomize within same priority
                    RANDOM()
                LIMIT :limit
            """),
                {"types": types_list, "limit": limit},
            )

            atoms = []
            for row in result:
                atoms.append(
                    {
                        "id": str(row.id),
                        "card_id": row.card_id,
                        "atom_type": row.atom_type,
                        "front": row.front,
                        "back": row.back or "",
                        "concept_id": str(row.concept_id) if row.concept_id else None,
                        "section_id": row.ccna_section_id,
                        "module_number": row.module_number,
                        "section_title": row.section_title,
                        "concept_name": row.concept_name or "Unknown",
                        "difficulty": row.difficulty,
                        "stability": row.stability,
                        "lapses": row.lapses,
                        "review_count": row.review_count,
                    }
                )

        logger.info(
            f"War session: {len(atoms)} atoms from modules {modules} (types: {prioritize_types})"
        )
        return atoms

    def get_adaptive_session(
        self,
        limit: int = 20,
        include_new: bool = True,
        interleave: bool = True,
        use_struggles: bool = True,
        exclude_ids: list[str] | None = None,
        modules: list[int] | None = None,
        sections: list[str] | None = None,
        source_file: str | None = None,
    ) -> list[dict]:
        """
        Get atoms for Adaptive Mode - uses struggle priority and FSRS scheduling.

        Adaptive Mode:
        1. Prioritizes atoms from struggle zones (v_struggle_priority view)
        2. Mixes in FSRS due reviews
        3. Adds new atoms for progressive learning
        4. Interleaves across modules for better retention

        Args:
            limit: Maximum atoms to return
            include_new: Whether to include never-reviewed atoms
            interleave: Whether to interleave across modules
            use_struggles: Whether to prioritize struggle zones (default True)
            exclude_ids: List of atom IDs to exclude from the session
            modules: Filter to specific module numbers (e.g., [1, 2, 3])
            sections: Filter to specific section IDs (e.g., ["11.4", "11.5"])
            source_file: Filter to specific source file (e.g., "ITNFinalPacketTracer.txt")

        Returns:
            List of atom dicts ordered for optimal learning
        """
        from src.db.database import engine

        with engine.connect() as conn:
            struggle_atoms = []
            due_atoms = []
            new_atoms = []
            exclude_ids = exclude_ids or []

            # Log active filters if any are set
            if modules or sections or source_file:
                logger.debug(f"Adaptive session filters: modules={modules}, sections={sections}, source_file={source_file}")

            # 1. Get struggle-weighted atoms first (if enabled and table exists)
            if use_struggles:
                try:
                    # Build filter clause for struggle query (uses vsp.* aliases)
                    struggle_filter_parts = []
                    struggle_filter_params = {}
                    if modules:
                        struggle_filter_parts.append("vsp.module_number = ANY(:filter_modules)")
                        struggle_filter_params["filter_modules"] = modules
                    if sections:
                        sec_conditions = []
                        for i, sec in enumerate(sections):
                            p = f"sf_sec_{i}"
                            sec_conditions.append(f"(vsp.section_id = :{p} OR vsp.section_id LIKE :{p}_pfx)")
                            struggle_filter_params[p] = sec
                            struggle_filter_params[f"{p}_pfx"] = f"{sec}.%"
                        if sec_conditions:
                            struggle_filter_parts.append(f"({' OR '.join(sec_conditions)})")
                    if source_file:
                        struggle_filter_parts.append("la.source_file = :filter_source_file")
                        struggle_filter_params["filter_source_file"] = source_file

                    struggle_filter_clause = (" AND " + " AND ".join(struggle_filter_parts)) if struggle_filter_parts else ""

                    struggle_query = f"""
                        SELECT
                            vsp.atom_id as id,
                            vsp.card_id,
                            vsp.atom_type,
                            vsp.front,
                            vsp.back,
                            la.concept_id,
                            vsp.section_id as ccna_section_id,
                            vsp.module_number,
                            vsp.section_title,
                            cc.name as concept_name,
                            vsp.difficulty,
                            vsp.stability,
                            COALESCE(la.anki_lapses, 0) as lapses,
                            COALESCE(la.anki_review_count, 0) as review_count,
                            la.anki_due_date,
                            'struggle' as source,
                            vsp.priority_score
                        FROM v_struggle_priority vsp
                        JOIN learning_atoms la ON vsp.atom_id = la.id
                        LEFT JOIN concepts cc ON la.concept_id = cc.id
                        WHERE vsp.atom_type IN ('mcq', 'true_false', 'parsons', 'matching')
                          AND vsp.front IS NOT NULL
                          AND vsp.front != ''
                          AND vsp.struggle_weight >= 0.5
                          AND (la.id NOT IN :exclude_ids OR :exclude_ids IS NULL)
                          {struggle_filter_clause}
                        ORDER BY vsp.priority_score DESC
                        LIMIT :struggle_limit
                    """
                    struggle_limit = limit // 2  # Half from struggles
                    query_params = {"struggle_limit": struggle_limit, "exclude_ids": tuple(exclude_ids) or (None,)}
                    query_params.update(struggle_filter_params)
                    result = conn.execute(text(struggle_query), query_params)
                    struggle_atoms = [dict(row._mapping) for row in result.fetchall()]
                    logger.debug(f"Got {len(struggle_atoms)} struggle-weighted atoms")
                except Exception as e:
                    logger.warning(f"Could not query v_struggle_priority (run struggles --import?): {e}")
                    struggle_atoms = []

            # 2. Get FSRS due reviews (excluding ones already in struggle set)
            current_exclude_ids = exclude_ids + [str(a.get("id")) for a in struggle_atoms]
            remaining_due = limit - len(struggle_atoms)

            if remaining_due > 0:
                # Build filter clause for due query (uses ca.* and cs.* aliases)
                due_filter_parts = []
                due_filter_params = {}
                if modules:
                    due_filter_parts.append("cs.module_number = ANY(:due_filter_modules)")
                    due_filter_params["due_filter_modules"] = modules
                if sections:
                    sec_conditions = []
                    for i, sec in enumerate(sections):
                        p = f"df_sec_{i}"
                        sec_conditions.append(f"(ca.ccna_section_id = :{p} OR ca.ccna_section_id LIKE :{p}_pfx)")
                        due_filter_params[p] = sec
                        due_filter_params[f"{p}_pfx"] = f"{sec}.%"
                    if sec_conditions:
                        due_filter_parts.append(f"({' OR '.join(sec_conditions)})")
                if source_file:
                    due_filter_parts.append("ca.source_file = :due_filter_source_file")
                    due_filter_params["due_filter_source_file"] = source_file

                due_filter_clause = (" AND " + " AND ".join(due_filter_parts)) if due_filter_parts else ""

                due_query = f"""
                    SELECT
                        ca.id,
                        ca.card_id,
                        ca.atom_type,
                        ca.front,
                        ca.back,
                        ca.concept_id,
                        ca.ccna_section_id,
                        cs.module_number,
                        cs.title as section_title,
                        cc.name as concept_name,
                        COALESCE(ca.anki_difficulty, 0.5) as difficulty,
                        COALESCE(ca.anki_stability, 0) as stability,
                        COALESCE(ca.anki_lapses, 0) as lapses,
                        COALESCE(ca.anki_review_count, 0) as review_count,
                        ca.anki_due_date,
                        'due' as source
                    FROM learning_atoms ca
                    JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
                    LEFT JOIN concepts cc ON ca.concept_id = cc.id
                    WHERE ca.atom_type IN ('mcq', 'true_false', 'parsons', 'matching')
                      AND ca.front IS NOT NULL
                      AND ca.front != ''
                      AND ca.anki_due_date IS NOT NULL
                      AND ca.anki_due_date <= CURRENT_DATE
                      AND (ca.id NOT IN :exclude_ids OR :exclude_ids IS NULL)
                      {due_filter_clause}
                    ORDER BY ca.anki_due_date ASC, ca.anki_stability ASC
                    LIMIT :due_limit
                """
                due_limit = remaining_due if not include_new else int(remaining_due * 0.7)
                due_query_params = {"due_limit": due_limit, "exclude_ids": tuple(current_exclude_ids) or (None,)}
                due_query_params.update(due_filter_params)
                due_result = conn.execute(text(due_query), due_query_params)
                due_atoms = [dict(row._mapping) for row in due_result.fetchall()]

            # 3. Get new atoms if requested
            current_exclude_ids.extend([str(a.get("id")) for a in due_atoms])
            remaining_new = limit - len(struggle_atoms) - len(due_atoms)

            if include_new and remaining_new > 0:
                # Build filter clause for new query (uses ca.* and cs.* aliases)
                new_filter_parts = []
                new_filter_params = {}
                if modules:
                    new_filter_parts.append("cs.module_number = ANY(:new_filter_modules)")
                    new_filter_params["new_filter_modules"] = modules
                if sections:
                    sec_conditions = []
                    for i, sec in enumerate(sections):
                        p = f"nf_sec_{i}"
                        sec_conditions.append(f"(ca.ccna_section_id = :{p} OR ca.ccna_section_id LIKE :{p}_pfx)")
                        new_filter_params[p] = sec
                        new_filter_params[f"{p}_pfx"] = f"{sec}.%"
                    if sec_conditions:
                        new_filter_parts.append(f"({' OR '.join(sec_conditions)})")
                if source_file:
                    new_filter_parts.append("ca.source_file = :new_filter_source_file")
                    new_filter_params["new_filter_source_file"] = source_file

                new_filter_clause = (" AND " + " AND ".join(new_filter_parts)) if new_filter_parts else ""

                new_query = f"""
                    SELECT
                        ca.id,
                        ca.card_id,
                        ca.atom_type,
                        ca.front,
                        ca.back,
                        ca.concept_id,
                        ca.ccna_section_id,
                        cs.module_number,
                        cs.title as section_title,
                        cc.name as concept_name,
                        COALESCE(ca.anki_difficulty, 0.5) as difficulty,
                        0 as stability,
                        0 as lapses,
                        0 as review_count,
                        NULL as anki_due_date,
                        'new' as source
                    FROM learning_atoms ca
                    JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
                    LEFT JOIN concepts cc ON ca.concept_id = cc.id
                    WHERE ca.atom_type IN ('mcq', 'true_false', 'parsons', 'matching')
                      AND ca.front IS NOT NULL
                      AND ca.front != ''
                      AND (ca.anki_review_count IS NULL OR ca.anki_review_count = 0)
                      AND (ca.id NOT IN :exclude_ids OR :exclude_ids IS NULL)
                      {new_filter_clause}
                    ORDER BY cs.display_order, RANDOM()
                    LIMIT :new_limit
                """
                new_query_params = {"new_limit": remaining_new, "exclude_ids": tuple(current_exclude_ids) or (None,)}
                new_query_params.update(new_filter_params)
                new_result = conn.execute(text(new_query), new_query_params)
                new_atoms = [dict(row._mapping) for row in new_result.fetchall()]

            # Combine: struggles first, then due, then new
            all_atoms = struggle_atoms + due_atoms + new_atoms

            # Apply type quotas for balanced distribution
            all_atoms = self._apply_type_quotas(all_atoms, limit)

            if interleave and len(all_atoms) > 1:
                all_atoms = self._interleave_atoms_by_type(all_atoms)

            # Convert to standard format
            atoms = []
            for row in all_atoms:
                atom = {
                    "id": str(row["id"]),
                    "card_id": row["card_id"],
                    "atom_type": row["atom_type"],
                    "front": row["front"],
                    "back": row["back"] or "",
                    "concept_id": str(row["concept_id"]) if row.get("concept_id") else None,
                    "section_id": row.get("ccna_section_id") or row.get("section_id"),
                    "module_number": row["module_number"],
                    "section_title": row["section_title"],
                    "concept_name": row["concept_name"] or "Unknown",
                    "difficulty": row["difficulty"],
                    "stability": row["stability"],
                    "lapses": row["lapses"],
                    "review_count": row["review_count"],
                    "source": row.get("source", "unknown"),
                }
                # Include quiz content if available (for MCQs with proper options)
                if row.get("quiz_content"):
                    atom["quiz_content"] = row["quiz_content"]
                atoms.append(atom)

        logger.debug(
            f"Adaptive session: {len(atoms)} atoms "
            f"({len(struggle_atoms)} struggle, {len(due_atoms)} due, {len(new_atoms)} new)"
        )
        return atoms

    def _interleave_atoms(self, atoms: list[dict]) -> list[dict]:
        """
        Interleave atoms by module and type for optimal learning.

        Implements spaced interleaving - avoids presenting
        consecutive atoms from the same module or of the same type.
        """
        if len(atoms) <= 1:
            return atoms

        # Group by module
        by_module: dict[int, list] = {}
        for atom in atoms:
            mod = atom.get("module_number", 0)
            by_module.setdefault(mod, []).append(atom)

        # Round-robin interleave
        result = []
        modules = list(by_module.keys())
        while any(by_module.values()):
            for mod in modules:
                if by_module.get(mod):
                    result.append(by_module[mod].pop(0))

        return result

    def _apply_type_quotas(self, atoms: list[dict], limit: int) -> list[dict]:
        """
        Apply question type quotas to ensure balanced distribution.

        Uses TYPE_QUOTAS from adaptive.models to calculate target counts
        for each question type (mcq, true_false, parsons, matching).

        Args:
            atoms: List of atom dicts to filter
            limit: Target session size

        Returns:
            Filtered list with balanced type distribution
        """
        if not atoms:
            return atoms

        # Group atoms by type
        by_type: dict[str, list[dict]] = {}
        for atom in atoms:
            atype = atom.get("atom_type", "unknown")
            by_type.setdefault(atype, []).append(atom)

        # Calculate target counts based on quotas
        targets = {atype: max(int(limit * quota), TYPE_MINIMUM.get(atype, 1))
                   for atype, quota in TYPE_QUOTAS.items()}

        # Log available vs target
        available = {atype: len(by_type.get(atype, [])) for atype in TYPE_QUOTAS.keys()}
        logger.debug(f"Type quota targets: {targets}, available: {available}")

        # Select atoms up to quota for each type
        selected: list[dict] = []
        shortfall = 0

        for atype, target in targets.items():
            type_atoms = by_type.get(atype, [])
            count = min(len(type_atoms), target)
            selected.extend(type_atoms[:count])
            shortfall += target - count

        # Fill shortfall from any available type (prefer MCQ for thinking)
        if shortfall > 0:
            remaining = []
            for atype in ["mcq", "matching", "true_false", "parsons"]:
                type_atoms = by_type.get(atype, [])
                already_selected = targets.get(atype, 0)
                remaining.extend(type_atoms[already_selected:])

            selected.extend(remaining[:shortfall])

        # Log final distribution
        final_dist = {}
        for atom in selected:
            atype = atom.get("atom_type", "unknown")
            final_dist[atype] = final_dist.get(atype, 0) + 1
        logger.debug(f"Type-balanced session: {final_dist}")

        return selected[:limit]

    def _interleave_atoms_by_type(self, atoms: list[dict]) -> list[dict]:
        """
        Interleave atoms by type to prevent consecutive same-type questions.

        Uses round-robin selection across atom types for optimal
        cognitive diversity and reduced fatigue.

        Args:
            atoms: List of atom dicts to interleave

        Returns:
            Reordered list with type-based interleaving
        """
        if len(atoms) <= 1:
            return atoms

        # Group by type
        by_type: dict[str, list[dict]] = {}
        for atom in atoms:
            atype = atom.get("atom_type", "unknown")
            by_type.setdefault(atype, []).append(atom)

        # Shuffle within each type group for variety
        import random
        for type_atoms in by_type.values():
            random.shuffle(type_atoms)

        # Round-robin interleave by type
        result = []
        type_order = ["mcq", "matching", "true_false", "parsons"]  # Conceptual first
        types_with_atoms = [t for t in type_order if by_type.get(t)]

        while any(by_type.get(t) for t in types_with_atoms):
            for atype in types_with_atoms:
                if by_type.get(atype):
                    result.append(by_type[atype].pop(0))

        return result

    def record_interaction(
        self,
        atom_id: str,
        is_correct: bool,
        response_time_ms: int,
        user_answer: str = "",
        session_type: str = "cortex",
        atom_type: str = "",
    ) -> dict:
        """
        Record a study interaction and update mastery metrics.

        This is the SINGLE entry point for all study results.
        Updates:
        1. atom_responses table (raw interaction log)
        2. learning_atoms FSRS fields (stability, difficulty, due_date)
        3. ccna_section_mastery aggregate scores
        4. Transfer testing (accuracy_by_type, memorization detection)

        Args:
            atom_id: UUID of the atom
            is_correct: Whether the answer was correct
            response_time_ms: Time taken to answer in milliseconds
            user_answer: The user's answer (for logging)
            session_type: Type of session (cortex, war, adaptive, anki)
            atom_type: Question type (mcq, true_false, parsons, matching)

        Returns:
            Dict with updated mastery info
        """
        from src.db.database import engine

        result = {
            "atom_id": atom_id,
            "is_correct": is_correct,
            "mastery_delta": 0.0,
            "new_stability": 0.0,
            "next_due": None,
        }

        with engine.connect() as conn:
            # 1. Record raw interaction
            try:
                conn.execute(
                    text("""
                    INSERT INTO atom_responses (
                        atom_id, user_id, is_correct, response_time_ms,
                        user_answer, responded_at
                    ) VALUES (
                        :atom_id, :user_id, :is_correct, :response_time,
                        :user_answer, NOW()
                    )
                """),
                    {
                        "atom_id": atom_id,
                        "user_id": self.user_id,
                        "is_correct": is_correct,
                        "response_time": response_time_ms,
                        "user_answer": user_answer[:500] if user_answer else "",
                    },
                )
                conn.commit()
            except Exception as e:
                logger.debug(f"Could not record response (table may not exist): {e}")
                conn.rollback()

            # 2. Update FSRS-like metrics on learning_atoms
            # Simplified FSRS: stability grows on correct, shrinks on incorrect
            try:
                if is_correct:
                    # Correct: increase stability, decrease difficulty
                    conn.execute(
                        text("""
                        UPDATE learning_atoms
                        SET
                            anki_stability = LEAST(COALESCE(anki_stability, 1) * 2.5, 365),
                            anki_difficulty = GREATEST(COALESCE(anki_difficulty, 0.3) - 0.05, 0.1),
                            anki_review_count = COALESCE(anki_review_count, 0) + 1,
                            anki_due_date = CURRENT_DATE + INTERVAL '1 day' * LEAST(COALESCE(anki_stability, 1) * 2.5, 365)::int,
                            updated_at = NOW()
                        WHERE id = :atom_id
                        RETURNING anki_stability, anki_due_date
                    """),
                        {"atom_id": atom_id},
                    )
                else:
                    # Incorrect: reset stability, increase difficulty, increment lapses
                    conn.execute(
                        text("""
                        UPDATE learning_atoms
                        SET
                            anki_stability = GREATEST(COALESCE(anki_stability, 1) * 0.5, 1),
                            anki_difficulty = LEAST(COALESCE(anki_difficulty, 0.3) + 0.1, 1.0),
                            anki_lapses = COALESCE(anki_lapses, 0) + 1,
                            anki_review_count = COALESCE(anki_review_count, 0) + 1,
                            anki_due_date = CURRENT_DATE + INTERVAL '1 day',
                            updated_at = NOW()
                        WHERE id = :atom_id
                        RETURNING anki_stability, anki_due_date
                    """),
                        {"atom_id": atom_id},
                    )

                # Fetch updated values
                updated = conn.execute(
                    text("""
                    SELECT anki_stability, anki_due_date, ccna_section_id
                    FROM learning_atoms WHERE id = :atom_id
                """),
                    {"atom_id": atom_id},
                ).fetchone()

                if updated:
                    result["new_stability"] = updated.anki_stability or 0
                    result["next_due"] = (
                        str(updated.anki_due_date) if updated.anki_due_date else None
                    )

                    # 3. Trigger section mastery recalculation
                    if updated.ccna_section_id:
                        self._update_section_mastery(conn, updated.ccna_section_id)

            except Exception as e:
                logger.warning(f"Could not update FSRS metrics: {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass

            try:
                conn.commit()
            except Exception:
                pass

        # 4. Update transfer testing (accuracy by type, memorization detection)
        if atom_type:
            self._update_transfer_testing(atom_id, atom_type, is_correct)
            result["atom_type"] = atom_type

        logger.debug(
            f"Recorded interaction: atom={atom_id[:8]}... "
            f"correct={is_correct} stability={result['new_stability']:.1f}"
        )
        return result

    def _update_transfer_testing(
        self,
        atom_id: str,
        atom_type: str,
        is_correct: bool,
    ) -> None:
        """
        Update transfer testing data for memorization detection.

        Tracks per-format accuracy and flags memorization suspects
        when T/F accuracy is 35%+ higher than procedural accuracy.

        Args:
            atom_id: UUID of the atom
            atom_type: Question type (mcq, true_false, parsons, matching)
            is_correct: Whether the answer was correct
        """
        import json
        from src.db.database import engine

        # Recognition types that might indicate memorization if not transferable
        recognition_types = {"true_false", "mcq"}
        # Procedural types that test genuine understanding
        procedural_types = {"parsons", "numeric", "sequence"}

        with engine.connect() as conn:
            try:
                # 1. Fetch current accuracy_by_type
                row = conn.execute(
                    text("""
                        SELECT accuracy_by_type, ccna_section_id
                        FROM learning_atoms
                        WHERE id = :atom_id
                    """),
                    {"atom_id": atom_id}
                ).fetchone()

                if not row:
                    return

                accuracy_data = row.accuracy_by_type or {}
                if isinstance(accuracy_data, str):
                    accuracy_data = json.loads(accuracy_data)

                section_id = row.ccna_section_id

                # 2. Update accuracy for this type
                type_stats = accuracy_data.get(atom_type, {"correct": 0, "total": 0})
                type_stats["total"] = type_stats.get("total", 0) + 1
                if is_correct:
                    type_stats["correct"] = type_stats.get("correct", 0) + 1
                accuracy_data[atom_type] = type_stats

                # 3. Calculate transfer score and memorization suspect flag
                transfer_score = None
                memorization_suspect = False

                # Calculate per-category accuracy
                recognition_correct = 0
                recognition_total = 0
                procedural_correct = 0
                procedural_total = 0

                for atype, stats in accuracy_data.items():
                    if atype in recognition_types:
                        recognition_correct += stats.get("correct", 0)
                        recognition_total += stats.get("total", 0)
                    elif atype in procedural_types:
                        procedural_correct += stats.get("correct", 0)
                        procedural_total += stats.get("total", 0)

                # Calculate transfer score if we have both recognition and procedural data
                if recognition_total >= 3 and procedural_total >= 2:
                    recognition_acc = recognition_correct / recognition_total
                    procedural_acc = procedural_correct / procedural_total

                    # Transfer score: average of accuracies (high = consistent understanding)
                    transfer_score = (recognition_acc + procedural_acc) / 2

                    # Flag memorization suspect: 35% gap between recognition and procedural
                    if recognition_acc - procedural_acc >= 0.35:
                        memorization_suspect = True
                        logger.warning(
                            f"Memorization suspect detected: atom={atom_id[:8]}, "
                            f"recognition={recognition_acc:.0%}, procedural={procedural_acc:.0%}"
                        )

                # 4. Queue for transfer test if recognition success
                transfer_queue = None
                if is_correct and atom_type in recognition_types:
                    # Queue a procedural test for next session
                    target_type = "parsons" if atom_type == "true_false" else "numeric"
                    transfer_queue = [f"{atom_id}:{target_type}"]

                # 5. Update database
                conn.execute(
                    text("""
                        UPDATE learning_atoms
                        SET
                            accuracy_by_type = :accuracy_data::jsonb,
                            transfer_score = COALESCE(:transfer_score, transfer_score),
                            memorization_suspect = :memorization_suspect,
                            format_seen = COALESCE(format_seen, '{}'::jsonb) || jsonb_build_object(:atom_type, NOW()),
                            transfer_queue = CASE
                                WHEN :transfer_queue IS NOT NULL
                                THEN COALESCE(transfer_queue, ARRAY[]::text[]) || :transfer_queue::text[]
                                ELSE transfer_queue
                            END,
                            updated_at = NOW()
                        WHERE id = :atom_id
                    """),
                    {
                        "atom_id": atom_id,
                        "accuracy_data": json.dumps(accuracy_data),
                        "transfer_score": transfer_score,
                        "memorization_suspect": memorization_suspect,
                        "atom_type": atom_type,
                        "transfer_queue": transfer_queue,
                    }
                )
                conn.commit()

            except Exception as e:
                logger.debug(f"Transfer testing update skipped: {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass

    def _update_section_mastery(self, conn, section_id: str) -> None:
        """Update section mastery scores after an interaction."""
        try:
            # Recalculate section stats from atom data
            # Mastery is calculated only from STUDIED atoms (have reviews or responses)
            # This prevents unstudied atoms from diluting progress
            conn.execute(
                text("""
                INSERT INTO ccna_section_mastery (
                    section_id, user_id, mastery_score,
                    atoms_total, atoms_mastered, atoms_learning, atoms_struggling, atoms_new,
                    total_reviews, last_review_date, updated_at
                )
                SELECT
                    :section_id,
                    :user_id,
                    -- Mastery = average stability of STUDIED atoms only (0.0-1.0 range)
                    -- Atoms are "studied" if they have reviews or NLS responses
                    -- Uses stability / 30 days as proxy for long-term memory
                    COALESCE(
                        AVG(LEAST(anki_stability / 30.0, 1.0)) FILTER (
                            WHERE COALESCE(anki_review_count, 0) > 0
                               OR COALESCE(nls_correct_count, 0) > 0
                               OR COALESCE(nls_incorrect_count, 0) > 0
                        ),
                        0
                    ),
                    COUNT(*),
                    COUNT(*) FILTER (WHERE anki_stability >= 21),
                    COUNT(*) FILTER (WHERE anki_stability >= 7 AND anki_stability < 21),
                    COUNT(*) FILTER (WHERE anki_lapses >= 2 OR anki_stability < 7),
                    COUNT(*) FILTER (WHERE anki_review_count IS NULL OR anki_review_count = 0),
                    COALESCE(SUM(anki_review_count), 0),
                    NOW(),
                    NOW()
                FROM learning_atoms
                WHERE ccna_section_id = :section_id
                ON CONFLICT (section_id, user_id)
                DO UPDATE SET
                    mastery_score = EXCLUDED.mastery_score,
                    atoms_total = EXCLUDED.atoms_total,
                    atoms_mastered = EXCLUDED.atoms_mastered,
                    atoms_learning = EXCLUDED.atoms_learning,
                    atoms_struggling = EXCLUDED.atoms_struggling,
                    atoms_new = EXCLUDED.atoms_new,
                    total_reviews = EXCLUDED.total_reviews,
                    last_review_date = EXCLUDED.last_review_date,
                    updated_at = NOW()
            """),
                {"section_id": section_id, "user_id": self.user_id},
            )
        except Exception as e:
            logger.debug(f"Could not update section mastery: {e}")

    def record_diagnosis(
        self,
        atom_id: str,
        diagnosis: CognitiveDiagnosis,
        response_time_ms: int,
        is_correct: bool,
    ) -> str | None:
        """
        Persist a cognitive diagnosis to the database.

        This is the critical "synapse" that wires the neuro-cognitive model
        to the persistence layer, enabling long-term learning analytics.

        Uses the existing PostgreSQL function `record_diagnosis()` from
        migration 017_neuromorphic_cortex.sql.

        Args:
            atom_id: UUID of the atom that was diagnosed
            diagnosis: CognitiveDiagnosis from the neuro model
            response_time_ms: Response time in milliseconds
            is_correct: Whether the answer was correct

        Returns:
            UUID of the created diagnosis record, or None if failed
        """
        import json

        from src.db.database import engine

        # Map Python enum values to PostgreSQL text
        fail_mode = diagnosis.fail_mode.value if diagnosis.fail_mode else None
        success_mode = diagnosis.success_mode.value if diagnosis.success_mode else None
        cognitive_state = diagnosis.cognitive_state.value if diagnosis.cognitive_state else "flow"
        remediation_type = diagnosis.remediation_type.value if diagnosis.remediation_type else None

        # Serialize evidence as JSON
        evidence_json = json.dumps(diagnosis.evidence) if diagnosis.evidence else "[]"

        with engine.connect() as conn:
            try:
                # Use the PostgreSQL function from 017_neuromorphic_cortex.sql
                result = conn.execute(
                    text("""
                    SELECT record_diagnosis(
                        :user_id,
                        :atom_id,
                        :fail_mode,
                        :success_mode,
                        :cognitive_state,
                        :confidence,
                        :response_time_ms,
                        :is_correct,
                        :remediation_type,
                        :evidence
                    ) as diagnosis_id
                """),
                    {
                        "user_id": self.user_id,
                        "atom_id": atom_id,
                        "fail_mode": fail_mode,
                        "success_mode": success_mode,
                        "cognitive_state": cognitive_state,
                        "confidence": round(diagnosis.confidence, 3),
                        "response_time_ms": response_time_ms,
                        "is_correct": is_correct,
                        "remediation_type": remediation_type,
                        "evidence": evidence_json,
                    },
                )

                row = result.fetchone()
                diagnosis_id = str(row.diagnosis_id) if row else None
                conn.commit()

                logger.info(
                    f"Recorded diagnosis: atom={atom_id[:8]}... "
                    f"fail_mode={fail_mode or 'success'} "
                    f"confidence={diagnosis.confidence:.2f} "
                    f"diagnosis_id={diagnosis_id[:8] if diagnosis_id else 'N/A'}..."
                )
                return diagnosis_id

            except Exception as e:
                logger.warning(f"Could not record diagnosis (function may not exist): {e}")
                conn.rollback()

                # Fallback: direct INSERT if function doesn't exist
                try:
                    result = conn.execute(
                        text("""
                        INSERT INTO cognitive_diagnoses (
                            user_id, atom_id, fail_mode, success_mode, cognitive_state,
                            confidence, response_time_ms, is_correct, remediation_type,
                            evidence, diagnosed_at
                        ) VALUES (
                            :user_id, :atom_id, :fail_mode, :success_mode, :cognitive_state,
                            :confidence, :response_time_ms, :is_correct, :remediation_type,
                            :evidence::jsonb, NOW()
                        )
                        RETURNING id
                    """),
                        {
                            "user_id": self.user_id,
                            "atom_id": atom_id,
                            "fail_mode": fail_mode,
                            "success_mode": success_mode,
                            "cognitive_state": cognitive_state,
                            "confidence": round(diagnosis.confidence, 3),
                            "response_time_ms": response_time_ms,
                            "is_correct": is_correct,
                            "remediation_type": remediation_type,
                            "evidence": evidence_json,
                        },
                    )

                    row = result.fetchone()
                    diagnosis_id = str(row.id) if row else None
                    conn.commit()

                    logger.info(f"Recorded diagnosis (fallback): diagnosis_id={diagnosis_id}")
                    return diagnosis_id

                except Exception as e2:
                    logger.error(f"Fallback diagnosis insert failed: {e2}")
                    conn.rollback()
                    return None

    def get_manual_session(
        self,
        sections: list[str],
        atom_types: list[str] | None = None,
        limit: int = 20,
        use_struggle_weights: bool = True,
        shuffle: bool = True,
    ) -> list[dict]:
        """
        Get atoms for Manual Mode - user-specified sections and types.

        Manual Mode gives full control:
        1. Specify exact sections to study (supports wildcards via CLI)
        2. Filter by atom types (all, mcq, true_false, parsons, matching)
        3. Optional struggle map weighting
        4. No FSRS scheduling constraints

        Args:
            sections: List of section IDs (e.g., ["11.3", "11.4", "14.2"])
            atom_types: List of atom types to include (None = all supported)
            limit: Maximum atoms to return
            use_struggle_weights: Apply struggle map priority weighting
            shuffle: Randomize order after retrieval

        Returns:
            List of atom dicts ready for presentation
        """
        from src.db.database import engine

        # Default to all supported quiz types
        if atom_types is None or atom_types == ["all"]:
            atom_types = ["mcq", "true_false", "parsons", "matching", "numeric"]

        with engine.connect() as conn:
            # Build the sections filter
            # Handle both direct section matches and parent prefix matches
            section_conditions = []
            params: dict = {"types": atom_types, "limit": limit}

            for i, section in enumerate(sections):
                param_name = f"sec_{i}"
                # Handle wildcard patterns like "5.x", "5.*", or just "5" for module-level
                if section.endswith(".x") or section.endswith(".*"):
                    # Wildcard: match all sections under this prefix
                    prefix = section[:-2]  # Strip ".x" or ".*"
                    section_conditions.append(f"cs.section_id LIKE :{param_name}_prefix")
                    params[f"{param_name}_prefix"] = f"{prefix}.%"
                elif "." not in section and section.isdigit():
                    # Just a module number: match all sections in this module
                    section_conditions.append(f"cs.module_number = :{param_name}_module")
                    params[f"{param_name}_module"] = int(section)
                else:
                    # Match exact section or any child sections
                    section_conditions.append(
                        f"(cs.section_id = :{param_name} OR cs.section_id LIKE :{param_name}_prefix)"
                    )
                    params[param_name] = section
                    params[f"{param_name}_prefix"] = f"{section}.%"

            sections_where = " OR ".join(section_conditions) if section_conditions else "TRUE"

            # Base query with optional struggle weighting
            if use_struggle_weights:
                query = f"""
                    SELECT
                        ca.id,
                        ca.card_id,
                        ca.atom_type,
                        ca.front,
                        ca.back,
                        ca.concept_id,
                        ca.ccna_section_id,
                        cs.module_number,
                        cs.title as section_title,
                        cc.name as concept_name,
                        COALESCE(ca.anki_difficulty, 0.5) as difficulty,
                        COALESCE(ca.anki_stability, 0) as stability,
                        COALESCE(ca.anki_lapses, 0) as lapses,
                        COALESCE(ca.anki_review_count, 0) as review_count,
                        COALESCE(sw.weight, 0.3) as struggle_weight
                    FROM learning_atoms ca
                    JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
                    LEFT JOIN concepts cc ON ca.concept_id = cc.id
                    LEFT JOIN struggle_weights sw ON
                        sw.module_number = cs.module_number AND
                        (sw.section_id IS NULL OR sw.section_id = cs.section_id)
                    WHERE ({sections_where})
                      AND ca.atom_type = ANY(:types)
                      AND ca.front IS NOT NULL
                      AND ca.front != ''
                    ORDER BY
                        COALESCE(sw.weight, 0.3) DESC,
                        COALESCE(ca.anki_stability, 0) ASC,
                        RANDOM()
                    LIMIT :limit
                """
            else:
                query = f"""
                    SELECT
                        ca.id,
                        ca.card_id,
                        ca.atom_type,
                        ca.front,
                        ca.back,
                        ca.concept_id,
                        ca.ccna_section_id,
                        cs.module_number,
                        cs.title as section_title,
                        cc.name as concept_name,
                        COALESCE(ca.anki_difficulty, 0.5) as difficulty,
                        COALESCE(ca.anki_stability, 0) as stability,
                        COALESCE(ca.anki_lapses, 0) as lapses,
                        COALESCE(ca.anki_review_count, 0) as review_count,
                        0.5 as struggle_weight
                    FROM learning_atoms ca
                    JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
                    LEFT JOIN concepts cc ON ca.concept_id = cc.id
                    WHERE ({sections_where})
                      AND ca.atom_type = ANY(:types)
                      AND ca.front IS NOT NULL
                      AND ca.front != ''
                    ORDER BY RANDOM()
                    LIMIT :limit
                """

            try:
                result = conn.execute(text(query), params)
                rows = result.fetchall()
            except Exception as e:
                logger.warning(f"Manual session query failed (struggle_weights may not exist): {e}")
                # Rollback the failed transaction before attempting fallback
                conn.rollback()
                # Fallback without struggle weights
                fallback_query = f"""
                    SELECT
                        ca.id,
                        ca.card_id,
                        ca.atom_type,
                        ca.front,
                        ca.back,
                        ca.concept_id,
                        ca.ccna_section_id,
                        cs.module_number,
                        cs.title as section_title,
                        cc.name as concept_name,
                        COALESCE(ca.anki_difficulty, 0.5) as difficulty,
                        COALESCE(ca.anki_stability, 0) as stability,
                        COALESCE(ca.anki_lapses, 0) as lapses,
                        COALESCE(ca.anki_review_count, 0) as review_count,
                        0.5 as struggle_weight
                    FROM learning_atoms ca
                    JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
                    LEFT JOIN concepts cc ON ca.concept_id = cc.id
                    WHERE ({sections_where})
                      AND ca.atom_type = ANY(:types)
                      AND ca.front IS NOT NULL
                      AND ca.front != ''
                    ORDER BY RANDOM()
                    LIMIT :limit
                """
                result = conn.execute(text(fallback_query), params)
                rows = result.fetchall()

            atoms = []
            for row in rows:
                atoms.append(
                    {
                        "id": str(row.id),
                        "card_id": row.card_id,
                        "atom_type": row.atom_type,
                        "front": row.front,
                        "back": row.back or "",
                        "concept_id": str(row.concept_id) if row.concept_id else None,
                        "section_id": row.ccna_section_id,
                        "module_number": row.module_number,
                        "section_title": row.section_title,
                        "concept_name": row.concept_name or "Unknown",
                        "difficulty": row.difficulty,
                        "stability": row.stability,
                        "lapses": row.lapses,
                        "review_count": row.review_count,
                        "struggle_weight": float(row.struggle_weight),
                    }
                )

            if shuffle:
                import random
                random.shuffle(atoms)

        logger.info(
            f"Manual session: {len(atoms)} atoms from {len(sections)} sections "
            f"(types: {atom_types}, struggle_weights: {use_struggle_weights})"
        )
        return atoms
