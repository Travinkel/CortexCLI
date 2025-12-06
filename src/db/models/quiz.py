"""
Quiz models for question management and quality assurance.

Implements:
- QuizQuestion: Question content with type-specific JSONB structure
- QuizDefinition: Quiz configuration at concept/cluster level
- QuizPassage: Passages for passage-based questions

Question Types:
- mcq: Multiple choice question
- true_false: True/False
- short_answer: Fill in blank, short answer
- matching: Match pairs (max 6 pairs for working memory)
- ranking: Order items
- passage_based: Question about a passage
- numeric: Calculation/numerical answer with steps
- parsons: Procedure ordering (code/step blocks)

Knowledge Types (from right-learning research):
- factual: Recall facts (passing 70%)
- conceptual: Understand relationships (passing 80%)
- procedural: Execute steps (passing 85%)
- metacognitive: Self-regulation strategies

Mastery Weights:
- Quiz: 37.5% (quiz_mastery_weight)
- Review: 62.5% (review_mastery_weight)
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, Text, func, ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .canonical import CleanAtom, CleanConcept, CleanConceptCluster
    from .prerequisites import QuestionPool


class QuizQuestion(Base):
    """
    Quiz question with type-specific content and quality metadata.

    The question_content JSONB structure varies by question_type:

    MCQ:
        {
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_index": 0,
            "explanations": {
                "0": "Correct because...",
                "1": "Wrong because...",
                "2": "Wrong because...",
                "3": "Wrong because..."
            }
        }

    True/False:
        {
            "correct": true,
            "explanation": "This is true/false because..."
        }

    Short Answer:
        {
            "correct_answers": ["answer1", "answer 1", "Answer1"],
            "case_sensitive": false,
            "partial_match": false
        }

    Matching:
        {
            "pairs": [
                {"left": "Term A", "right": "Definition A"},
                {"left": "Term B", "right": "Definition B"}
            ],
            "shuffle_right": true
        }

    Ranking:
        {
            "items": ["First", "Second", "Third"],
            "correct_order": [0, 1, 2]
        }

    Passage-based:
        {
            "passage_id": "uuid-of-passage",
            "question": "According to the passage..."
        }

    Numeric:
        {
            "answer": 42.5,
            "tolerance": 0.1,
            "unit": "ms",
            "steps": [
                "Step 1: Calculate latency...",
                "Step 2: Add propagation delay..."
            ],
            "explanation": "The total delay is calculated by..."
        }

    Parsons:
        {
            "blocks": [
                "Configure interface IP",
                "Enable the interface",
                "Save configuration",
                "Verify connectivity"
            ],
            "correct_order": [0, 1, 2, 3],
            "distractors": ["Restart router"],
            "explanation": "The correct order follows..."
        }
    """

    __tablename__ = "quiz_questions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid()
    )
    atom_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_atoms.id", ondelete="CASCADE"),
        nullable=False
    )

    # Question type
    question_type: Mapped[str] = mapped_column(Text, nullable=False)

    # Content structure (JSONB for flexibility per type)
    question_content: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Difficulty and cognitive load
    difficulty: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
        default=Decimal("0.5")
    )
    intrinsic_load: Mapped[int | None] = mapped_column(Integer)  # 1-5
    knowledge_type: Mapped[str | None] = mapped_column(Text)

    # Scoring
    points: Mapped[int] = mapped_column(Integer, default=1)
    partial_credit: Mapped[bool] = mapped_column(Boolean, default=False)

    # Quality metrics
    distractor_quality_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    answer_clarity_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    quality_issues: Mapped[list | None] = mapped_column(ARRAY(Text))

    # Pool membership
    pool_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("question_pools.id", ondelete="SET NULL")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    atom: Mapped["CleanAtom"] = relationship(
        "CleanAtom",
        back_populates="quiz_question"
    )
    pool: Mapped["QuestionPool | None"] = relationship(
        "QuestionPool",
        back_populates="questions",
        foreign_keys=[pool_id]
    )

    def __repr__(self) -> str:
        return f"<QuizQuestion(type={self.question_type}, difficulty={self.difficulty})>"

    @property
    def passing_threshold(self) -> float:
        """Get passing threshold based on knowledge type."""
        thresholds = {
            "factual": 0.70,
            "conceptual": 0.80,
            "procedural": 0.85,
            "metacognitive": 0.85,
        }
        return thresholds.get(self.knowledge_type, 0.70)

    def validate_content_structure(self) -> list[str]:
        """
        Validate the question_content structure for the question type.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        content = self.question_content or {}

        if self.question_type == "mcq":
            if "options" not in content:
                errors.append("MCQ requires 'options' array")
            elif not isinstance(content["options"], list) or len(content["options"]) < 2:
                errors.append("MCQ requires at least 2 options")
            elif len(content["options"]) > 6:
                errors.append("MCQ should have max 6 options (working memory limit)")
            if "correct_index" not in content:
                errors.append("MCQ requires 'correct_index'")

        elif self.question_type == "true_false":
            if "correct" not in content:
                errors.append("True/False requires 'correct' boolean")

        elif self.question_type == "short_answer":
            if "correct_answers" not in content:
                errors.append("Short answer requires 'correct_answers' array")
            elif not isinstance(content["correct_answers"], list) or len(content["correct_answers"]) == 0:
                errors.append("Short answer requires at least one correct answer")

        elif self.question_type == "matching":
            if "pairs" not in content:
                errors.append("Matching requires 'pairs' array")
            elif not isinstance(content["pairs"], list):
                errors.append("Matching 'pairs' must be an array")
            elif len(content["pairs"]) > 6:
                errors.append("Matching should have max 6 pairs (working memory limit)")
            else:
                for i, pair in enumerate(content["pairs"]):
                    if "left" not in pair or "right" not in pair:
                        errors.append(f"Matching pair {i} requires 'left' and 'right'")

        elif self.question_type == "ranking":
            if "items" not in content:
                errors.append("Ranking requires 'items' array")
            if "correct_order" not in content:
                errors.append("Ranking requires 'correct_order' array")
            elif len(content.get("items", [])) != len(content.get("correct_order", [])):
                errors.append("Ranking items and correct_order must have same length")

        elif self.question_type == "passage_based":
            if "passage_id" not in content:
                errors.append("Passage-based requires 'passage_id'")
            if "question" not in content:
                errors.append("Passage-based requires 'question' text")

        elif self.question_type == "numeric":
            # Numeric: Binary/Hex/Subnetting calculations (answer can be string for binary/hex)
            if "answer" not in content:
                errors.append("Numeric requires 'answer' value")
            # Note: answer can be string (for binary "11000000") or number (for decimal 192)
            if "steps" not in content:
                errors.append("Numeric requires 'steps' for solution walkthrough")
            # Optional validation for answer_type
            if "answer_type" in content:
                valid_types = ["binary", "decimal", "hexadecimal", "ip_address", "subnet_mask", "integer"]
                if content["answer_type"] not in valid_types:
                    errors.append(f"Numeric 'answer_type' must be one of: {valid_types}")

        elif self.question_type == "parsons":
            if "blocks" not in content:
                errors.append("Parsons requires 'blocks' array")
            elif not isinstance(content["blocks"], list):
                errors.append("Parsons 'blocks' must be an array")
            elif len(content["blocks"]) < 2:
                errors.append("Parsons requires at least 2 blocks to order")
            elif len(content["blocks"]) > 8:
                errors.append("Parsons should have max 8 blocks (cognitive limit)")
            if "correct_order" not in content:
                errors.append("Parsons requires 'correct_order' array")
            elif not isinstance(content["correct_order"], list):
                errors.append("Parsons 'correct_order' must be an array")
            elif len(content.get("blocks", [])) != len(content.get("correct_order", [])):
                errors.append("Parsons blocks and correct_order must have same length")

        return errors

    def get_option_count(self) -> int | None:
        """Get number of options for MCQ/matching questions."""
        if self.question_type == "mcq":
            return len(self.question_content.get("options", []))
        elif self.question_type == "matching":
            return len(self.question_content.get("pairs", []))
        return None


class QuizDefinition(Base):
    """
    Quiz configuration at concept/cluster level.

    Defines quiz parameters including:
    - Question selection (count, time limit)
    - Passing thresholds
    - Mastery weights (37.5% quiz + 62.5% review)
    - Randomization settings
    - Adaptive difficulty

    Attributes:
        question_count: Number of questions per attempt
        time_limit_minutes: Optional time constraint
        passing_threshold: Minimum score to pass (0-1)
        quiz_mastery_weight: Quiz contribution to mastery (default 0.375)
        review_mastery_weight: Review contribution to mastery (default 0.625)
    """

    __tablename__ = "quiz_definitions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid()
    )

    # Scope
    concept_cluster_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("concept_clusters.id", ondelete="SET NULL")
    )
    concept_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("concepts.id", ondelete="SET NULL")
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Question selection
    question_count: Mapped[int] = mapped_column(Integer, default=10)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer)

    # Passing threshold
    passing_threshold: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=Decimal("0.70")
    )

    # Mastery weights (from right-learning: 37.5% quiz + 62.5% review)
    quiz_mastery_weight: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=Decimal("0.375")
    )
    review_mastery_weight: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=Decimal("0.625")
    )

    # Attempt configuration
    max_attempts: Mapped[int | None] = mapped_column(Integer)
    allow_resume: Mapped[bool] = mapped_column(Boolean, default=True)
    randomize_questions: Mapped[bool] = mapped_column(Boolean, default=True)
    randomize_options: Mapped[bool] = mapped_column(Boolean, default=True)
    show_immediate_feedback: Mapped[bool] = mapped_column(Boolean, default=True)

    # Adaptive mode
    adaptive_difficulty: Mapped[bool] = mapped_column(Boolean, default=False)

    # Pool configuration
    question_pool_ids: Mapped[list | None] = mapped_column(ARRAY(PG_UUID(as_uuid=True)))

    requires_prerequisites: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    concept_cluster: Mapped["CleanConceptCluster | None"] = relationship("CleanConceptCluster")
    concept: Mapped["CleanConcept | None"] = relationship("CleanConcept")
    passages: Mapped[list["QuizPassage"]] = relationship(
        back_populates="quiz_definition",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<QuizDefinition(name={self.name}, questions={self.question_count})>"

    def calculate_mastery(self, review_mastery: float, quiz_score: float) -> float:
        """
        Calculate combined mastery score.

        Formula: (review_mastery × review_weight) + (quiz_score × quiz_weight)

        Args:
            review_mastery: Mastery from spaced repetition (0-1)
            quiz_score: Best quiz score (0-1)

        Returns:
            Combined mastery score (0-1)
        """
        review_contribution = float(self.review_mastery_weight) * review_mastery
        quiz_contribution = float(self.quiz_mastery_weight) * quiz_score
        return review_contribution + quiz_contribution

    def get_passing_threshold_for_type(self, knowledge_type: str) -> float:
        """
        Get passing threshold adjusted for knowledge type.

        Args:
            knowledge_type: factual/conceptual/procedural/metacognitive

        Returns:
            Adjusted passing threshold
        """
        adjustments = {
            "factual": 0.70,
            "conceptual": 0.80,
            "procedural": 0.85,
            "metacognitive": 0.85,
        }
        return adjustments.get(knowledge_type, float(self.passing_threshold))


class QuizPassage(Base):
    """
    Passage for passage-based quiz questions.

    Stores text passages that can be referenced by multiple questions,
    enabling reading comprehension style assessments.

    Attributes:
        title: Optional passage title
        content: The passage text
        source_reference: Citation or source attribution
        word_count: Number of words for difficulty estimation
        readability_score: Flesch-Kincaid or similar score
    """

    __tablename__ = "quiz_passages"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid()
    )
    quiz_definition_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("quiz_definitions.id", ondelete="CASCADE")
    )

    title: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_reference: Mapped[str | None] = mapped_column(Text)
    word_count: Mapped[int | None] = mapped_column(Integer)
    readability_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))

    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    quiz_definition: Mapped["QuizDefinition | None"] = relationship(
        back_populates="passages"
    )

    def __repr__(self) -> str:
        title = self.title or "Untitled"
        return f"<QuizPassage(title={title}, words={self.word_count})>"

    def calculate_word_count(self) -> int:
        """Calculate and store word count from content."""
        if self.content:
            self.word_count = len(self.content.split())
        else:
            self.word_count = 0
        return self.word_count
