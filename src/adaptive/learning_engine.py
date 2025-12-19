"""
Adaptive Learning Engine.

Main orchestration layer that coordinates:
- Session management
- Mastery tracking
- Adaptive sequencing
- Just-in-time remediation
- Answer processing

This is the primary interface for learning applications.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.adaptive.mastery_calculator import MasteryCalculator
from src.adaptive.models import (
    AnswerResult,
    AtomPresentation,
    ConceptMastery,
    KnowledgeGap,
    LearningPath,
    RemediationPlan,
    SessionMode,
    SessionProgress,
    SessionState,
    SessionStatus,
    TriggerType,
)
from src.adaptive.neuro_model import (
    CognitiveDiagnosis,
    FailMode,
    diagnose_interaction,
)
from src.adaptive.path_sequencer import PathSequencer
from src.adaptive.persona_service import (
    LearnerPersona,
    PersonaService,
    SessionStatistics,
)
from src.adaptive.remediation_router import RemediationRouter
from src.adaptive.suitability_scorer import SuitabilityScorer
from src.db.database import session_scope

# Optional imports for Cortex 2.0 features
try:
    from src.graph.zscore_engine import (
        AtomMetrics,
        ForceZEngine,
        ZScoreEngine,
        get_forcez_engine,
        get_zscore_engine,
    )

    HAS_ZSCORE = True
except ImportError:
    HAS_ZSCORE = False
    logger.warning("Z-Score engine not available - using default atom ordering")

try:
    from src.integrations.vertex_tutor import get_quick_hint

    HAS_TUTOR = True
except ImportError:
    HAS_TUTOR = False
    logger.debug("Vertex Tutor not available - using basic remediation")


class LearningEngine:
    """
    Adaptive Learning Engine - main orchestration layer.

    Provides a unified interface for:
    - Creating and managing learning sessions
    - Presenting atoms in optimal order
    - Processing answers and triggering remediation
    - Tracking mastery progress
    """

    # Minimum remediation atoms before triggering JIT generation
    MIN_REMEDIATION_ATOMS = 3

    def __init__(self, session: Session | None = None, enable_jit: bool = True):
        self._session = session
        self._mastery_calc = MasteryCalculator(session)
        self._sequencer = PathSequencer(session)
        self._remediator = RemediationRouter(session, enable_jit=enable_jit)
        self._suitability = SuitabilityScorer(session)
        self._enable_jit = enable_jit
        self._jit_generator = None

        # NCDE (Neural Cognitive Diagnosis Engine) state
        # Tracks interaction history per session for cognitive diagnosis
        self._session_histories: dict[UUID, list[dict]] = {}
        self._session_error_streaks: dict[UUID, int] = {}
        self._session_start_times: dict[UUID, datetime] = {}

        # Cortex 2.0 components
        self._zscore_engine: ZScoreEngine | None = None
        self._forcez_engine: ForceZEngine | None = None
        if HAS_ZSCORE:
            self._zscore_engine = get_zscore_engine()
            self._forcez_engine = get_forcez_engine()

        # Persona service for learner profile updates
        self._persona_service: PersonaService | None = None

        # Session statistics accumulator (for persona updates)
        self._session_stats: dict[UUID, SessionStatistics] = {}

    @property
    def jit_generator(self):
        """Lazy-load JIT generator."""
        if self._jit_generator is None and self._enable_jit:
            from src.adaptive.jit_generator import JITGenerationService

            self._jit_generator = JITGenerationService(session=self._session)
        return self._jit_generator

    # =========================================================================
    # Session Management
    # =========================================================================

    def create_session(
        self,
        learner_id: str,
        mode: SessionMode = SessionMode.ADAPTIVE,
        target_concept_id: UUID | None = None,
        target_cluster_id: UUID | None = None,
        atom_count: int = 20,
    ) -> SessionState:
        """
        Create a new learning session.

        Args:
            learner_id: Learner identifier
            mode: Learning mode (adaptive, review, quiz, remediation)
            target_concept_id: Optional specific concept to focus on
            target_cluster_id: Optional cluster scope
            atom_count: Number of atoms for the session

        Returns:
            SessionState with initial configuration
        """
        with self._get_session() as session:
            session_id = uuid4()

            # Get atoms for the session based on mode
            if mode == SessionMode.ADAPTIVE or mode == SessionMode.REVIEW:
                atom_sequence = self._sequencer.get_next_atoms(
                    learner_id,
                    concept_id=target_concept_id,
                    cluster_id=target_cluster_id,
                    count=atom_count,
                    include_review=True,
                )
            elif mode == SessionMode.QUIZ:
                # Quiz mode: new atoms only, no reviews
                atom_sequence = self._sequencer.get_next_atoms(
                    learner_id,
                    concept_id=target_concept_id,
                    cluster_id=target_cluster_id,
                    count=atom_count,
                    include_review=False,
                )
            else:  # Remediation mode
                atom_sequence = []  # Will be populated by remediation plan

            # Get target names
            target_concept_name = None
            target_cluster_name = None

            if target_concept_id:
                concept_info = self._get_concept_info(session, target_concept_id)
                target_concept_name = concept_info.get("name") if concept_info else None

            if target_cluster_id:
                cluster_info = self._get_cluster_info(session, target_cluster_id)
                target_cluster_name = cluster_info.get("name") if cluster_info else None

            # Persist session
            self._create_session_record(
                session,
                session_id=session_id,
                learner_id=learner_id,
                mode=mode,
                target_concept_id=target_concept_id,
                target_cluster_id=target_cluster_id,
                atom_sequence=atom_sequence,
            )

            # Get first atom
            current_atom = None
            next_atom = None
            if atom_sequence:
                current_atom = self._get_atom_presentation(session, atom_sequence[0])
                if len(atom_sequence) > 1:
                    next_atom = self._get_atom_presentation(session, atom_sequence[1])

            # Initialize NCDE tracking for this session
            self._session_histories[session_id] = []
            self._session_error_streaks[session_id] = 0
            self._session_start_times[session_id] = datetime.utcnow()

            # Initialize session statistics for persona updates
            self._session_stats[session_id] = SessionStatistics(
                session_hour=datetime.now().hour,
                session_date=datetime.now(),
            )

            # Initialize persona service for this learner
            self._persona_service = PersonaService(learner_id)

            return SessionState(
                session_id=session_id,
                learner_id=learner_id,
                mode=mode,
                status=SessionStatus.ACTIVE,
                target_concept_name=target_concept_name,
                target_cluster_name=target_cluster_name,
                progress=SessionProgress(
                    atoms_remaining=len(atom_sequence),
                ),
                current_atom=current_atom,
                next_atom=next_atom,
                started_at=datetime.utcnow(),
            )

    def get_session(self, session_id: UUID) -> SessionState | None:
        """
        Get current state of a learning session.

        Args:
            session_id: Session identifier

        Returns:
            SessionState or None if not found
        """
        with self._get_session() as session:
            query = text("""
                SELECT
                    lps.id,
                    lps.learner_id,
                    lps.target_concept_id,
                    lps.target_cluster_id,
                    lps.mode,
                    lps.status,
                    lps.atoms_presented,
                    lps.atoms_correct,
                    lps.atoms_incorrect,
                    lps.remediation_count,
                    lps.current_atom_index,
                    lps.atom_sequence,
                    lps.started_at,
                    lps.completed_at,
                    cc.name as concept_name,
                    kc.name as cluster_name
                FROM learning_path_sessions lps
                LEFT JOIN concepts cc ON lps.target_concept_id = cc.id
                LEFT JOIN knowledge_clusters kc ON lps.target_cluster_id = kc.id
                WHERE lps.id = :session_id
            """)

            result = session.execute(query, {"session_id": str(session_id)})
            row = result.fetchone()

            if not row:
                return None

            # Parse atom sequence
            atom_sequence = row.atom_sequence or []
            current_index = row.current_atom_index or 0

            # Get current and next atoms
            current_atom = None
            next_atom = None

            if atom_sequence and current_index < len(atom_sequence):
                current_atom = self._get_atom_presentation(
                    session, UUID(atom_sequence[current_index])
                )
                if current_index + 1 < len(atom_sequence):
                    next_atom = self._get_atom_presentation(
                        session, UUID(atom_sequence[current_index + 1])
                    )

            return SessionState(
                session_id=session_id,
                learner_id=row.learner_id,
                mode=SessionMode(row.mode) if row.mode else SessionMode.ADAPTIVE,
                status=SessionStatus(row.status) if row.status else SessionStatus.ACTIVE,
                target_concept_name=row.concept_name,
                target_cluster_name=row.cluster_name,
                progress=SessionProgress(
                    atoms_completed=row.atoms_presented or 0,
                    atoms_remaining=len(atom_sequence) - current_index,
                    atoms_correct=row.atoms_correct or 0,
                    atoms_incorrect=row.atoms_incorrect or 0,
                    remediation_count=row.remediation_count or 0,
                ),
                current_atom=current_atom,
                next_atom=next_atom,
                started_at=row.started_at,
            )

    def end_session(
        self,
        session_id: UUID,
        status: SessionStatus = SessionStatus.COMPLETED,
    ) -> SessionState:
        """
        End a learning session.

        Args:
            session_id: Session identifier
            status: Final status (completed, abandoned)

        Returns:
            Final SessionState
        """
        with self._get_session() as session:
            query = text("""
                UPDATE learning_path_sessions
                SET status = :status,
                    completed_at = NOW()
                WHERE id = :session_id
            """)

            session.execute(
                query,
                {
                    "session_id": str(session_id),
                    "status": status.value,
                },
            )
            session.commit()

        return self.get_session(session_id)

    # =========================================================================
    # Answer Processing
    # =========================================================================

    def submit_answer(
        self,
        session_id: UUID,
        atom_id: UUID,
        answer: str,
        confidence: float | None = None,
        time_taken_seconds: int | None = None,
    ) -> AnswerResult:
        """
        Submit an answer and get the result with cognitive diagnosis and remediation.

        This is the core adaptive loop with NCDE (Neural Cognitive Diagnosis Engine):
        1. Evaluate the answer
        2. Run cognitive diagnosis (NCDE) to classify WHY the learner failed/succeeded
        3. Check for knowledge gaps based on diagnosis
        4. Trigger strategy-specific remediation if needed
        5. Update mastery state
        6. Return result with diagnosis and remediation plan

        Args:
            session_id: Session identifier
            atom_id: Atom being answered
            answer: Learner's answer
            confidence: Optional self-reported confidence (0-1)
            time_taken_seconds: Time spent on the atom

        Returns:
            AnswerResult with correctness, cognitive diagnosis, and remediation plan
        """
        with self._get_session() as session:
            # Get atom details
            atom_info = self._get_atom_info(session, atom_id)
            if not atom_info:
                return AnswerResult(
                    is_correct=False,
                    explanation="Atom not found",
                )

            # Evaluate answer
            is_correct, score, explanation, correct_answer = self._evaluate_answer(
                session, atom_id, answer, atom_info
            )

            # =====================================================================
            # NCDE: Neural Cognitive Diagnosis Engine
            # =====================================================================
            # Convert time to milliseconds for NCDE
            response_time_ms = (time_taken_seconds or 5) * 1000

            # Get session history and state for diagnosis
            recent_history = self._session_histories.get(session_id, [])[-20:]
            error_streak = self._session_error_streaks.get(session_id, 0)
            session_start = self._session_start_times.get(session_id, datetime.utcnow())
            session_duration_seconds = int((datetime.utcnow() - session_start).total_seconds())

            # Run cognitive diagnosis
            diagnosis = diagnose_interaction(
                atom=atom_info,
                is_correct=is_correct,
                response_time_ms=response_time_ms,
                recent_history=recent_history,
                session_duration_seconds=session_duration_seconds,
                session_error_streak=error_streak,
                confusable_atoms=None,  # TODO: Query confusable atoms by concept
            )

            # Update session history for future diagnoses
            self._session_histories.setdefault(session_id, []).append(
                {
                    "atom_id": str(atom_id),
                    "concept_id": atom_info.get("concept_id"),
                    "is_correct": is_correct,
                    "response_time_ms": response_time_ms,
                    "fail_mode": diagnosis.fail_mode.value if diagnosis.fail_mode else None,
                    "success_mode": diagnosis.success_mode.value
                    if diagnosis.success_mode
                    else None,
                    "cognitive_state": diagnosis.cognitive_state.value,
                }
            )

            # Update error streak
            if is_correct:
                self._session_error_streaks[session_id] = 0
            else:
                self._session_error_streaks[session_id] = error_streak + 1

            # Log diagnosis for debugging
            if diagnosis.fail_mode:
                logger.info(
                    f"NCDE Diagnosis: {diagnosis.fail_mode.value} "
                    f"(confidence={diagnosis.confidence:.2f}, "
                    f"state={diagnosis.cognitive_state.value}) "
                    f"→ remediation={diagnosis.remediation_type.value}"
                )

            # =====================================================================
            # Record response with diagnosis
            # =====================================================================
            self._record_response(
                session,
                session_id=session_id,
                atom_id=atom_id,
                answer=answer,
                is_correct=is_correct,
                score=score,
                confidence=confidence,
                time_taken=time_taken_seconds,
            )

            # Update session progress
            self._update_session_progress(session, session_id, is_correct)

            # =====================================================================
            # Update Session Statistics for Persona
            # =====================================================================
            self._accumulate_session_stats(
                session_id=session_id,
                atom_info=atom_info,
                is_correct=is_correct,
                response_time_ms=response_time_ms,
                confidence=confidence,
                diagnosis=diagnosis,
            )

            # Get learner_id from session
            learner_id = self._get_session_learner(session, session_id)

            # =====================================================================
            # Strategy-Specific Remediation Based on Diagnosis
            # =====================================================================
            remediation_plan = None
            session_state = self.get_session(session_id)

            if session_state and session_state.mode == SessionMode.ADAPTIVE:
                # Use cognitive diagnosis to guide remediation
                if not is_correct:
                    # Get strategy-specific remediation based on fail mode
                    remediation_plan = self._get_cognitive_remediation(
                        session=session,
                        learner_id=learner_id,
                        atom_id=atom_id,
                        atom_info=atom_info,
                        diagnosis=diagnosis,
                    )

                    # Fall back to prerequisite-based remediation if no cognitive plan
                    if remediation_plan is None:
                        remediation_plan = self._remediator.check_remediation_needed(
                            learner_id=learner_id,
                            atom_id=atom_id,
                            is_correct=False,
                            confidence=int(confidence * 5) if confidence else None,
                        )

                elif confidence is not None and confidence < 0.5:
                    remediation_plan = self._remediator.check_remediation_needed(
                        learner_id=learner_id,
                        atom_id=atom_id,
                        is_correct=True,
                        confidence=int(confidence * 5),
                    )

                # JIT Enhancement: Generate content if remediation atoms are insufficient
                if remediation_plan and self._enable_jit:
                    remediation_plan = self._enhance_remediation_with_jit(
                        session=session,
                        learner_id=learner_id,
                        remediation_plan=remediation_plan,
                        fail_mode=diagnosis.fail_mode.value if diagnosis.fail_mode else None,
                    )

            # Update mastery state
            if atom_info.get("concept_id"):
                self._mastery_calc.update_mastery_state(learner_id, UUID(atom_info["concept_id"]))

            session.commit()

            # Build enhanced explanation with diagnosis insight
            enhanced_explanation = explanation
            if diagnosis.fail_mode and diagnosis.explanation:
                enhanced_explanation = f"{explanation}\n\n[NCDE] {diagnosis.explanation}"

            return AnswerResult(
                is_correct=is_correct,
                score=score,
                explanation=enhanced_explanation,
                correct_answer=correct_answer,
                remediation_triggered=remediation_plan is not None,
                remediation_plan=remediation_plan,
                # Add diagnosis to result (if model supports it)
                # diagnosis=diagnosis.to_dict(),
            )

    def get_next_atom(self, session_id: UUID) -> AtomPresentation | None:
        """
        Get the next atom in the session.

        Handles:
        - Active remediation sequences
        - Normal progression
        - Session completion

        Args:
            session_id: Session identifier

        Returns:
            Next atom or None if session complete
        """
        with self._get_session() as session:
            # Get session state
            query = text("""
                SELECT
                    current_atom_index,
                    atom_sequence,
                    active_remediation_atoms,
                    remediation_index,
                    status
                FROM learning_path_sessions
                WHERE id = :session_id
            """)

            result = session.execute(query, {"session_id": str(session_id)})
            row = result.fetchone()

            if not row or row.status != "active":
                return None

            # Check if in remediation
            if row.active_remediation_atoms and row.remediation_index is not None:
                rem_atoms = row.active_remediation_atoms
                rem_index = row.remediation_index

                if rem_index < len(rem_atoms):
                    # Return next remediation atom
                    atom = self._get_atom_presentation(session, UUID(rem_atoms[rem_index]))
                    if atom:
                        atom.is_remediation = True
                    return atom
                else:
                    # Remediation complete, clear it
                    self._clear_remediation(session, session_id)

            # Normal progression
            atom_sequence = row.atom_sequence or []
            current_index = (row.current_atom_index or 0) + 1

            if current_index < len(atom_sequence):
                # Advance index
                update_query = text("""
                    UPDATE learning_path_sessions
                    SET current_atom_index = :index
                    WHERE id = :session_id
                """)
                session.execute(
                    update_query,
                    {
                        "session_id": str(session_id),
                        "index": current_index,
                    },
                )
                session.commit()

                return self._get_atom_presentation(session, UUID(atom_sequence[current_index]))

            # Session complete
            self.end_session(session_id, SessionStatus.COMPLETED)
            return None

    def inject_remediation(
        self,
        session_id: UUID,
        remediation_plan: RemediationPlan,
    ) -> bool:
        """
        Inject a remediation sequence into the session.

        Args:
            session_id: Session identifier
            remediation_plan: Remediation plan to inject

        Returns:
            True if injection successful
        """
        with self._get_session() as session:
            atom_ids = [str(a) for a in remediation_plan.atoms]

            query = text("""
                UPDATE learning_path_sessions
                SET active_remediation_atoms = :atoms,
                    remediation_index = 0,
                    remediation_count = remediation_count + 1
                WHERE id = :session_id
            """)

            session.execute(
                query,
                {
                    "session_id": str(session_id),
                    "atoms": atom_ids,
                },
            )
            session.commit()

            return True

    # =========================================================================
    # Mastery & Progress
    # =========================================================================

    def get_learner_mastery(
        self,
        learner_id: str,
        concept_ids: list[UUID] | None = None,
        cluster_id: UUID | None = None,
    ) -> list[ConceptMastery]:
        """
        Get mastery state for a learner.

        Args:
            learner_id: Learner identifier
            concept_ids: Optional specific concepts
            cluster_id: Optional cluster scope

        Returns:
            List of ConceptMastery for each concept
        """
        with self._get_session() as session:
            conditions = []
            params = {"learner_id": learner_id}

            if concept_ids:
                concept_id_strs = [str(c) for c in concept_ids]
                conditions.append("cc.id = ANY(:concept_ids)")
                params["concept_ids"] = concept_id_strs
            elif cluster_id:
                conditions.append("cc.cluster_id = :cluster_id")
                params["cluster_id"] = str(cluster_id)

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            query = text(f"""
                SELECT cc.id, cc.name
                FROM concepts cc
                WHERE {where_clause}
                ORDER BY cc.name
            """)

            result = session.execute(query, params)
            concepts = result.fetchall()

            mastery_list = []
            for concept in concepts:
                mastery = self._mastery_calc.compute_concept_mastery(
                    learner_id, UUID(str(concept.id))
                )
                mastery_list.append(mastery)

            return mastery_list

    def get_learning_path(
        self,
        learner_id: str,
        target_concept_id: UUID,
        target_mastery: float = 0.85,
    ) -> LearningPath:
        """
        Get optimal learning path to master a concept.

        Args:
            learner_id: Learner identifier
            target_concept_id: Concept to master
            target_mastery: Target mastery level

        Returns:
            LearningPath with prerequisites and atoms
        """
        return self._sequencer.get_learning_path(learner_id, target_concept_id, target_mastery)

    def get_knowledge_gaps(
        self,
        learner_id: str,
        cluster_id: UUID | None = None,
    ) -> list[KnowledgeGap]:
        """
        Identify knowledge gaps for a learner.

        Args:
            learner_id: Learner identifier
            cluster_id: Optional cluster scope

        Returns:
            List of KnowledgeGap ordered by priority
        """
        return self._remediator.get_knowledge_gaps(learner_id, cluster_id)

    def recalculate_mastery(
        self,
        learner_id: str,
        concept_ids: list[UUID] | None = None,
    ) -> int:
        """
        Recalculate and persist mastery state.

        Args:
            learner_id: Learner identifier
            concept_ids: Optional specific concepts (all if None)

        Returns:
            Number of concepts updated
        """
        with self._get_session() as session:
            if concept_ids:
                concepts = concept_ids
            else:
                # Get all concepts with activity
                query = text("""
                    SELECT DISTINCT concept_id
                    FROM learning_atoms ca
                    WHERE ca.anki_review_count > 0
                    OR EXISTS (
                        SELECT 1 FROM quiz_attempt_answers qaa
                        JOIN quiz_attempts qa ON qaa.attempt_id = qa.id
                        WHERE qaa.atom_id = ca.id
                        AND qa.learner_id = :learner_id
                    )
                """)
                result = session.execute(query, {"learner_id": learner_id})
                concepts = [UUID(str(row.concept_id)) for row in result.fetchall()]

            count = 0
            for concept_id in concepts:
                try:
                    self._mastery_calc.update_mastery_state(learner_id, concept_id)
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to update mastery for {concept_id}: {e}")

            session.commit()
            return count

    # =========================================================================
    # Suitability
    # =========================================================================

    def get_atom_suitability(self, atom_id: UUID) -> dict:
        """
        Get suitability scores for an atom.

        Args:
            atom_id: Atom identifier

        Returns:
            Dict with scores for each atom type
        """
        suitability = self._suitability.score_atom(atom_id)
        return {
            "atom_id": str(suitability.atom_id),
            "current_type": suitability.current_type,
            "recommended_type": suitability.recommended_type,
            "recommendation_confidence": suitability.recommendation_confidence,
            "type_mismatch": suitability.type_mismatch,
            "scores": {
                k: {
                    "score": v.score,
                    "knowledge_signal": v.knowledge_signal,
                    "structure_signal": v.structure_signal,
                    "length_signal": v.length_signal,
                }
                for k, v in suitability.scores.items()
            },
        }

    def batch_compute_suitability(
        self,
        atom_ids: list[UUID] | None = None,
        limit: int = 100,
    ) -> int:
        """
        Batch compute and store suitability scores.

        Args:
            atom_ids: Optional specific atoms
            limit: Max atoms to process

        Returns:
            Number of atoms processed
        """
        return self._suitability.batch_score(atom_ids, limit)

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _create_session_record(
        self,
        session: Session,
        session_id: UUID,
        learner_id: str,
        mode: SessionMode,
        target_concept_id: UUID | None,
        target_cluster_id: UUID | None,
        atom_sequence: list[UUID],
    ) -> None:
        """Create session record in database."""
        atom_id_strs = [str(a) for a in atom_sequence]

        query = text("""
            INSERT INTO learning_path_sessions (
                id, learner_id, target_concept_id, target_cluster_id,
                mode, status, atom_sequence, current_atom_index, started_at
            ) VALUES (
                :id, :learner_id, :concept_id, :cluster_id,
                :mode, 'active', :atoms, 0, NOW()
            )
        """)

        session.execute(
            query,
            {
                "id": str(session_id),
                "learner_id": learner_id,
                "concept_id": str(target_concept_id) if target_concept_id else None,
                "cluster_id": str(target_cluster_id) if target_cluster_id else None,
                "mode": mode.value,
                "atoms": atom_id_strs,
            },
        )
        session.commit()

    def _get_atom_presentation(
        self,
        session: Session,
        atom_id: UUID,
    ) -> AtomPresentation | None:
        """Get atom formatted for presentation."""
        query = text("""
            SELECT
                ca.id,
                ca.atom_type,
                ca.front,
                ca.back,
                ca.quiz_question_metadata as content_json,
                ca.concept_id,
                ca.card_id,
                ca.ccna_section_id,
                cc.name as concept_name
            FROM learning_atoms ca
            LEFT JOIN concepts cc ON ca.concept_id = cc.id
            WHERE ca.id = :atom_id
        """)

        result = session.execute(query, {"atom_id": str(atom_id)})
        row = result.fetchone()

        if not row:
            return None

        return AtomPresentation(
            atom_id=UUID(str(row.id)),
            atom_type=row.atom_type,
            front=row.front,
            back=row.back,
            content_json=row.content_json,
            concept_id=UUID(str(row.concept_id)) if row.concept_id else None,
            concept_name=row.concept_name,
            card_id=row.card_id,
            ccna_section_id=row.ccna_section_id,
        )

    def _get_atom_info(self, session: Session, atom_id: UUID) -> dict | None:
        """Get atom info for answer evaluation."""
        query = text("""
            SELECT
                id, atom_type, front, back, quiz_question_metadata as content_json, concept_id
            FROM learning_atoms
            WHERE id = :atom_id
        """)

        result = session.execute(query, {"atom_id": str(atom_id)})
        row = result.fetchone()

        if row:
            return {
                "id": str(row.id),
                "atom_type": row.atom_type,
                "front": row.front,
                "back": row.back,
                "content_json": row.content_json,
                "concept_id": str(row.concept_id) if row.concept_id else None,
            }
        return None

    def _evaluate_answer(
        self,
        session: Session,
        atom_id: UUID,
        answer: str,
        atom_info: dict,
    ) -> tuple[bool, float, str, str | None]:
        """
        Evaluate learner's answer.

        Returns:
            (is_correct, score, explanation, correct_answer)
        """
        atom_type = atom_info.get("atom_type", "").lower()
        content_json = atom_info.get("content_json") or {}
        back = atom_info.get("back", "")

        # Simple evaluation based on atom type
        if atom_type == "flashcard":
            # For flashcards, we trust self-assessment
            # The answer would be "correct" or "incorrect"
            is_correct = answer.lower() in ["correct", "yes", "1", "true"]
            return (is_correct, 1.0 if is_correct else 0.0, "", back)

        elif atom_type == "true_false":
            correct = content_json.get("correct_answer", "").lower()
            is_correct = answer.lower() == correct
            explanation = content_json.get("explanation", "")
            return (is_correct, 1.0 if is_correct else 0.0, explanation, correct)

        elif atom_type == "mcq":
            correct = content_json.get("correct_answer", "")
            is_correct = answer.strip().upper() == correct.strip().upper()
            explanation = content_json.get("explanation", "")
            return (is_correct, 1.0 if is_correct else 0.0, explanation, correct)

        elif atom_type == "cloze":
            correct = content_json.get("answer", "")
            # Fuzzy match for cloze
            is_correct = answer.strip().lower() == correct.strip().lower()
            return (is_correct, 1.0 if is_correct else 0.0, "", correct)

        elif atom_type in ["parsons", "sequence", "ranking"]:
            # Order-based: answer should be comma-separated indices
            correct_order = content_json.get("correct_order", [])
            try:
                answer_order = [int(x.strip()) for x in answer.split(",")]
                is_correct = answer_order == correct_order
                # Partial credit for partially correct order
                if not is_correct and correct_order:
                    matches = sum(1 for a, c in zip(answer_order, correct_order) if a == c)
                    score = matches / len(correct_order)
                else:
                    score = 1.0 if is_correct else 0.0
                return (is_correct, score, "", str(correct_order))
            except ValueError:
                return (False, 0.0, "Invalid answer format", str(correct_order))

        elif atom_type == "matching":
            # Matching: answer should be pairs like "A-1,B-2,C-3"
            correct_pairs = content_json.get("correct_pairs", {})
            try:
                answer_pairs = dict(p.split("-") for p in answer.split(","))
                is_correct = answer_pairs == correct_pairs
                if not is_correct and correct_pairs:
                    matches = sum(1 for k, v in answer_pairs.items() if correct_pairs.get(k) == v)
                    score = matches / len(correct_pairs)
                else:
                    score = 1.0 if is_correct else 0.0
                return (is_correct, score, "", str(correct_pairs))
            except (ValueError, AttributeError):
                return (False, 0.0, "Invalid answer format", str(correct_pairs))

        # Default: basic string match
        is_correct = answer.strip().lower() == back.strip().lower()
        return (is_correct, 1.0 if is_correct else 0.0, "", back)

    def _record_response(
        self,
        session: Session,
        session_id: UUID,
        atom_id: UUID,
        answer: str,
        is_correct: bool,
        score: float,
        confidence: float | None,
        time_taken: int | None,
    ) -> None:
        """Record answer response in database."""
        query = text("""
            INSERT INTO session_atom_responses (
                id, session_id, atom_id, answer_given, is_correct,
                score, confidence_rating, time_taken_seconds, answered_at
            ) VALUES (
                :id, :session_id, :atom_id, :answer, :correct,
                :score, :confidence, :time_taken, NOW()
            )
        """)

        session.execute(
            query,
            {
                "id": str(uuid4()),
                "session_id": str(session_id),
                "atom_id": str(atom_id),
                "answer": answer,
                "correct": is_correct,
                "score": score,
                "confidence": confidence,
                "time_taken": time_taken,
            },
        )

    def _update_session_progress(
        self,
        session: Session,
        session_id: UUID,
        is_correct: bool,
    ) -> None:
        """Update session progress counters."""
        if is_correct:
            query = text("""
                UPDATE learning_path_sessions
                SET atoms_presented = atoms_presented + 1,
                    atoms_correct = atoms_correct + 1
                WHERE id = :session_id
            """)
        else:
            query = text("""
                UPDATE learning_path_sessions
                SET atoms_presented = atoms_presented + 1,
                    atoms_incorrect = atoms_incorrect + 1
                WHERE id = :session_id
            """)

        session.execute(query, {"session_id": str(session_id)})

    def _get_session_learner(self, session: Session, session_id: UUID) -> str:
        """Get learner_id for a session."""
        query = text("""
            SELECT learner_id FROM learning_path_sessions WHERE id = :session_id
        """)
        result = session.execute(query, {"session_id": str(session_id)})
        row = result.fetchone()
        return row.learner_id if row else ""

    def _clear_remediation(self, session: Session, session_id: UUID) -> None:
        """Clear active remediation from session."""
        query = text("""
            UPDATE learning_path_sessions
            SET active_remediation_atoms = NULL,
                remediation_index = NULL
            WHERE id = :session_id
        """)
        session.execute(query, {"session_id": str(session_id)})
        session.commit()

    def _get_concept_info(self, session: Session, concept_id: UUID) -> dict | None:
        """Get concept info."""
        query = text("""
            SELECT id, name FROM concepts WHERE id = :concept_id
        """)
        result = session.execute(query, {"concept_id": str(concept_id)})
        row = result.fetchone()
        if row:
            return {"id": str(row.id), "name": row.name}
        return None

    def _get_cluster_info(self, session: Session, cluster_id: UUID) -> dict | None:
        """Get cluster info."""
        query = text("""
            SELECT id, name FROM clusters WHERE id = :cluster_id
        """)
        result = session.execute(query, {"concept_id": str(cluster_id)})
        row = result.fetchone()
        if row:
            return {"id": str(row.id), "name": row.name}
        return None

    # =========================================================================
    # NCDE: Strategy-Specific Remediation
    # =========================================================================

    def _get_cognitive_remediation(
        self,
        session: Session,
        learner_id: str,
        atom_id: UUID,
        atom_info: dict,
        diagnosis: CognitiveDiagnosis,
    ) -> RemediationPlan | None:
        """
        Get strategy-specific remediation based on cognitive diagnosis.

        Maps FailMode to specific remediation strategies:
        - ENCODING_ERROR → Elaborate with different framing
        - RETRIEVAL_ERROR → Standard spaced repetition
        - DISCRIMINATION_ERROR → Contrastive pairs
        - INTEGRATION_ERROR → Worked examples (Parsons/numeric)
        - EXECUTIVE_ERROR → Forced latency (no atom change)
        - FATIGUE_ERROR → Suggest break (no atom change)

        Args:
            session: Database session
            learner_id: Learner identifier
            atom_id: The atom that was answered incorrectly
            atom_info: Atom metadata
            diagnosis: Cognitive diagnosis from NCDE

        Returns:
            RemediationPlan with strategy-specific atoms, or None
        """
        from src.adaptive.models import GatingType

        fail_mode = diagnosis.fail_mode
        concept_id = atom_info.get("concept_id")

        # No remediation for non-actionable fail modes
        if fail_mode in (FailMode.EXECUTIVE_ERROR, FailMode.FATIGUE_ERROR):
            # These require behavioral change, not more atoms
            logger.debug(f"FailMode {fail_mode} requires behavioral intervention, not atoms")
            return None

        if not concept_id:
            return None

        concept_uuid = UUID(concept_id) if isinstance(concept_id, str) else concept_id

        # Get concept name
        concept_info = self._get_concept_info(session, concept_uuid)
        concept_name = concept_info.get("name", "Unknown") if concept_info else "Unknown"

        # Strategy-specific atom selection
        atoms: list[UUID] = []

        if fail_mode == FailMode.DISCRIMINATION_ERROR:
            # Get contrastive/confusable atoms from same concept
            atoms = self._get_contrastive_atoms(session, concept_uuid, atom_id, limit=5)
            priority = "high"
            gating = GatingType.SOFT

        elif fail_mode == FailMode.INTEGRATION_ERROR:
            # Get worked example atoms (parsons, numeric) from same concept
            atoms = self._get_worked_example_atoms(session, concept_uuid, limit=5)
            priority = "high"
            gating = GatingType.SOFT

        elif fail_mode == FailMode.ENCODING_ERROR:
            # Get declarative atoms with elaboration potential
            atoms = self._get_elaboration_atoms(session, concept_uuid, atom_id, limit=5)
            priority = "medium"
            gating = GatingType.SOFT

        else:  # RETRIEVAL_ERROR or default
            # Standard remediation: foundational atoms
            atoms = self._remediator._get_remediation_atoms(session, concept_uuid, limit=5)
            priority = "medium"
            gating = GatingType.SOFT

        if not atoms:
            return None

        return RemediationPlan(
            gap_concept_id=concept_uuid,
            gap_concept_name=concept_name,
            atoms=atoms,
            priority=priority,
            gating_type=gating,
            mastery_target=0.65,
            estimated_duration_minutes=len(atoms) * 2,
            trigger_type=TriggerType.INCORRECT_ANSWER,
            trigger_atom_id=atom_id,
        )

    def _get_contrastive_atoms(
        self,
        session: Session,
        concept_id: UUID,
        exclude_atom_id: UUID,
        limit: int = 5,
    ) -> list[UUID]:
        """
        Get atoms for contrastive training (discrimination error).

        Returns atoms from the same concept that are likely confusable
        with the failed atom. Prioritizes MCQ and true/false for
        discrimination practice.
        """
        query = text("""
            SELECT id
            FROM learning_atoms
            WHERE concept_id = :concept_id
            AND id != :exclude_id
            AND atom_type IN ('mcq', 'true_false', 'flashcard')
            ORDER BY
                CASE atom_type
                    WHEN 'mcq' THEN 1  -- MCQs best for discrimination
                    WHEN 'true_false' THEN 2
                    ELSE 3
                END,
                COALESCE(quality_score, 0) DESC
            LIMIT :limit
        """)

        result = session.execute(
            query,
            {
                "concept_id": str(concept_id),
                "exclude_id": str(exclude_atom_id),
                "limit": limit,
            },
        )
        return [UUID(str(row.id)) for row in result.fetchall()]

    def _get_worked_example_atoms(
        self,
        session: Session,
        concept_id: UUID,
        limit: int = 5,
    ) -> list[UUID]:
        """
        Get atoms for worked example training (integration error).

        Returns Parsons problems and numeric atoms that show
        step-by-step reasoning.
        """
        query = text("""
            SELECT id
            FROM learning_atoms
            WHERE concept_id = :concept_id
            AND atom_type IN ('parsons', 'numeric', 'ranking', 'sequence')
            ORDER BY
                CASE atom_type
                    WHEN 'parsons' THEN 1  -- Parsons best for integration
                    WHEN 'sequence' THEN 2
                    WHEN 'ranking' THEN 3
                    ELSE 4
                END,
                COALESCE(quality_score, 0) DESC
            LIMIT :limit
        """)

        result = session.execute(
            query,
            {
                "concept_id": str(concept_id),
                "limit": limit,
            },
        )
        atoms = [UUID(str(row.id)) for row in result.fetchall()]

        # Fall back to any atoms if no procedural ones found
        if not atoms:
            return self._remediator._get_remediation_atoms(session, concept_id, limit)

        return atoms

    def _get_elaboration_atoms(
        self,
        session: Session,
        concept_id: UUID,
        exclude_atom_id: UUID,
        limit: int = 5,
    ) -> list[UUID]:
        """
        Get atoms for elaboration (encoding error).

        Returns foundational atoms that present the concept
        from different angles (cloze, flashcard, definition).
        """
        query = text("""
            SELECT id
            FROM learning_atoms
            WHERE concept_id = :concept_id
            AND id != :exclude_id
            AND atom_type IN ('flashcard', 'cloze', 'definition')
            ORDER BY
                CASE knowledge_type
                    WHEN 'declarative' THEN 1
                    WHEN 'factual' THEN 1
                    WHEN 'conceptual' THEN 2
                    ELSE 3
                END,
                COALESCE(quality_score, 0) DESC
            LIMIT :limit
        """)

        result = session.execute(
            query,
            {
                "concept_id": str(concept_id),
                "exclude_id": str(exclude_atom_id),
                "limit": limit,
            },
        )
        atoms = [UUID(str(row.id)) for row in result.fetchall()]

        # Fall back to standard remediation if no elaboration atoms
        if not atoms:
            return self._remediator._get_remediation_atoms(session, concept_id, limit)

        return atoms

    # =========================================================================
    # JIT Content Generation
    # =========================================================================

    def _enhance_remediation_with_jit(
        self,
        session: Session,
        learner_id: str,
        remediation_plan: RemediationPlan,
        fail_mode: str | None = None,
    ) -> RemediationPlan:
        """
        Enhance a remediation plan with JIT-generated content if atoms are insufficient.

        Called after cognitive/prerequisite remediation to fill gaps with AI-generated
        content when existing atoms are exhausted.

        Args:
            session: Database session
            learner_id: Learner identifier
            remediation_plan: Existing remediation plan (may have few atoms)
            fail_mode: NCDE diagnosis fail mode (guides content type selection)

        Returns:
            Enhanced RemediationPlan with JIT-generated atoms if needed
        """
        existing_count = len(remediation_plan.atoms)

        # If we have enough atoms, return the plan as-is
        if existing_count >= self.MIN_REMEDIATION_ATOMS:
            return remediation_plan

        # No JIT generator available
        if not self.jit_generator:
            logger.debug("JIT generator not available, returning original plan")
            return remediation_plan

        logger.info(
            f"JIT enhancing remediation for concept {remediation_plan.gap_concept_id}: "
            f"have {existing_count}, need {self.MIN_REMEDIATION_ATOMS}"
        )

        try:
            import asyncio

            # Run async JIT generation
            result = asyncio.run(
                self.jit_generator.generate_for_failed_question(
                    concept_id=remediation_plan.gap_concept_id,
                    learner_id=learner_id,
                    fail_mode=fail_mode,
                    existing_atom_count=existing_count,
                )
            )

            if result.atoms:
                # Save generated atoms to database
                new_atom_ids = self._save_jit_atoms(
                    session, result.atoms, remediation_plan.gap_concept_id
                )

                logger.info(
                    f"JIT generated {len(new_atom_ids)} atoms in {result.generation_time_ms}ms"
                )

                # Create enhanced plan with combined atoms
                combined_atoms = list(remediation_plan.atoms) + new_atom_ids
                return RemediationPlan(
                    gap_concept_id=remediation_plan.gap_concept_id,
                    gap_concept_name=remediation_plan.gap_concept_name,
                    atoms=combined_atoms,
                    priority=remediation_plan.priority,
                    gating_type=remediation_plan.gating_type,
                    mastery_target=remediation_plan.mastery_target,
                    estimated_duration_minutes=len(combined_atoms) * 2,
                    trigger_type=remediation_plan.trigger_type,
                    trigger_atom_id=remediation_plan.trigger_atom_id,
                )

        except Exception as e:
            logger.error(f"JIT enhancement failed: {e}")
            # Return original plan on error

        return remediation_plan

    def _save_jit_atoms(
        self,
        session: Session,
        atoms: list,
        concept_id: UUID,
    ) -> list[UUID]:
        """Save JIT-generated atoms to the database."""
        from uuid import uuid4
        import json

        saved_ids = []

        for atom in atoms:
            atom_id = uuid4()

            try:
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
                        "quality_score": atom.quality_score or 75.0,
                    },
                )

                row = result.fetchone()
                if row:
                    saved_ids.append(UUID(str(row.id)))

            except Exception as e:
                logger.error(f"Failed to save JIT atom {atom.card_id}: {e}")
                continue

        return saved_ids

    # =========================================================================
    # Persona & Session Statistics
    # =========================================================================

    def _accumulate_session_stats(
        self,
        session_id: UUID,
        atom_info: dict,
        is_correct: bool,
        response_time_ms: int,
        confidence: float | None,
        diagnosis: CognitiveDiagnosis,
    ) -> None:
        """
        Accumulate statistics for persona updates at session end.

        Called after every answer to build up session-level metrics.
        """
        if session_id not in self._session_stats:
            self._session_stats[session_id] = SessionStatistics(
                session_hour=datetime.now().hour,
                session_date=datetime.now(),
            )

        stats = self._session_stats[session_id]

        # Update overall counts
        if is_correct:
            stats.total_correct += 1
        else:
            stats.total_incorrect += 1

        # Update by knowledge type
        knowledge_type = atom_info.get("knowledge_type", "factual")
        if is_correct:
            stats.correct_by_type[knowledge_type] = stats.correct_by_type.get(knowledge_type, 0) + 1
        else:
            stats.incorrect_by_type[knowledge_type] = (
                stats.incorrect_by_type.get(knowledge_type, 0) + 1
            )

        # Update by atom type (mechanism)
        atom_type = atom_info.get("atom_type", "flashcard")
        if is_correct:
            stats.correct_by_mechanism[atom_type] = stats.correct_by_mechanism.get(atom_type, 0) + 1
        else:
            stats.incorrect_by_mechanism[atom_type] = (
                stats.incorrect_by_mechanism.get(atom_type, 0) + 1
            )

        # Update response time (rolling average)
        total = stats.total_correct + stats.total_incorrect
        stats.avg_response_time_ms = (
            (stats.avg_response_time_ms * (total - 1) + response_time_ms) // total
            if total > 0
            else response_time_ms
        )

        # Track calibration (confidence vs actual)
        if confidence is not None:
            if confidence > 0.6:  # High confidence
                if is_correct:
                    stats.high_confidence_correct += 1
                else:
                    stats.high_confidence_incorrect += 1
            else:  # Low confidence
                if is_correct:
                    stats.low_confidence_correct += 1
                else:
                    stats.low_confidence_incorrect += 1

        # Track discrimination errors as confusion pairs
        if diagnosis.fail_mode == FailMode.DISCRIMINATION_ERROR:
            concept = atom_info.get("concept_name", "")
            if concept:
                stats.confusion_pairs.append((concept, atom_type))

    def end_session_with_persona(self, session_id: UUID) -> LearnerPersona | None:
        """
        End a learning session and update the learner persona.

        This should be called when the user finishes a study session.
        It updates the persona based on accumulated session statistics
        and cleans up session state.

        Args:
            session_id: The session to end

        Returns:
            Updated LearnerPersona, or None if session not found
        """
        # Calculate session duration
        start_time = self._session_start_times.get(session_id)
        if start_time:
            duration_minutes = int((datetime.utcnow() - start_time).total_seconds() / 60)
        else:
            duration_minutes = 25  # Default

        # Get session stats
        stats = self._session_stats.get(session_id)
        if stats:
            stats.session_duration_minutes = duration_minutes

            # Update persona
            if self._persona_service:
                persona = self._persona_service.update_from_session(stats)
                logger.info(
                    f"Session {session_id} ended: "
                    f"accuracy={stats.overall_accuracy:.1%}, "
                    f"atoms={stats.total_correct + stats.total_incorrect}, "
                    f"duration={duration_minutes}min"
                )

                # Clean up session state
                self._cleanup_session(session_id)
                return persona

        # Clean up even if no stats
        self._cleanup_session(session_id)
        return None

    def _cleanup_session(self, session_id: UUID) -> None:
        """Clean up session tracking state."""
        self._session_histories.pop(session_id, None)
        self._session_error_streaks.pop(session_id, None)
        self._session_start_times.pop(session_id, None)
        self._session_stats.pop(session_id, None)

    def get_learner_persona(self, learner_id: str = "default") -> LearnerPersona:
        """
        Get the learner's current persona profile.

        Args:
            learner_id: Learner identifier

        Returns:
            LearnerPersona with current profile
        """
        service = PersonaService(learner_id)
        return service.get_persona()

    # =========================================================================
    # Z-Score & Force Z Integration
    # =========================================================================

    def get_focus_stream_atoms(
        self,
        learner_id: str,
        limit: int = 20,
        active_project_ids: list[str] | None = None,
    ) -> list[UUID]:
        """
        Get atoms for the Focus Stream based on Z-Score.

        The Focus Stream contains atoms that most need attention right now,
        based on the Cortex 2.0 Z-Score algorithm combining:
        - Decay (time since last touch)
        - Centrality (importance in knowledge graph)
        - Project relevance (alignment with active goals)
        - Novelty (new atoms that need encoding)

        Args:
            learner_id: Learner identifier
            limit: Maximum atoms to return
            active_project_ids: Active learning project IDs

        Returns:
            List of atom UUIDs sorted by Z-Score (highest first)
        """
        if not self._zscore_engine:
            logger.debug("Z-Score engine not available, falling back to default ordering")
            return []

        with self._get_session() as session:
            # Get all atoms with their metrics
            query = text("""
                SELECT
                    a.id,
                    a.last_reviewed_at,
                    a.review_count,
                    a.stability,
                    a.difficulty,
                    a.memory_state
                FROM learning_atoms a
                JOIN learner_atom_states las ON a.id = las.atom_id AND las.learner_id = :learner_id
                WHERE a.memory_state != 'suspended'
                ORDER BY a.last_reviewed_at ASC NULLS FIRST
                LIMIT :limit * 2
            """)

            result = session.execute(query, {"learner_id": learner_id, "limit": limit})
            rows = result.fetchall()

            if not rows:
                return []

            # Build metrics for Z-Score computation
            metrics_list = []
            for row in rows:
                metrics_list.append(
                    AtomMetrics(
                        atom_id=str(row.id),
                        last_touched=row.last_reviewed_at,
                        review_count=row.review_count or 0,
                        stability=float(row.stability or 0),
                        difficulty=float(row.difficulty or 0.3),
                        memory_state=row.memory_state or "NEW",
                    )
                )

            # Compute Z-Scores
            results = self._zscore_engine.compute_batch(
                metrics_list,
                active_project_ids=active_project_ids or [],
            )

            # Filter to activated atoms and sort by Z-Score
            activated = [r for r in results if r.z_activation]
            activated.sort(key=lambda r: r.z_score, reverse=True)

            return [UUID(r.atom_id) for r in activated[:limit]]

    def check_force_z_backtrack(
        self,
        atom_id: UUID,
        session_id: UUID,
    ) -> list[UUID] | None:
        """
        Check if Force Z backtracking is needed for a struggling atom.

        Called when a learner repeatedly fails on an atom. Force Z
        identifies weak prerequisite atoms that should be remediated first.

        Args:
            atom_id: The atom the learner is struggling with
            session_id: Current session ID

        Returns:
            List of prerequisite atom UUIDs to inject, or None
        """
        if not self._forcez_engine:
            return None

        result = self._forcez_engine.analyze(str(atom_id))

        if not result.should_backtrack:
            return None

        logger.info(f"Force Z activated: {result.explanation}")

        # Convert to UUIDs
        return [UUID(aid) for aid in result.recommended_path]

    def get_tutor_hint(
        self,
        atom_info: dict,
        diagnosis: CognitiveDiagnosis,
    ) -> str:
        """
        Get a quick tutoring hint based on the diagnosis.

        For deeper tutoring sessions, use the Vertex Tutor directly.

        Args:
            atom_info: Atom metadata
            diagnosis: Cognitive diagnosis from NCDE

        Returns:
            Hint string
        """
        if HAS_TUTOR and diagnosis.fail_mode:
            return get_quick_hint(atom_info, diagnosis.fail_mode)

        # Fallback hint
        concept = atom_info.get("concept_name", "this concept")
        return f"Take a moment to think about {concept}. What do you already know about it?"

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
