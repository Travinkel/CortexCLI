"""
Retention Engine - Maximizing Long-Term Memory Formation.

Implements evidence-based learning science principles:
1. FSRS-4 Algorithm - Optimized spaced repetition intervals
2. Desirable Difficulty - Calibrated challenge levels
3. Smart Interleaving - Concept-aware mixing
4. Retrieval Practice - Testing over re-reading
5. Spacing Effect - Distributed practice optimization

Based on research from:
- Bjork & Bjork (desirable difficulties)
- Karpicke (retrieval practice)
- Rohrer (interleaving)
- Wozniak (SM algorithms)
- Ye (FSRS algorithm)
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from loguru import logger
from sqlalchemy import text


# =============================================================================
# FSRS-4 CONSTANTS (Optimized for CCNA-style content)
# =============================================================================

# Default FSRS parameters (can be personalized)
FSRS_PARAMS = {
    "w": [
        0.4,    # w0: initial stability for Again
        0.6,    # w1: initial stability for Hard
        2.4,    # w2: initial stability for Good
        5.8,    # w3: initial stability for Easy
        4.93,   # w4: difficulty decay
        0.94,   # w5: stability decay
        0.86,   # w6: stability factor
        0.01,   # w7: difficulty-stability factor
        1.49,   # w8: hard penalty
        0.14,   # w9: easy bonus
        0.94,   # w10: forgetting curve exponent
        2.18,   # w11: fail relearn factor
        0.05,   # w12: hard interval factor
        0.34,   # w13: easy interval factor
        1.26,   # w14: stability growth
        0.29,   # w15: difficulty growth
        2.61,   # w16: short-term stability
    ],
    "requestRetention": 0.90,  # Target 90% recall
    "maximumInterval": 365,    # Cap at 1 year
    "easyBonus": 1.3,
    "hardInterval": 1.2,
}

# Grade mapping for quiz responses
GRADE_AGAIN = 1  # Complete failure
GRADE_HARD = 2   # Correct but difficult
GRADE_GOOD = 3   # Correct with normal effort
GRADE_EASY = 4   # Correct with little effort


@dataclass
class FSRSState:
    """Memory state for an atom."""
    stability: float = 0.0      # Days until 90% forgetting
    difficulty: float = 0.3     # 0.0 (easy) to 1.0 (hard)
    elapsed_days: int = 0       # Days since last review
    reps: int = 0               # Total review count
    lapses: int = 0             # Failed review count
    last_review: Optional[date] = None

    @property
    def retrievability(self) -> float:
        """Calculate current recall probability (0-1)."""
        if self.stability <= 0:
            return 0.0
        return math.pow(0.9, self.elapsed_days / self.stability)


@dataclass
class ReviewResult:
    """Result of reviewing an atom."""
    atom_id: str
    grade: int  # 1-4 (Again, Hard, Good, Easy)
    response_time_ms: int
    was_correct: bool
    new_stability: float
    new_difficulty: float
    next_interval: int  # Days until next review
    next_due: date


class FSRSScheduler:
    """
    FSRS-4 Spaced Repetition Scheduler.

    Calculates optimal review intervals based on memory state
    and desired retention rate.
    """

    def __init__(self, params: dict = None):
        self.params = params or FSRS_PARAMS
        self.w = self.params["w"]
        self.request_retention = self.params["requestRetention"]
        self.max_interval = self.params["maximumInterval"]

    def grade_response(
        self,
        is_correct: bool,
        response_time_ms: int,
        expected_time_ms: int = 15000,
        hint_used: bool = False,
    ) -> int:
        """
        Convert response to FSRS grade (1-4).

        Factors:
        - Correctness (primary)
        - Response time relative to expected
        - Hint usage
        """
        if not is_correct:
            return GRADE_AGAIN

        # Time ratio: <0.5 = fast, >2.0 = slow
        time_ratio = response_time_ms / expected_time_ms

        if hint_used:
            return GRADE_HARD
        elif time_ratio < 0.5:
            return GRADE_EASY
        elif time_ratio < 1.5:
            return GRADE_GOOD
        else:
            return GRADE_HARD

    def review(self, state: FSRSState, grade: int) -> FSRSState:
        """
        Process a review and return new memory state.

        Implements FSRS-4 algorithm for interval calculation.
        """
        new_state = FSRSState(
            difficulty=state.difficulty,
            reps=state.reps + 1,
            lapses=state.lapses,
            last_review=date.today(),
        )

        if state.reps == 0:
            # First review - use initial stability
            new_state.stability = self._initial_stability(grade)
            new_state.difficulty = self._initial_difficulty(grade)
        else:
            if grade == GRADE_AGAIN:
                # Failed - relearn
                new_state.lapses += 1
                new_state.stability = self._next_forget_stability(
                    state.difficulty, state.stability, state.retrievability
                )
                new_state.difficulty = self._next_difficulty(state.difficulty, grade)
            else:
                # Passed - strengthen
                new_state.stability = self._next_recall_stability(
                    state.difficulty, state.stability, state.retrievability, grade
                )
                new_state.difficulty = self._next_difficulty(state.difficulty, grade)

        # Calculate interval from stability and desired retention
        new_state.elapsed_days = 0
        interval = self._next_interval(new_state.stability)

        return new_state, interval

    def _initial_stability(self, grade: int) -> float:
        """Initial stability based on first review grade."""
        return self.w[grade - 1]

    def _initial_difficulty(self, grade: int) -> float:
        """Initial difficulty based on first review grade."""
        # Scale from 0.1 (Easy) to 0.9 (Again)
        return max(0.1, min(0.9, 1.0 - (grade - 1) * 0.3))

    def _next_difficulty(self, d: float, grade: int) -> float:
        """Update difficulty based on review outcome."""
        delta = (grade - 3) / 10  # -0.2 to +0.1
        new_d = d - delta
        return max(0.1, min(0.9, new_d))

    def _next_recall_stability(
        self, d: float, s: float, r: float, grade: int
    ) -> float:
        """Calculate new stability after successful recall."""
        # FSRS-4 stability growth formula
        hard_penalty = self.w[8] if grade == GRADE_HARD else 1.0
        easy_bonus = self.w[9] if grade == GRADE_EASY else 1.0

        new_s = s * (
            1 + math.exp(self.w[14]) *
            (11 - d) *
            math.pow(s, -self.w[15]) *
            (math.exp((1 - r) * self.w[16]) - 1) *
            hard_penalty *
            easy_bonus
        )

        return min(self.max_interval, max(1, new_s))

    def _next_forget_stability(self, d: float, s: float, r: float) -> float:
        """Calculate new stability after forgetting."""
        # Relearn at reduced stability
        new_s = self.w[11] * math.pow(d, -self.w[12]) * (
            math.pow(s + 1, self.w[13]) - 1
        ) * math.exp((1 - r) * self.w[14])

        return max(1, min(s, new_s))

    def _next_interval(self, stability: float) -> int:
        """Convert stability to interval days."""
        # Interval = stability * desired retention factor
        interval = stability * math.log(self.request_retention) / math.log(0.9)
        return max(1, min(self.max_interval, round(interval)))


class DesirableDifficultyCalibrator:
    """
    Calibrates question difficulty for optimal learning.

    Implements Bjork's "desirable difficulties" principle:
    - Too easy = no learning
    - Too hard = frustration
    - Sweet spot = ~70-85% success rate
    """

    TARGET_SUCCESS_RATE = 0.80  # 80% success optimal for learning
    ADJUSTMENT_RATE = 0.1      # How fast to adjust

    def __init__(self):
        self.atom_difficulties: dict[str, float] = {}
        self.user_ability: float = 0.5  # 0-1 scale

    def calibrate_selection(
        self,
        atoms: list[dict],
        target_success_rate: float = None,
    ) -> list[dict]:
        """
        Reorder atoms to achieve target success rate.

        Mix harder and easier atoms to maintain engagement.
        """
        target = target_success_rate or self.TARGET_SUCCESS_RATE

        # Sort by difficulty
        sorted_atoms = sorted(
            atoms,
            key=lambda a: a.get("difficulty", 0.5)
        )

        # Interleave: easy-hard-medium pattern for engagement
        n = len(sorted_atoms)
        if n < 3:
            return sorted_atoms

        result = []
        easy = sorted_atoms[:n//3]
        medium = sorted_atoms[n//3:2*n//3]
        hard = sorted_atoms[2*n//3:]

        # Start with medium, then alternate
        while easy or medium or hard:
            if medium:
                result.append(medium.pop(0))
            if easy:
                result.append(easy.pop(0))
            if hard:
                result.append(hard.pop(0))

        return result

    def adjust_after_response(
        self,
        atom_id: str,
        was_correct: bool,
        response_time_ms: int,
    ) -> float:
        """
        Adjust atom difficulty estimate based on response.

        Returns new difficulty estimate.
        """
        current = self.atom_difficulties.get(atom_id, 0.5)

        # Bayesian update
        if was_correct:
            new_difficulty = current - self.ADJUSTMENT_RATE
        else:
            new_difficulty = current + self.ADJUSTMENT_RATE * 2

        # Factor in response time
        if was_correct and response_time_ms < 5000:
            new_difficulty -= 0.05  # Very quick = easier
        elif response_time_ms > 30000:
            new_difficulty += 0.05  # Very slow = harder

        new_difficulty = max(0.1, min(0.9, new_difficulty))
        self.atom_difficulties[atom_id] = new_difficulty

        return new_difficulty


class SmartInterleaver:
    """
    Concept-aware interleaving for optimal retention.

    Based on Rohrer's research showing interleaving
    improves long-term retention over blocked practice.
    """

    # Concept relationships for CCNA
    CONCEPT_CLUSTERS = {
        "addressing": ["ipv4", "subnet", "vlsm", "cidr", "broadcast", "unicast"],
        "layers": ["osi", "tcp_ip", "encapsulation", "pdu", "header"],
        "switching": ["mac", "arp", "ethernet", "vlan", "stp"],
        "routing": ["gateway", "route", "hop", "metric", "static", "dynamic"],
        "protocols": ["tcp", "udp", "icmp", "dhcp", "dns", "http"],
        "security": ["acl", "firewall", "nat", "password", "encryption"],
        "config": ["ios", "cli", "mode", "command", "interface"],
    }

    def interleave(
        self,
        atoms: list[dict],
        spacing_factor: int = 3,
    ) -> list[dict]:
        """
        Interleave atoms with concept-aware spacing.

        Args:
            atoms: List of atoms to interleave
            spacing_factor: Minimum gap between related concepts

        Returns:
            Optimally interleaved atom list
        """
        if len(atoms) <= spacing_factor:
            random.shuffle(atoms)
            return atoms

        # Tag atoms with concept clusters
        for atom in atoms:
            atom["_clusters"] = self._identify_clusters(atom)

        result = []
        remaining = atoms.copy()
        recent_clusters: list[set] = []

        while remaining:
            # Find atom that doesn't overlap with recent clusters
            best_atom = None
            best_score = -1

            for atom in remaining:
                score = self._spacing_score(atom["_clusters"], recent_clusters)
                if score > best_score:
                    best_score = score
                    best_atom = atom

            if best_atom:
                result.append(best_atom)
                remaining.remove(best_atom)
                recent_clusters.append(best_atom["_clusters"])
                if len(recent_clusters) > spacing_factor:
                    recent_clusters.pop(0)

        # Clean up temp tags
        for atom in result:
            atom.pop("_clusters", None)

        return result

    def _identify_clusters(self, atom: dict) -> set[str]:
        """Identify which concept clusters an atom belongs to."""
        clusters = set()

        # Check front and back content
        text = f"{atom.get('front', '')} {atom.get('back', '')}".lower()

        for cluster_name, keywords in self.CONCEPT_CLUSTERS.items():
            if any(kw in text for kw in keywords):
                clusters.add(cluster_name)

        return clusters or {"general"}

    def _spacing_score(
        self,
        atom_clusters: set[str],
        recent_clusters: list[set[str]],
    ) -> float:
        """Score how well-spaced this atom is from recent ones."""
        if not recent_clusters:
            return 1.0

        # Higher score = less overlap with recent
        overlaps = sum(
            len(atom_clusters & recent) / max(1, len(atom_clusters))
            for recent in recent_clusters
        )

        return 1.0 - (overlaps / len(recent_clusters))


class RetentionEngine:
    """
    Main engine for maximizing retention.

    Combines:
    - FSRS scheduling
    - Desirable difficulty
    - Smart interleaving
    - Reading integration
    """

    def __init__(self, db_engine=None):
        self.db_engine = db_engine
        self.fsrs = FSRSScheduler()
        self.calibrator = DesirableDifficultyCalibrator()
        self.interleaver = SmartInterleaver()

    def get_optimized_session(
        self,
        limit: int = 20,
        modules: list[int] = None,
        struggle_modules: set[int] = None,
    ) -> list[dict]:
        """
        Get atoms optimized for maximum retention.

        Order:
        1. Overdue reviews (highest priority)
        2. Due reviews (FSRS scheduled)
        3. New atoms (progressive introduction)

        Processing:
        1. Difficulty calibration
        2. Smart interleaving
        3. Spaced by concept clusters
        """
        from src.db.database import engine

        db = self.db_engine or engine

        try:
            with db.connect() as conn:
                # 1. Get overdue atoms (urgently need review)
                overdue = self._get_overdue_atoms(conn, limit // 3, modules)

                # 2. Get due atoms (scheduled for today)
                due = self._get_due_atoms(conn, limit // 2, modules)

                # 3. Get new atoms (never reviewed)
                new_limit = limit - len(overdue) - len(due)
                new = self._get_new_atoms(conn, max(0, new_limit), modules)

            # Combine with priority
            all_atoms = overdue + due + new

            # Weight struggle modules higher
            if struggle_modules:
                for atom in all_atoms:
                    if atom.get("module_number") in struggle_modules:
                        atom["_priority"] = atom.get("_priority", 1.0) * 1.5

            # Apply difficulty calibration
            all_atoms = self.calibrator.calibrate_selection(all_atoms)

            # Smart interleaving
            all_atoms = self.interleaver.interleave(all_atoms)

            return all_atoms[:limit]

        except Exception as e:
            logger.error(f"Failed to get optimized session: {e}")
            return []

    def record_response(
        self,
        atom_id: str,
        is_correct: bool,
        response_time_ms: int,
        hint_used: bool = False,
    ) -> Optional[ReviewResult]:
        """
        Record response and update FSRS state.

        Returns scheduling information, or None on error.
        """
        from src.db.database import engine

        try:
            # Get current state
            with engine.connect() as conn:
                row = conn.execute(
                    text("""
                        SELECT
                            COALESCE(anki_stability, 0) as stability,
                            COALESCE(anki_difficulty, 0.3) as difficulty,
                            COALESCE(anki_review_count, 0) as reps,
                            COALESCE(anki_lapses, 0) as lapses,
                            anki_due_date as last_review
                        FROM clean_atoms
                        WHERE id = :atom_id
                    """),
                    {"atom_id": atom_id}
                ).fetchone()

                if not row:
                    logger.warning(f"Atom {atom_id} not found")
                    return None

                # Build current state
                state = FSRSState(
                    stability=float(row.stability),
                    difficulty=float(row.difficulty),
                    reps=int(row.reps),
                    lapses=int(row.lapses),
                    last_review=row.last_review,
                )

                if state.last_review:
                    state.elapsed_days = (date.today() - state.last_review).days

            # Calculate grade and new state
            grade = self.fsrs.grade_response(
                is_correct, response_time_ms, hint_used=hint_used
            )
            new_state, interval = self.fsrs.review(state, grade)
            next_due = date.today() + timedelta(days=interval)

            # Update database
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        UPDATE clean_atoms
                        SET
                            anki_stability = :stability,
                            anki_difficulty = :difficulty,
                            anki_review_count = :reps,
                            anki_lapses = :lapses,
                            anki_due_date = :due_date,
                            updated_at = NOW()
                        WHERE id = :atom_id
                    """),
                    {
                        "atom_id": atom_id,
                        "stability": new_state.stability,
                        "difficulty": new_state.difficulty,
                        "reps": new_state.reps,
                        "lapses": new_state.lapses,
                        "due_date": next_due,
                    }
                )

                # Also record in atom_responses
                conn.execute(
                    text("""
                        INSERT INTO atom_responses (
                            atom_id, user_id, is_correct, response_time_ms, responded_at
                        ) VALUES (
                            :atom_id, :user_id, :is_correct, :response_time, NOW()
                        )
                    """),
                    {
                        "atom_id": atom_id,
                        "user_id": "default",  # Single-user CLI mode
                        "is_correct": is_correct,
                        "response_time": response_time_ms,
                    }
                )

                conn.commit()

            # Update difficulty calibrator
            self.calibrator.adjust_after_response(atom_id, is_correct, response_time_ms)

            return ReviewResult(
                atom_id=atom_id,
                grade=grade,
                response_time_ms=response_time_ms,
                was_correct=is_correct,
                new_stability=new_state.stability,
                new_difficulty=new_state.difficulty,
                next_interval=interval,
                next_due=next_due,
            )

        except Exception as e:
            logger.error(f"Failed to record response for atom {atom_id}: {e}")
            return None

    def suggest_reading(
        self,
        modules: list[int] = None,
        struggle_modules: set[int] = None,
    ) -> list[dict]:
        """
        Suggest sections to read before studying.

        Returns sections where:
        - High lapse rate (encoding issues)
        - Low stability across atoms
        - In struggle modules
        """
        from src.db.database import engine

        try:
            with engine.connect() as conn:
                query = """
                    SELECT
                        cs.section_id,
                        cs.module_number,
                        cs.title,
                        COUNT(la.id) as atom_count,
                        AVG(COALESCE(la.anki_stability, 0)) as avg_stability,
                        SUM(COALESCE(la.anki_lapses, 0)) as total_lapses,
                        AVG(COALESCE(la.anki_difficulty, 0.5)) as avg_difficulty
                    FROM ccna_sections cs
                    LEFT JOIN clean_atoms la ON la.ccna_section_id = cs.section_id
                    WHERE 1=1
                """

                params = {}
                if modules:
                    query += " AND cs.module_number = ANY(:modules)"
                    params["modules"] = modules

                query += """
                    GROUP BY cs.section_id, cs.module_number, cs.title
                    HAVING AVG(COALESCE(la.anki_stability, 0)) < 7
                       OR SUM(COALESCE(la.anki_lapses, 0)) > 3
                    ORDER BY
                        SUM(COALESCE(la.anki_lapses, 0)) DESC,
                        AVG(COALESCE(la.anki_stability, 0)) ASC
                    LIMIT 5
                """

                result = conn.execute(text(query), params)

                suggestions = []
                for row in result.fetchall():
                    priority = "high" if row.total_lapses > 5 else "medium"
                    if struggle_modules and row.module_number in struggle_modules:
                        priority = "critical"

                    suggestions.append({
                        "section_id": row.section_id,
                        "module_number": row.module_number,
                        "title": row.title,
                        "priority": priority,
                        "reason": f"{int(row.total_lapses or 0)} lapses, {float(row.avg_stability or 0):.1f}d stability",
                        "command": f"nls cortex read {row.module_number} --section {row.section_id}",
                    })

                return suggestions

        except Exception as e:
            logger.error(f"Failed to get reading suggestions: {e}")
            return []

    def _get_overdue_atoms(
        self, conn, limit: int, modules: list[int] = None
    ) -> list[dict]:
        """Get atoms past their due date."""
        query = """
            SELECT
                la.id, la.atom_type, la.front, la.back,
                la.ccna_section_id, cs.module_number, cs.title as section_title,
                COALESCE(la.anki_difficulty, 0.5) as difficulty,
                COALESCE(la.anki_stability, 0) as stability,
                COALESCE(la.anki_lapses, 0) as lapses,
                COALESCE(la.anki_review_count, 0) as review_count,
                la.anki_due_date,
                CURRENT_DATE - la.anki_due_date as days_overdue
            FROM clean_atoms la
            JOIN ccna_sections cs ON la.ccna_section_id = cs.section_id
            WHERE la.atom_type IN ('mcq', 'true_false', 'parsons', 'numeric', 'matching')
              AND la.front IS NOT NULL AND la.front != ''
              AND la.anki_due_date < CURRENT_DATE
        """

        params = {"limit": limit}
        if modules:
            query += " AND cs.module_number = ANY(:modules)"
            params["modules"] = modules

        query += " ORDER BY la.anki_due_date ASC, la.anki_stability ASC LIMIT :limit"

        result = conn.execute(text(query), params)
        return [self._row_to_atom(row, "overdue") for row in result.fetchall()]

    def _get_due_atoms(
        self, conn, limit: int, modules: list[int] = None
    ) -> list[dict]:
        """Get atoms due today."""
        query = """
            SELECT
                la.id, la.atom_type, la.front, la.back,
                la.ccna_section_id, cs.module_number, cs.title as section_title,
                COALESCE(la.anki_difficulty, 0.5) as difficulty,
                COALESCE(la.anki_stability, 0) as stability,
                COALESCE(la.anki_lapses, 0) as lapses,
                COALESCE(la.anki_review_count, 0) as review_count,
                la.anki_due_date
            FROM clean_atoms la
            JOIN ccna_sections cs ON la.ccna_section_id = cs.section_id
            WHERE la.atom_type IN ('mcq', 'true_false', 'parsons', 'numeric', 'matching')
              AND la.front IS NOT NULL AND la.front != ''
              AND la.anki_due_date = CURRENT_DATE
        """

        params = {"limit": limit}
        if modules:
            query += " AND cs.module_number = ANY(:modules)"
            params["modules"] = modules

        query += " ORDER BY la.anki_stability ASC LIMIT :limit"

        result = conn.execute(text(query), params)
        return [self._row_to_atom(row, "due") for row in result.fetchall()]

    def _get_new_atoms(
        self, conn, limit: int, modules: list[int] = None
    ) -> list[dict]:
        """Get never-reviewed atoms."""
        query = """
            SELECT
                la.id, la.atom_type, la.front, la.back,
                la.ccna_section_id, cs.module_number, cs.title as section_title,
                0.5 as difficulty, 0 as stability, 0 as lapses, 0 as review_count,
                NULL as anki_due_date
            FROM clean_atoms la
            JOIN ccna_sections cs ON la.ccna_section_id = cs.section_id
            WHERE la.atom_type IN ('mcq', 'true_false', 'parsons', 'numeric', 'matching')
              AND la.front IS NOT NULL AND la.front != ''
              AND (la.anki_review_count IS NULL OR la.anki_review_count = 0)
        """

        params = {"limit": limit}
        if modules:
            query += " AND cs.module_number = ANY(:modules)"
            params["modules"] = modules

        query += " ORDER BY cs.display_order, RANDOM() LIMIT :limit"

        result = conn.execute(text(query), params)
        return [self._row_to_atom(row, "new") for row in result.fetchall()]

    def _row_to_atom(self, row, source: str) -> dict:
        """Convert database row to atom dict."""
        return {
            "id": str(row.id),
            "atom_type": row.atom_type,
            "front": row.front,
            "back": row.back or "",
            "section_id": row.ccna_section_id,
            "module_number": row.module_number,
            "section_title": row.section_title,
            "difficulty": float(row.difficulty),
            "stability": float(row.stability),
            "lapses": int(row.lapses),
            "review_count": int(row.review_count),
            "source": source,
            "_priority": 1.0 if source == "new" else 1.5 if source == "due" else 2.0,
        }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def calculate_retention_score(atoms_reviewed: int, correct: int, avg_stability: float) -> float:
    """
    Calculate overall retention effectiveness score.

    Combines:
    - Accuracy (40%)
    - Stability growth (40%)
    - Volume (20%)
    """
    if atoms_reviewed == 0:
        return 0.0

    accuracy = correct / atoms_reviewed
    stability_factor = min(1.0, avg_stability / 30)  # 30 days = max
    volume_factor = min(1.0, atoms_reviewed / 20)    # 20 atoms = good session

    return (accuracy * 0.4) + (stability_factor * 0.4) + (volume_factor * 0.2)


def estimate_study_time(atom_count: int, avg_difficulty: float = 0.5) -> int:
    """Estimate study time in minutes."""
    # Base: 30 seconds per atom, adjusted by difficulty
    base_seconds = 30
    difficulty_factor = 1 + avg_difficulty  # 1.0 to 2.0
    total_seconds = atom_count * base_seconds * difficulty_factor
    return max(1, round(total_seconds / 60))
