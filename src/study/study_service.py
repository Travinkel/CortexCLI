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
from typing import Optional

from loguru import logger
from sqlalchemy import text

from src.study.mastery_calculator import MasteryCalculator, MasteryMetrics, MasteryResult
from src.study.interleaver import AdaptiveInterleaver, StudyQueue


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
    new_atoms_available: int
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
    parent_section_id: Optional[str]
    mastery_score: float
    is_mastered: bool
    needs_remediation: bool
    remediation_reason: Optional[str]
    atoms_total: int
    atoms_mastered: int
    atoms_learning: int
    atoms_struggling: int
    atoms_new: int
    last_review_date: Optional[datetime]
    subsections: list["SectionDetail"]


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
            due_result = conn.execute(text("""
                SELECT COUNT(*) as cnt
                FROM learning_atoms
                WHERE anki_due_date IS NOT NULL
                  AND anki_due_date <= CURRENT_DATE
            """))
            due_reviews = due_result.fetchone().cnt or 0

            # Get new atoms available
            new_result = conn.execute(text("""
                SELECT COUNT(*) as cnt
                FROM learning_atoms
                WHERE (anki_review_count IS NULL OR anki_review_count = 0)
                  AND ccna_section_id IS NOT NULL
            """))
            new_atoms = new_result.fetchone().cnt or 0

            # Get remediation stats
            remediation_result = conn.execute(text("""
                SELECT
                    COUNT(*) as sections,
                    COALESCE(SUM(atoms_struggling), 0) as atoms
                FROM ccna_section_mastery
                WHERE needs_remediation = TRUE
                  AND user_id = :user_id
            """), {"user_id": self.user_id})
            rem_row = remediation_result.fetchone()
            remediation_sections = rem_row.sections or 0
            remediation_atoms = rem_row.atoms or 0

            # Get overall mastery
            mastery_result = conn.execute(text("""
                SELECT AVG(mastery_score) as avg_mastery
                FROM ccna_section_mastery
                WHERE user_id = :user_id
            """), {"user_id": self.user_id})
            overall_mastery = mastery_result.fetchone().avg_mastery or 0

            # Get current progress (first incomplete section)
            progress_result = conn.execute(text("""
                SELECT s.module_number, s.section_id
                FROM ccna_sections s
                LEFT JOIN ccna_section_mastery m
                    ON s.section_id = m.section_id AND m.user_id = :user_id
                WHERE COALESCE(m.is_completed, FALSE) = FALSE
                ORDER BY s.display_order
                LIMIT 1
            """), {"user_id": self.user_id})
            progress_row = progress_result.fetchone()
            current_module = progress_row.module_number if progress_row else 1
            current_section = progress_row.section_id if progress_row else "1.2"

            # Estimate time (30 sec per card)
            total_cards = due_reviews + min(30, new_atoms) + min(15, remediation_atoms)
            estimated_minutes = max(1, total_cards // 2)

            # Streak (simplified - count consecutive days with sessions)
            streak_result = conn.execute(text("""
                SELECT COUNT(DISTINCT session_date) as streak
                FROM ccna_study_sessions
                WHERE user_id = :user_id
                  AND session_date >= CURRENT_DATE - INTERVAL '30 days'
            """), {"user_id": self.user_id})
            streak_days = streak_result.fetchone().streak or 0

        return DailyStudySummary(
            date=date.today(),
            due_reviews=due_reviews,
            new_atoms_available=new_atoms,
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
            result = conn.execute(text("""
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
            """), {"user_id": self.user_id})

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
                summaries.append(ModuleSummary(
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
                ))

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
            result = conn.execute(text("""
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
            """), {"user_id": self.user_id, "module": module_number})

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
            result = conn.execute(text("""
                SELECT refresh_all_section_mastery(:user_id) as count
            """), {"user_id": self.user_id})
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
            result = conn.execute(text("""
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
            """), {"user_id": self.user_id})

            sections = []
            for row in result:
                sections.append(SectionDetail(
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
                ))

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
            overall_result = conn.execute(text("""
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
            """), {"user_id": self.user_id})
            overall = overall_result.fetchone()

            # Session history
            sessions_result = conn.execute(text("""
                SELECT
                    COUNT(*) as total_sessions,
                    SUM(duration_minutes) as total_minutes,
                    SUM(cards_reviewed) as total_cards,
                    AVG(correct_count::float / NULLIF(correct_count + incorrect_count, 0)) * 100 as avg_accuracy
                FROM ccna_study_sessions
                WHERE user_id = :user_id
            """), {"user_id": self.user_id})
            sessions = sessions_result.fetchone()

        return {
            "sections": {
                "total": overall.total_sections or 0,
                "completed": overall.completed_sections or 0,
                "completion_rate": round(
                    (overall.completed_sections or 0) / max(overall.total_sections or 1, 1) * 100,
                    1
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
            atoms_result = conn.execute(text("""
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
            """), {"module": module_number, "max_depth": max_depth})

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

    def get_multi_module_activity_path(
        self, module_numbers: list[int], max_depth: int = 3
    ) -> dict:
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
                if atom.get("destination") == "anki" or atom.get("atom_type") in ("flashcard", "cloze"):
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

                result["anki_jobs"].append({
                    "module": mod,
                    "is_target_module": is_target,
                    "flashcard_count": fc_count,
                    "cloze_count": cl_count,
                    "total": len(atoms_list),
                    "anki_query": f"deck:CCNA* tag:module:{mod}",
                    "note_ids": [a.get("anki_note_id") for a in atoms_list if a.get("anki_note_id")],
                })

            # Build NLS quiz jobs (grouped by type with CLT metadata)
            for qtype, atoms_list in nls_by_type.items():
                if atoms_list:
                    avg_clt = sum(
                        (a.get("clt_intrinsic") or 2) + (a.get("clt_extraneous") or 2) + (a.get("clt_germane") or 3)
                        for a in atoms_list
                    ) / (len(atoms_list) * 3)

                    result["nls_jobs"].append({
                        "quiz_type": qtype,
                        "count": len(atoms_list),
                        "avg_clt_load": round(avg_clt, 1),
                        "modules_included": sorted(set(a.get("module_number", 0) for a in atoms_list)),
                    })

            result["modules_touched"] = sorted(modules_set)
            result["concept_count"] = len(concepts_set)

            # Summary statistics
            result["summary"] = {
                "total_atoms": len(atoms),
                "anki_total": sum(j["total"] for j in result["anki_jobs"]),
                "nls_total": sum(j["count"] for j in result["nls_jobs"]),
                "prerequisite_modules": [m for m in result["modules_touched"] if m not in module_numbers],
                "target_modules": module_numbers,
            }

        logger.info(
            f"Activity path for modules {module_numbers}: "
            f"{result['summary']['anki_total']} Anki, {result['summary']['nls_total']} NLS, "
            f"{result['concept_count']} concepts across {len(result['modules_touched'])} modules"
        )

        return result

    def _fallback_multi_module_expansion(self, conn, module_numbers: list[int], max_depth: int) -> list[dict]:
        """Fallback expansion using prerequisite graph if available."""
        # Convert module list to SQL-safe format
        modules_str = ",".join(str(m) for m in module_numbers)

        # First check if explicit_prerequisites table exists
        try:
            check = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'explicit_prerequisites'
                )
            """))
            has_prereqs = check.scalar()
        except Exception:
            has_prereqs = False

        if not has_prereqs or max_depth == 0:
            # No prerequisite table or no expansion requested - use simple query
            return self._simple_module_atoms(conn, module_numbers)

        # Full recursive expansion with prerequisites
        result = conn.execute(text(f"""
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
        """), {"max_depth": max_depth})

        return [dict(row._mapping) for row in result.fetchall()]

    def _simple_module_atoms(self, conn, module_numbers: list[int]) -> list[dict]:
        """Simple query to get all atoms for modules without prerequisite expansion."""
        modules_str = ",".join(str(m) for m in module_numbers)

        result = conn.execute(text(f"""
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
        """))

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
                suggestions.append({
                    "priority": 1,
                    "type": "anki",
                    "action": f"Review {job['total']} cards in Module {job['module']}",
                    "reason": f"Prerequisites for Module(s) {target_modules}",
                    "query": job["anki_query"],
                    "count": job["total"],
                })
            elif job["is_target_module"]:
                suggestions.append({
                    "priority": 2,
                    "type": "anki",
                    "action": f"Learn {job['total']} new cards in Module {job['module']}",
                    "reason": "Target module content",
                    "query": job["anki_query"],
                    "count": job["total"],
                })

        # NLS quiz suggestions (CLT-balanced)
        for job in activity_path.get("nls_jobs", []):
            clt_desc = "moderate" if job["avg_clt_load"] < 3 else "challenging"
            suggestions.append({
                "priority": 3,
                "type": "nls_quiz",
                "action": f"Complete {job['count']} {job['quiz_type'].upper()} questions",
                "reason": f"{clt_desc.title()} CLT load ({job['avg_clt_load']}), covers modules {job['modules_included']}",
                "quiz_type": job["quiz_type"],
                "count": job["count"],
            })

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
            result = conn.execute(text(f"""
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
            """), {"types": types_list, "limit": limit})

            atoms = []
            for row in result:
                atoms.append({
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
                })

        logger.info(
            f"War session: {len(atoms)} atoms from modules {modules} "
            f"(types: {prioritize_types})"
        )
        return atoms

    def get_adaptive_session(
        self,
        limit: int = 20,
        include_new: bool = True,
        interleave: bool = True,
    ) -> list[dict]:
        """
        Get atoms for Adaptive Mode - uses FSRS scheduling and interleaving.

        Adaptive Mode:
        1. Prioritizes due reviews (FSRS scheduled)
        2. Mixes in new atoms for progressive learning
        3. Interleaves across modules for better retention
        4. Balances atom types to prevent fatigue

        Args:
            limit: Maximum atoms to return
            include_new: Whether to include never-reviewed atoms
            interleave: Whether to interleave across modules

        Returns:
            List of atom dicts ordered for optimal learning
        """
        from src.db.database import engine

        with engine.connect() as conn:
            # Get due reviews first
            due_query = """
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
                WHERE ca.atom_type IN ('mcq', 'true_false', 'parsons', 'numeric')
                  AND ca.front IS NOT NULL
                  AND ca.front != ''
                  AND ca.anki_due_date IS NOT NULL
                  AND ca.anki_due_date <= CURRENT_DATE
                ORDER BY ca.anki_due_date ASC, ca.anki_stability ASC
                LIMIT :due_limit
            """

            due_limit = limit if not include_new else int(limit * 0.7)
            due_result = conn.execute(text(due_query), {"due_limit": due_limit})
            due_atoms = [dict(row._mapping) for row in due_result.fetchall()]

            # Get new atoms if requested
            new_atoms = []
            if include_new and len(due_atoms) < limit:
                remaining = limit - len(due_atoms)
                # All quiz content is stored in learning_atoms.back (JSON for MCQ/matching)
                new_query = """
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
                    ORDER BY cs.display_order, RANDOM()
                    LIMIT :new_limit
                """
                new_result = conn.execute(text(new_query), {"new_limit": remaining})
                new_atoms = [dict(row._mapping) for row in new_result.fetchall()]

            # Combine and optionally interleave
            all_atoms = due_atoms + new_atoms

            if interleave and len(all_atoms) > 1:
                all_atoms = self._interleave_atoms(all_atoms)

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
                    "section_id": row["ccna_section_id"],
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

        logger.info(
            f"Adaptive session: {len(atoms)} atoms "
            f"({len(due_atoms)} due, {len(new_atoms)} new)"
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

    def record_interaction(
        self,
        atom_id: str,
        is_correct: bool,
        response_time_ms: int,
        user_answer: str = "",
        session_type: str = "cortex",
    ) -> dict:
        """
        Record a study interaction and update mastery metrics.

        This is the SINGLE entry point for all study results.
        Updates:
        1. atom_responses table (raw interaction log)
        2. learning_atoms FSRS fields (stability, difficulty, due_date)
        3. ccna_section_mastery aggregate scores

        Args:
            atom_id: UUID of the atom
            is_correct: Whether the answer was correct
            response_time_ms: Time taken to answer in milliseconds
            user_answer: The user's answer (for logging)
            session_type: Type of session (cortex, war, adaptive, anki)

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
                conn.execute(text("""
                    INSERT INTO atom_responses (
                        atom_id, user_id, is_correct, response_time_ms,
                        user_answer, responded_at
                    ) VALUES (
                        :atom_id, :user_id, :is_correct, :response_time,
                        :user_answer, NOW()
                    )
                """), {
                    "atom_id": atom_id,
                    "user_id": self.user_id,
                    "is_correct": is_correct,
                    "response_time": response_time_ms,
                    "user_answer": user_answer[:500] if user_answer else "",
                })
                conn.commit()
            except Exception as e:
                logger.debug(f"Could not record response (table may not exist): {e}")
                conn.rollback()

            # 2. Update FSRS-like metrics on learning_atoms
            # Simplified FSRS: stability grows on correct, shrinks on incorrect
            try:
                if is_correct:
                    # Correct: increase stability, decrease difficulty
                    conn.execute(text("""
                        UPDATE learning_atoms
                        SET
                            anki_stability = LEAST(COALESCE(anki_stability, 1) * 2.5, 365),
                            anki_difficulty = GREATEST(COALESCE(anki_difficulty, 0.3) - 0.05, 0.1),
                            anki_review_count = COALESCE(anki_review_count, 0) + 1,
                            anki_due_date = CURRENT_DATE + INTERVAL '1 day' * LEAST(COALESCE(anki_stability, 1) * 2.5, 365)::int,
                            updated_at = NOW()
                        WHERE id = :atom_id
                        RETURNING anki_stability, anki_due_date
                    """), {"atom_id": atom_id})
                else:
                    # Incorrect: reset stability, increase difficulty, increment lapses
                    conn.execute(text("""
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
                    """), {"atom_id": atom_id})

                # Fetch updated values
                updated = conn.execute(text("""
                    SELECT anki_stability, anki_due_date, ccna_section_id
                    FROM learning_atoms WHERE id = :atom_id
                """), {"atom_id": atom_id}).fetchone()

                if updated:
                    result["new_stability"] = updated.anki_stability or 0
                    result["next_due"] = str(updated.anki_due_date) if updated.anki_due_date else None

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

        logger.debug(
            f"Recorded interaction: atom={atom_id[:8]}... "
            f"correct={is_correct} stability={result['new_stability']:.1f}"
        )
        return result

    def _update_section_mastery(self, conn, section_id: str) -> None:
        """Update section mastery scores after an interaction."""
        try:
            # Recalculate section stats from atom data
            conn.execute(text("""
                INSERT INTO ccna_section_mastery (
                    section_id, user_id, mastery_score,
                    atoms_total, atoms_mastered, atoms_learning, atoms_struggling, atoms_new,
                    total_reviews, last_review_date, updated_at
                )
                SELECT
                    :section_id,
                    :user_id,
                    -- Mastery = weighted average of atom stability
                    COALESCE(AVG(LEAST(anki_stability / 30.0, 1.0)) * 100, 0),
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
            """), {"section_id": section_id, "user_id": self.user_id})
        except Exception as e:
            logger.debug(f"Could not update section mastery: {e}")
