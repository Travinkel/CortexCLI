"""
Remediation Router.

Detects knowledge gaps and routes learners to prerequisite content.
Implements Knewton-style just-in-time remediation.

When a learner:
1. Answers incorrectly
2. Shows low confidence
3. Has unmet prerequisite mastery

The router identifies the gap and provides remediation atoms.

Enhanced with JIT Generation:
- When existing atoms are exhausted, generates new content on-the-fly
- Uses NCDE fail modes to guide content type selection
- Caches generated content for reuse
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.adaptive.mastery_calculator import MasteryCalculator
from src.adaptive.models import (
    GatingType,
    KnowledgeGap,
    RemediationPlan,
    TriggerType,
)
from src.db.database import session_scope


# =============================================================================
# FAIL MODE REMEDIATION STRATEGIES
# =============================================================================
# Map NCDE fail modes to content strategies for targeted remediation.
# Each strategy specifies:
# - note_type: Type of study note to generate (or None for practice-only)
# - atom_types: Preferred question types for practice
# - description: Human-readable explanation of the strategy

class NoteType:
    """Types of remediation notes."""
    ELABORATIVE = "elaborative"      # Deep explanation with multiple examples
    CONTRASTIVE = "contrastive"      # Side-by-side comparison of similar concepts
    PROCEDURAL = "procedural"        # Step-by-step worked examples
    SUMMARY = "summary"              # High-level overview and key takeaways
    MNEMONIC = "mnemonic"            # Memory aids and associations


FAIL_MODE_STRATEGIES: dict[str, dict] = {
    # FM1: Encoding Error - Information wasn't stored properly
    # Strategy: Deep explanation + memorization drills
    "FM1_ENCODING": {
        "note_type": NoteType.ELABORATIVE,
        "atom_types": ["flashcard", "cloze"],
        "description": "Deep explanation with multiple examples + memorization drills",
        "exercise_count": 8,
    },

    # FM2: Retrieval Error - Information stored but can't be accessed
    # Strategy: Spaced retrieval practice without new content
    "FM2_RETRIEVAL": {
        "note_type": None,  # No note, just practice
        "atom_types": ["flashcard", "cloze", "mcq"],
        "description": "Spaced retrieval practice to strengthen access pathways",
        "exercise_count": 10,
    },

    # FM3: Discrimination Error - Confusion between similar concepts
    # Strategy: Contrastive analysis + discrimination drills
    "FM3_DISCRIMINATION": {
        "note_type": NoteType.CONTRASTIVE,
        "atom_types": ["matching", "mcq", "true_false"],
        "description": "Side-by-side comparison + discrimination drills",
        "exercise_count": 6,
    },

    # FM4: Integration Error - Can't apply knowledge in context
    # Strategy: Worked examples + procedure practice
    "FM4_INTEGRATION": {
        "note_type": NoteType.PROCEDURAL,
        "atom_types": ["parsons", "numeric"],
        "description": "Worked examples + procedural application practice",
        "exercise_count": 5,
    },

    # FM5: Executive Error - Strategy selection failure
    # Strategy: Strategy review + decision practice
    "FM5_EXECUTIVE": {
        "note_type": NoteType.SUMMARY,
        "atom_types": ["mcq", "true_false"],
        "description": "Strategy review + decision-making practice",
        "exercise_count": 8,
    },

    # FM6: Fatigue/Attention Error - Cognitive overload
    # Strategy: Suggest break, no new content
    "FM6_FATIGUE": {
        "note_type": None,
        "atom_types": [],
        "description": "Suggest break - learner is cognitively depleted",
        "exercise_count": 0,
        "suggest_break": True,
    },

    # Default fallback strategy
    "DEFAULT": {
        "note_type": NoteType.ELABORATIVE,
        "atom_types": ["mcq", "true_false", "cloze"],
        "description": "Balanced review and practice",
        "exercise_count": 5,
    },
}


def get_remediation_strategy(fail_mode: str | None) -> dict:
    """
    Get remediation strategy for a given fail mode.

    Args:
        fail_mode: NCDE fail mode identifier (FM1_ENCODING, FM2_RETRIEVAL, etc.)

    Returns:
        Strategy dict with note_type, atom_types, description, exercise_count
    """
    if not fail_mode:
        return FAIL_MODE_STRATEGIES["DEFAULT"]

    # Normalize fail mode string
    fail_mode_upper = fail_mode.upper().replace(" ", "_").replace("-", "_")

    # Handle both "FM1" and "FM1_ENCODING" formats
    if fail_mode_upper in FAIL_MODE_STRATEGIES:
        return FAIL_MODE_STRATEGIES[fail_mode_upper]

    # Try prefix matching (e.g., "encoding_error" -> "FM1_ENCODING")
    for key, strategy in FAIL_MODE_STRATEGIES.items():
        if fail_mode_upper in key or key in fail_mode_upper:
            return strategy

    return FAIL_MODE_STRATEGIES["DEFAULT"]


class RemediationRouter:
    """
    Route learners to remediation content when gaps are detected.

    Implements just-in-time remediation:
    - Detects gaps from incorrect answers or low mastery
    - Identifies prerequisite concepts needing reinforcement
    - Selects optimal atoms for remediation
    - Tracks remediation outcomes

    Enhanced with JIT Generation:
    - Generates new content when existing atoms are exhausted
    - Uses NCDE fail modes to guide content selection
    """

    # Minimum atoms needed before triggering JIT generation
    MIN_REMEDIATION_ATOMS = 3

    def __init__(
        self,
        session: Session | None = None,
        enable_jit: bool = True,
    ):
        self._session = session
        self._mastery_calc = MasteryCalculator(session)
        self._enable_jit = enable_jit
        self._jit_generator = None

    @property
    def jit_generator(self):
        """Lazy-load JIT generator."""
        if self._jit_generator is None and self._enable_jit:
            from src.adaptive.jit_generator import JITGenerationService

            self._jit_generator = JITGenerationService(session=self._session)
        return self._jit_generator

    def check_remediation_needed(
        self,
        learner_id: str,
        atom_id: UUID,
        is_correct: bool,
        confidence: int | None = None,
    ) -> RemediationPlan | None:
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
        concept_id: UUID | None = None,
        cluster_id: UUID | None = None,
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
                    gap = self._check_single_gap(session, learner_id, prereq)
                    if gap:
                        gaps.append(gap)
            else:
                # Check all concepts in scope
                concepts = self._get_concepts_in_scope(session, cluster_id)
                for concept in concepts:
                    mastery = self._mastery_calc.compute_concept_mastery(learner_id, concept["id"])
                    if mastery.combined_mastery < 0.65:  # Below proficient
                        gaps.append(
                            KnowledgeGap(
                                concept_id=concept["id"],
                                concept_name=concept["name"],
                                current_mastery=mastery.combined_mastery,
                                required_mastery=0.65,
                                priority=self._determine_priority(mastery.combined_mastery),
                                recommended_atoms=self._get_remediation_atoms(
                                    session, concept["id"], 5
                                ),
                            )
                        )

            # Sort by priority (high first)
            priority_order = {"high": 0, "medium": 1, "low": 2}
            gaps.sort(key=lambda g: priority_order.get(g.priority, 2))

            return gaps

    def trigger_remediation(
        self,
        learner_id: str,
        concept_id: UUID,
        trigger_type: TriggerType = TriggerType.MANUAL,
        session_id: UUID | None = None,
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
            mastery = self._mastery_calc.compute_concept_mastery(learner_id, concept_id)

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
            self._record_remediation_event(session, learner_id, plan, session_id)

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
            new_mastery = self._mastery_calc.compute_concept_mastery(learner_id, concept_id)

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

            session.execute(
                update_query,
                {
                    "remediation_id": str(remediation_id),
                    "atoms_completed": atoms_completed,
                    "atoms_correct": atoms_correct,
                    "post_mastery": new_mastery.combined_mastery,
                    "improvement": improvement,
                    "successful": successful,
                },
            )
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
        reason: str | None = None,
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

            session.execute(
                query,
                {
                    "remediation_id": str(remediation_id),
                    "reason": reason,
                },
            )
            session.commit()

    def _get_atom_concept(
        self,
        session: Session,
        atom_id: UUID,
    ) -> UUID | None:
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
    ) -> KnowledgeGap | None:
        """Find the most significant knowledge gap among prerequisites."""
        if not prerequisites:
            return None

        largest_gap = None
        largest_gap_size = 0

        for prereq in prerequisites:
            mastery = self._mastery_calc.compute_concept_mastery(learner_id, prereq["concept_id"])
            gap_size = prereq["threshold"] - mastery.combined_mastery

            if gap_size > largest_gap_size:
                largest_gap_size = gap_size
                largest_gap = KnowledgeGap(
                    concept_id=prereq["concept_id"],
                    concept_name=prereq["concept_name"],
                    current_mastery=mastery.combined_mastery,
                    required_mastery=prereq["threshold"],
                    priority="high" if prereq["gating_type"] == "hard" else "medium",
                    recommended_atoms=self._get_remediation_atoms(session, prereq["concept_id"], 5),
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
    ) -> KnowledgeGap | None:
        """Check if a single prerequisite has a gap."""
        mastery = self._mastery_calc.compute_concept_mastery(learner_id, prereq["concept_id"])

        if mastery.combined_mastery < prereq["threshold"]:
            return KnowledgeGap(
                concept_id=prereq["concept_id"],
                concept_name=prereq["concept_name"],
                current_mastery=mastery.combined_mastery,
                required_mastery=prereq["threshold"],
                priority="high" if prereq["gating_type"] == "hard" else "medium",
                recommended_atoms=self._get_remediation_atoms(session, prereq["concept_id"], 5),
            )
        return None

    def _get_concepts_in_scope(
        self,
        session: Session,
        cluster_id: UUID | None,
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
        return [{"id": UUID(str(row.id)), "name": row.name} for row in result.fetchall()]

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

        result = session.execute(
            query,
            {
                "concept_id": str(concept_id),
                "limit": limit,
            },
        )
        return [UUID(str(row.id)) for row in result.fetchall()]

    def _create_remediation_plan(
        self,
        session: Session,
        learner_id: str,
        gap: KnowledgeGap,
        trigger_type: TriggerType,
        trigger_atom_id: UUID | None,
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
        session_id: UUID | None,
    ) -> UUID:
        """Record a remediation event in the database."""
        # Get current mastery
        mastery = self._mastery_calc.compute_concept_mastery(learner_id, plan.gap_concept_id)

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
            result = session.execute(
                query,
                {
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
                },
            )
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

    # =========================================================================
    # JIT GENERATION INTEGRATION
    # =========================================================================

    async def get_remediation_atoms_with_jit(
        self,
        concept_id: UUID,
        learner_id: str,
        limit: int = 10,
        fail_mode: str | None = None,
    ) -> list[UUID]:
        """
        Get remediation atoms, generating new ones if insufficient.

        Args:
            concept_id: Concept needing remediation
            learner_id: Learner identifier
            limit: Maximum atoms to return
            fail_mode: NCDE diagnosis (encoding_error, discrimination_error, etc.)

        Returns:
            List of atom UUIDs for remediation
        """
        with self._get_session() as session:
            # Get existing atoms
            existing_atoms = self._get_remediation_atoms(session, concept_id, limit)
            existing_count = len(existing_atoms)

            logger.debug(
                f"Remediation for {concept_id}: {existing_count} existing atoms, "
                f"min required: {self.MIN_REMEDIATION_ATOMS}"
            )

            # If we have enough, return them
            if existing_count >= self.MIN_REMEDIATION_ATOMS:
                return existing_atoms

            # JIT generation if enabled and atoms are insufficient
            if self._enable_jit and self.jit_generator:
                try:
                    logger.info(
                        f"Triggering JIT generation for concept {concept_id} "
                        f"(have {existing_count}, need {self.MIN_REMEDIATION_ATOMS})"
                    )

                    result = await self.jit_generator.generate_for_failed_question(
                        concept_id=concept_id,
                        learner_id=learner_id,
                        fail_mode=fail_mode,
                        existing_atom_count=existing_count,
                    )

                    if result.atoms:
                        # Save generated atoms to database
                        new_atom_ids = await self._save_generated_atoms(
                            session, result.atoms, concept_id
                        )
                        logger.info(
                            f"JIT generated {len(new_atom_ids)} atoms in {result.generation_time_ms}ms"
                        )

                        # Combine existing and new atoms
                        return existing_atoms + new_atom_ids[:limit - existing_count]

                except Exception as e:
                    logger.error(f"JIT generation failed: {e}")
                    # Fall through to return existing atoms

            return existing_atoms

    async def _save_generated_atoms(
        self,
        session: Session,
        atoms: list,
        concept_id: UUID,
    ) -> list[UUID]:
        """
        Save JIT-generated atoms to the database.

        Args:
            session: Database session
            atoms: Generated atoms from JITGenerationService
            concept_id: Concept these atoms belong to

        Returns:
            List of saved atom UUIDs
        """
        from uuid import uuid4

        saved_ids = []

        for atom in atoms:
            atom_id = uuid4()

            try:
                # Prepare content_json as string
                content_json_str = None
                if atom.content_json:
                    import json

                    content_json_str = json.dumps(atom.content_json)

                query = text("""
                    INSERT INTO learning_atoms (
                        id, concept_id, card_id, atom_type, front, back,
                        knowledge_type, tags, is_hydrated, fidelity_type,
                        source_fact_basis, quality_score, created_at
                    ) VALUES (
                        :id, :concept_id, :card_id, :atom_type, :front, :back,
                        :knowledge_type, :tags, :is_hydrated, :fidelity_type,
                        :source_fact_basis, :quality_score, NOW()
                    )
                    RETURNING id
                """)

                result = session.execute(
                    query,
                    {
                        "id": str(atom_id),
                        "concept_id": str(concept_id),
                        "card_id": atom.card_id,
                        "atom_type": atom.atom_type.value,
                        "front": atom.front,
                        "back": atom.back,
                        "knowledge_type": atom.knowledge_type.value,
                        "tags": atom.tags,
                        "is_hydrated": atom.is_hydrated,
                        "fidelity_type": atom.fidelity_type,
                        "source_fact_basis": atom.source_fact_basis,
                        "quality_score": atom.quality_score or 75.0,  # Default JIT quality
                    },
                )

                row = result.fetchone()
                if row:
                    saved_ids.append(UUID(str(row.id)))

            except Exception as e:
                logger.error(f"Failed to save JIT atom {atom.card_id}: {e}")
                continue

        session.commit()
        return saved_ids

    def trigger_remediation_with_jit(
        self,
        learner_id: str,
        concept_id: UUID,
        trigger_type: TriggerType = TriggerType.MANUAL,
        fail_mode: str | None = None,
        session_id: UUID | None = None,
    ) -> RemediationPlan:
        """
        Trigger remediation with JIT generation fallback.

        Synchronous wrapper for async JIT generation.

        Args:
            learner_id: Learner identifier
            concept_id: Concept needing remediation
            trigger_type: Why remediation was triggered
            fail_mode: NCDE diagnosis
            session_id: Optional learning session ID

        Returns:
            RemediationPlan with remediation atoms (may include JIT-generated)
        """
        # Run async JIT in sync context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're already in an async context, create a task
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.get_remediation_atoms_with_jit(
                            concept_id, learner_id, 10, fail_mode
                        ),
                    )
                    atoms = future.result(timeout=30)
            else:
                atoms = loop.run_until_complete(
                    self.get_remediation_atoms_with_jit(
                        concept_id, learner_id, 10, fail_mode
                    )
                )
        except Exception as e:
            logger.error(f"JIT remediation failed, falling back: {e}")
            # Fallback to regular remediation
            return self.trigger_remediation(
                learner_id, concept_id, trigger_type, session_id
            )

        with self._get_session() as session:
            # Get concept info
            concept_info = self._get_concept_info(session, concept_id)
            if not concept_info:
                raise ValueError(f"Concept not found: {concept_id}")

            # Get current mastery
            mastery = self._mastery_calc.compute_concept_mastery(learner_id, concept_id)

            # Create plan with JIT-enhanced atoms
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
            self._record_remediation_event(session, learner_id, plan, session_id)

            return plan

    def _get_concept_info(
        self,
        session: Session,
        concept_id: UUID,
    ) -> dict | None:
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
