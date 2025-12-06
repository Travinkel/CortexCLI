"""
Remediation Router.

Detects knowledge gaps and routes learners to prerequisite content.
Implements Knewton-style just-in-time remediation.

When a learner:
1. Answers incorrectly
2. Shows low confidence
3. Has unmet prerequisite mastery

The router identifies the gap and provides remediation atoms.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.adaptive.models import (
    KnowledgeGap,
    RemediationPlan,
    TriggerType,
    GatingType,
    MASTERY_THRESHOLDS,
)
from src.adaptive.mastery_calculator import MasteryCalculator
from src.db.database import session_scope


class RemediationRouter:
    """
    Route learners to remediation content when gaps are detected.

    Implements just-in-time remediation:
    - Detects gaps from incorrect answers or low mastery
    - Identifies prerequisite concepts needing reinforcement
    - Selects optimal atoms for remediation
    - Tracks remediation outcomes
    """

    def __init__(self, session: Optional[Session] = None):
        self._session = session
        self._mastery_calc = MasteryCalculator(session)

    def check_remediation_needed(
        self,
        learner_id: str,
        atom_id: UUID,
        is_correct: bool,
        confidence: Optional[int] = None,
    ) -> Optional[RemediationPlan]:
        """
        Check if remediation is needed after an answer.

        Args:
            learner_id: Learner identifier
            atom_id: Atom that was answered
            is_correct: Whether answer was correct
            confidence: Self-reported confidence (1-5)

        Returns:
            RemediationPlan if remediation needed, None otherwise
        """
        # Only check if answer was incorrect or confidence was low
        if is_correct and (confidence is None or confidence >= 3):
            return None

        with self._get_session() as session:
            # Get atom's concept
            concept_id = self._get_atom_concept(session, atom_id)
            if not concept_id:
                return None

            # Get concept's prerequisites
            prerequisites = self._get_concept_prerequisites(session, concept_id)

            # Find the weakest prerequisite
            gap = self._find_knowledge_gap(session, learner_id, prerequisites)

            if gap:
                # Determine trigger type
                if not is_correct:
                    trigger_type = TriggerType.INCORRECT_ANSWER
                elif confidence and confidence < 3:
                    trigger_type = TriggerType.LOW_CONFIDENCE
                else:
                    trigger_type = TriggerType.PREREQUISITE_GAP

                return self._create_remediation_plan(
                    session,
                    learner_id,
                    gap,
                    trigger_type,
                    atom_id,
                )

        return None

    def get_knowledge_gaps(
        self,
        learner_id: str,
        concept_id: Optional[UUID] = None,
        cluster_id: Optional[UUID] = None,
    ) -> list[KnowledgeGap]:
        """
        Identify all knowledge gaps for a learner.

        Args:
            learner_id: Learner identifier
            concept_id: Optional specific concept to check
            cluster_id: Optional cluster scope

        Returns:
            List of KnowledgeGap objects sorted by priority
        """
        with self._get_session() as session:
            gaps = []

            if concept_id:
                # Check specific concept and its prerequisites
                prerequisites = self._get_concept_prerequisites(session, concept_id)
                for prereq in prerequisites:
                    gap = self._check_single_gap(
                        session, learner_id, prereq
                    )
                    if gap:
                        gaps.append(gap)
            else:
                # Check all concepts in scope
                concepts = self._get_concepts_in_scope(session, cluster_id)
                for concept in concepts:
                    mastery = self._mastery_calc.compute_concept_mastery(
                        learner_id, concept["id"]
                    )
                    if mastery.combined_mastery < 0.65:  # Below proficient
                        gaps.append(KnowledgeGap(
                            concept_id=concept["id"],
                            concept_name=concept["name"],
                            current_mastery=mastery.combined_mastery,
                            required_mastery=0.65,
                            priority=self._determine_priority(mastery.combined_mastery),
                            recommended_atoms=self._get_remediation_atoms(
                                session, concept["id"], 5
                            ),
                        ))

            # Sort by priority (high first)
            priority_order = {"high": 0, "medium": 1, "low": 2}
            gaps.sort(key=lambda g: priority_order.get(g.priority, 2))

            return gaps

    def trigger_remediation(
        self,
        learner_id: str,
        concept_id: UUID,
        trigger_type: TriggerType = TriggerType.MANUAL,
        session_id: Optional[UUID] = None,
    ) -> RemediationPlan:
        """
        Manually trigger remediation for a concept.

        Args:
            learner_id: Learner identifier
            concept_id: Concept needing remediation
            trigger_type: Why remediation was triggered
            session_id: Optional learning session ID

        Returns:
            RemediationPlan with remediation atoms
        """
        with self._get_session() as session:
            # Get concept info
            concept_info = self._get_concept_info(session, concept_id)
            if not concept_info:
                raise ValueError(f"Concept not found: {concept_id}")

            # Get current mastery
            mastery = self._mastery_calc.compute_concept_mastery(
                learner_id, concept_id
            )

            # Get remediation atoms
            atoms = self._get_remediation_atoms(session, concept_id, 10)

            # Create plan
            plan = RemediationPlan(
                gap_concept_id=concept_id,
                gap_concept_name=concept_info["name"],
                atoms=atoms,
                priority=self._determine_priority(mastery.combined_mastery),
                gating_type=GatingType.SOFT,
                mastery_target=0.65,
                estimated_duration_minutes=len(atoms) * 2,
                trigger_type=trigger_type,
            )

            # Record the event
            self._record_remediation_event(
                session, learner_id, plan, session_id
            )

            return plan

    def complete_remediation(
        self,
        remediation_id: UUID,
        atoms_completed: int,
        atoms_correct: int,
    ) -> dict:
        """
        Mark a remediation as complete and record outcome.

        Args:
            remediation_id: Remediation event ID
            atoms_completed: Number of atoms completed
            atoms_correct: Number correct

        Returns:
            Dict with outcome metrics
        """
        with self._get_session() as session:
            # Get remediation event
            query = text("""
                SELECT
                    id, learner_id, gap_concept_id,
                    mastery_at_trigger, required_mastery
                FROM remediation_events
                WHERE id = :remediation_id
            """)

            result = session.execute(query, {"remediation_id": str(remediation_id)})
            event = result.fetchone()

            if not event:
                raise ValueError(f"Remediation event not found: {remediation_id}")

            # Calculate new mastery
            learner_id = event.learner_id
            concept_id = UUID(str(event.gap_concept_id))
            new_mastery = self._mastery_calc.compute_concept_mastery(
                learner_id, concept_id
            )

            # Determine if successful
            required = float(event.required_mastery or 0.65)
            successful = new_mastery.combined_mastery >= required
            improvement = new_mastery.combined_mastery - float(event.mastery_at_trigger or 0)

            # Update event
            update_query = text("""
                UPDATE remediation_events
                SET
                    remediation_completed_at = NOW(),
                    atoms_completed = :atoms_completed,
                    atoms_correct = :atoms_correct,
                    post_remediation_mastery = :post_mastery,
                    mastery_improvement = :improvement,
                    remediation_successful = :successful
                WHERE id = :remediation_id
            """)

            session.execute(update_query, {
                "remediation_id": str(remediation_id),
                "atoms_completed": atoms_completed,
                "atoms_correct": atoms_correct,
                "post_mastery": new_mastery.combined_mastery,
                "improvement": improvement,
                "successful": successful,
            })
            session.commit()

            return {
                "remediation_id": str(remediation_id),
                "successful": successful,
                "mastery_before": float(event.mastery_at_trigger or 0),
                "mastery_after": new_mastery.combined_mastery,
                "improvement": improvement,
                "atoms_completed": atoms_completed,
                "accuracy": (atoms_correct / atoms_completed * 100) if atoms_completed > 0 else 0,
            }

    def skip_remediation(
        self,
        remediation_id: UUID,
        reason: Optional[str] = None,
    ) -> None:
        """
        Record that learner skipped remediation.

        Args:
            remediation_id: Remediation event ID
            reason: Optional reason for skipping
        """
        with self._get_session() as session:
            query = text("""
                UPDATE remediation_events
                SET
                    was_skipped = TRUE,
                    skip_reason = :reason,
                    remediation_completed_at = NOW()
                WHERE id = :remediation_id
            """)

            session.execute(query, {
                "remediation_id": str(remediation_id),
                "reason": reason,
            })
            session.commit()

    def _get_atom_concept(
        self,
        session: Session,
        atom_id: UUID,
    ) -> Optional[UUID]:
        """Get the concept ID for an atom."""
        query = text("SELECT concept_id FROM learning_atoms WHERE id = :atom_id")
        result = session.execute(query, {"atom_id": str(atom_id)})
        row = result.fetchone()
        if row and row.concept_id:
            return UUID(str(row.concept_id))
        return None

    def _get_concept_prerequisites(
        self,
        session: Session,
        concept_id: UUID,
    ) -> list[dict]:
        """Get prerequisites for a concept."""
        query = text("""
            SELECT
                ep.target_concept_id,
                cc.name as concept_name,
                ep.mastery_threshold,
                ep.gating_type,
                ep.mastery_type
            FROM explicit_prerequisites ep
            JOIN concepts cc ON ep.target_concept_id = cc.id
            WHERE ep.source_concept_id = :concept_id
            AND ep.status = 'active'
        """)

        try:
            result = session.execute(query, {"concept_id": str(concept_id)})
            return [
                {
                    "concept_id": UUID(str(row.target_concept_id)),
                    "concept_name": row.concept_name,
                    "threshold": float(row.mastery_threshold or 0.65),
                    "gating_type": row.gating_type or "soft",
                    "mastery_type": row.mastery_type or "integration",
                }
                for row in result.fetchall()
            ]
        except Exception:
            return []

    def _find_knowledge_gap(
        self,
        session: Session,
        learner_id: str,
        prerequisites: list[dict],
    ) -> Optional[KnowledgeGap]:
        """Find the most significant knowledge gap among prerequisites."""
        if not prerequisites:
            return None

        largest_gap = None
        largest_gap_size = 0

        for prereq in prerequisites:
            mastery = self._mastery_calc.compute_concept_mastery(
                learner_id, prereq["concept_id"]
            )
            gap_size = prereq["threshold"] - mastery.combined_mastery

            if gap_size > largest_gap_size:
                largest_gap_size = gap_size
                largest_gap = KnowledgeGap(
                    concept_id=prereq["concept_id"],
                    concept_name=prereq["concept_name"],
                    current_mastery=mastery.combined_mastery,
                    required_mastery=prereq["threshold"],
                    priority="high" if prereq["gating_type"] == "hard" else "medium",
                    recommended_atoms=self._get_remediation_atoms(
                        session, prereq["concept_id"], 5
                    ),
                )

        # Only return if there's actually a gap
        if largest_gap and largest_gap_size > 0:
            return largest_gap
        return None

    def _check_single_gap(
        self,
        session: Session,
        learner_id: str,
        prereq: dict,
    ) -> Optional[KnowledgeGap]:
        """Check if a single prerequisite has a gap."""
        mastery = self._mastery_calc.compute_concept_mastery(
            learner_id, prereq["concept_id"]
        )

        if mastery.combined_mastery < prereq["threshold"]:
            return KnowledgeGap(
                concept_id=prereq["concept_id"],
                concept_name=prereq["concept_name"],
                current_mastery=mastery.combined_mastery,
                required_mastery=prereq["threshold"],
                priority="high" if prereq["gating_type"] == "hard" else "medium",
                recommended_atoms=self._get_remediation_atoms(
                    session, prereq["concept_id"], 5
                ),
            )
        return None

    def _get_concepts_in_scope(
        self,
        session: Session,
        cluster_id: Optional[UUID],
    ) -> list[dict]:
        """Get concepts in scope."""
        if cluster_id:
            query = text("""
                SELECT id, name FROM concepts
                WHERE cluster_id = :cluster_id
            """)
            params = {"cluster_id": str(cluster_id)}
        else:
            query = text("SELECT id, name FROM concepts LIMIT 100")
            params = {}

        result = session.execute(query, params)
        return [
            {"id": UUID(str(row.id)), "name": row.name}
            for row in result.fetchall()
        ]

    def _get_remediation_atoms(
        self,
        session: Session,
        concept_id: UUID,
        limit: int = 10,
    ) -> list[UUID]:
        """
        Get atoms for remediation, prioritizing:
        1. Foundational (declarative) atoms first
        2. Lower complexity
        3. Higher quality scores
        """
        query = text("""
            SELECT id
            FROM learning_atoms
            WHERE concept_id = :concept_id
            ORDER BY
                CASE knowledge_type
                    WHEN 'declarative' THEN 1
                    WHEN 'factual' THEN 1
                    WHEN 'conceptual' THEN 2
                    WHEN 'procedural' THEN 3
                    ELSE 4
                END,
                COALESCE(quality_score, 0) DESC,
                created_at
            LIMIT :limit
        """)

        result = session.execute(query, {
            "concept_id": str(concept_id),
            "limit": limit,
        })
        return [UUID(str(row.id)) for row in result.fetchall()]

    def _create_remediation_plan(
        self,
        session: Session,
        learner_id: str,
        gap: KnowledgeGap,
        trigger_type: TriggerType,
        trigger_atom_id: Optional[UUID],
    ) -> RemediationPlan:
        """Create a remediation plan for a gap."""
        # Get more atoms if needed
        atoms = gap.recommended_atoms
        if len(atoms) < 5:
            atoms = self._get_remediation_atoms(session, gap.concept_id, 10)

        plan = RemediationPlan(
            gap_concept_id=gap.concept_id,
            gap_concept_name=gap.concept_name,
            atoms=atoms,
            priority=gap.priority,
            gating_type=GatingType.HARD if gap.priority == "high" else GatingType.SOFT,
            mastery_target=gap.required_mastery,
            estimated_duration_minutes=len(atoms) * 2,
            trigger_type=trigger_type,
            trigger_atom_id=trigger_atom_id,
        )

        return plan

    def _record_remediation_event(
        self,
        session: Session,
        learner_id: str,
        plan: RemediationPlan,
        session_id: Optional[UUID],
    ) -> UUID:
        """Record a remediation event in the database."""
        # Get current mastery
        mastery = self._mastery_calc.compute_concept_mastery(
            learner_id, plan.gap_concept_id
        )

        query = text("""
            INSERT INTO remediation_events (
                session_id, learner_id, trigger_atom_id,
                trigger_type, gap_concept_id,
                mastery_at_trigger, required_mastery, mastery_gap,
                gating_type, remediation_atoms
            ) VALUES (
                :session_id, :learner_id, :trigger_atom_id,
                :trigger_type, :gap_concept_id,
                :mastery_at_trigger, :required_mastery, :mastery_gap,
                :gating_type, :remediation_atoms
            )
            RETURNING id
        """)

        try:
            result = session.execute(query, {
                "session_id": str(session_id) if session_id else None,
                "learner_id": learner_id,
                "trigger_atom_id": str(plan.trigger_atom_id) if plan.trigger_atom_id else None,
                "trigger_type": plan.trigger_type.value,
                "gap_concept_id": str(plan.gap_concept_id),
                "mastery_at_trigger": mastery.combined_mastery,
                "required_mastery": plan.mastery_target,
                "mastery_gap": max(0, plan.mastery_target - mastery.combined_mastery),
                "gating_type": plan.gating_type.value,
                "remediation_atoms": [str(a) for a in plan.atoms],
            })
            session.commit()
            row = result.fetchone()
            return UUID(str(row.id)) if row else None
        except Exception as e:
            logger.error(f"Failed to record remediation event: {e}")
            session.rollback()
            return None

    def _determine_priority(self, mastery: float) -> str:
        """Determine gap priority based on mastery level."""
        if mastery < 0.3:
            return "high"
        elif mastery < 0.5:
            return "medium"
        return "low"

    def _get_concept_info(
        self,
        session: Session,
        concept_id: UUID,
    ) -> Optional[dict]:
        """Get concept info."""
        query = text("SELECT id, name FROM concepts WHERE id = :concept_id")
        result = session.execute(query, {"concept_id": str(concept_id)})
        row = result.fetchone()
        if row:
            return {"id": row.id, "name": row.name}
        return None

    def _get_session(self):
        """Get session context manager."""
        if self._session:
            class SessionWrapper:
                def __init__(self, s):
                    self.session = s
                def __enter__(self):
                    return self.session
                def __exit__(self, *args):
                    pass
            return SessionWrapper(self._session)
        return session_scope()
