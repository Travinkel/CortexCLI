"""
Atom Type Suitability Scorer.

Scores how suitable content is for each atom type using:
- Primary signal (60%): Knowledge type alignment
- Secondary signal (30%): Content structure analysis
- Tertiary signal (10%): Length appropriateness

Formula:
    suitability = (knowledge_weight × 0.6) + (structure_weight × 0.3) + (length_weight × 0.1)
"""

from __future__ import annotations

import re
from uuid import UUID

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.adaptive.models import (
    KNOWLEDGE_TYPE_AFFINITY,
    AtomSuitability,
    ContentFeatures,
    SuitabilityScore,
)
from src.db.database import session_scope

# Optimal word count ranges by atom type
OPTIMAL_LENGTH = {
    "flashcard": {"min": 5, "max": 25, "answer_max": 15},
    "cloze": {"min": 10, "max": 40, "blanks_max": 3},
    "mcq": {"min": 15, "max": 50, "options": 4},
    "true_false": {"min": 8, "max": 30},
    "matching": {"min": 10, "max": 30, "pairs_max": 6},
    "parsons": {"min": 15, "max": 60, "steps_max": 8},
    "compare": {"min": 20, "max": 60},
    "ranking": {"min": 10, "max": 40, "items_max": 8},
    "sequence": {"min": 15, "max": 50, "steps_max": 6},
}


class SuitabilityScorer:
    """
    Score atom type suitability based on knowledge type, content structure, and length.

    Uses a three-signal approach:
    - Knowledge type affinity (60%): How well the knowledge type fits the atom type
    - Content structure (30%): Whether content has features suited for the type
    - Length appropriateness (10%): Whether content length is optimal for the type
    """

    def __init__(self, session: Session | None = None):
        self._session = session

    def score_atom(
        self,
        atom_id: UUID,
        front: str | None = None,
        back: str | None = None,
        knowledge_type: str | None = None,
        current_type: str | None = None,
    ) -> AtomSuitability:
        """
        Compute suitability scores for an atom.

        Args:
            atom_id: Atom UUID
            front: Front content (optional, will fetch if not provided)
            back: Back content (optional)
            knowledge_type: Knowledge type (factual, conceptual, procedural)
            current_type: Current atom type

        Returns:
            AtomSuitability with scores for all types
        """
        # Fetch atom data if not provided
        if front is None:
            atom_data = self._fetch_atom_data(atom_id)
            if not atom_data:
                logger.warning(f"Atom not found: {atom_id}")
                return AtomSuitability(
                    atom_id=atom_id,
                    current_type="unknown",
                    recommended_type="flashcard",
                    recommendation_confidence=0.0,
                    type_mismatch=False,
                )
            front = atom_data.get("front", "")
            back = atom_data.get("back", "")
            knowledge_type = atom_data.get("knowledge_type", "factual")
            current_type = atom_data.get("atom_type", "flashcard")

        # Normalize knowledge type
        knowledge_type = self._normalize_knowledge_type(knowledge_type)
        current_type = (current_type or "flashcard").lower()

        # Extract content features
        content_features = self.extract_features(front, back)

        # Compute scores for each atom type
        scores = {}
        for atom_type in KNOWLEDGE_TYPE_AFFINITY.get(knowledge_type, {}).keys():
            score = self._compute_type_score(
                atom_type, knowledge_type, content_features, front, back
            )
            scores[atom_type] = score

        # Find recommended type (highest score)
        if scores:
            recommended_type = max(scores.keys(), key=lambda t: scores[t].score)
            recommendation_confidence = scores[recommended_type].score
        else:
            recommended_type = "flashcard"
            recommendation_confidence = 0.5

        # Check for mismatch
        type_mismatch = (
            current_type != recommended_type
            and recommendation_confidence > 0.7
            and scores.get(current_type, SuitabilityScore(current_type, 0, 0, 0, 0)).score < 0.5
        )

        return AtomSuitability(
            atom_id=atom_id,
            current_type=current_type,
            recommended_type=recommended_type,
            recommendation_confidence=recommendation_confidence,
            type_mismatch=type_mismatch,
            scores=scores,
            content_features=content_features,
        )

    def _compute_type_score(
        self,
        atom_type: str,
        knowledge_type: str,
        features: ContentFeatures,
        front: str,
        back: str | None,
    ) -> SuitabilityScore:
        """Compute suitability score for a specific atom type."""
        # Primary signal: Knowledge type affinity (60%)
        knowledge_signal = KNOWLEDGE_TYPE_AFFINITY.get(knowledge_type, {}).get(atom_type, 0.5)

        # Secondary signal: Content structure alignment (30%)
        structure_signal = self._compute_structure_alignment(features, atom_type)

        # Tertiary signal: Length appropriateness (10%)
        length_signal = self._compute_length_score(features, atom_type)

        # Combined score
        combined = knowledge_signal * 0.6 + structure_signal * 0.3 + length_signal * 0.1

        # Generate reasoning
        reasoning = self._generate_reasoning(
            atom_type, knowledge_signal, structure_signal, length_signal, features
        )

        return SuitabilityScore(
            atom_type=atom_type,
            score=combined,
            knowledge_signal=knowledge_signal,
            structure_signal=structure_signal,
            length_signal=length_signal,
            confidence=combined,  # Use score as confidence
            reasoning=reasoning,
        )

    def _compute_structure_alignment(
        self,
        features: ContentFeatures,
        atom_type: str,
    ) -> float:
        """
        Score how well content structure aligns with atom type.

        Different atom types have different structural requirements.
        """
        score = 0.5  # Base score

        if atom_type == "matching":
            # Needs pairs/lists/definitions
            if features.has_definition_list:
                score += 0.4
            if features.list_item_count >= 3:
                score += 0.1
            if features.list_item_count > 6:
                score -= 0.1  # Too many pairs

        elif atom_type == "parsons":
            # Needs CLI commands or numbered steps
            if features.has_cli_commands:
                score += 0.4
            if features.has_numbered_steps:
                score += 0.1
            if features.cli_command_count > 8:
                score -= 0.1  # Too many steps

        elif atom_type == "cloze":
            # Needs key terms/bold terms
            if features.has_bold_terms:
                score += 0.3
            if features.technical_term_count > 0:
                score += 0.2
            if features.sentence_count > 3:
                score -= 0.1  # Too long for cloze

        elif atom_type == "compare":
            # Needs comparison structure
            if features.has_comparison_table:
                score += 0.4
            if features.comparison_keyword_count > 0:
                score += 0.1 * min(features.comparison_keyword_count, 3)

        elif atom_type == "mcq":
            # Needs concepts with alternatives
            if features.concept_count >= 2:
                score += 0.3
            if features.has_alternatives:
                score += 0.2

        elif atom_type == "true_false":
            # Works well with single statements
            if features.sentence_count == 1:
                score += 0.3
            if features.is_factual:
                score += 0.2

        elif atom_type == "ranking" or atom_type == "sequence":
            # Needs ordered items
            if features.has_numbered_steps:
                score += 0.4
            if features.list_item_count >= 3:
                score += 0.1

        elif atom_type == "flashcard":
            # Works with most content, slight boost for simple factual
            if features.is_factual:
                score += 0.2
            if features.sentence_count <= 2:
                score += 0.1

        return min(1.0, max(0.0, score))

    def _compute_length_score(
        self,
        features: ContentFeatures,
        atom_type: str,
    ) -> float:
        """Score length appropriateness for atom type."""
        optimal = OPTIMAL_LENGTH.get(atom_type, {"min": 5, "max": 50})
        word_count = features.word_count

        if word_count < optimal["min"]:
            # Too short
            return max(0.3, word_count / optimal["min"])
        elif word_count > optimal["max"]:
            # Too long
            return max(0.3, optimal["max"] / word_count)
        else:
            # In optimal range
            return 1.0

    def extract_features(
        self,
        front: str,
        back: str | None = None,
    ) -> ContentFeatures:
        """
        Extract structural features from content.

        Analyzes content to identify:
        - CLI commands
        - Lists and definitions
        - Bold/technical terms
        - Comparison structures
        - Code blocks
        """
        content = f"{front}\n{back or ''}"

        # Basic counts
        words = content.split()
        sentences = re.split(r"[.!?]+", content)

        # CLI commands (Cisco IOS style)
        cli_patterns = [
            r"^\s*\w+#\s*\w+",  # Router# command
            r"^\s*\w+>\s*\w+",  # Router> command
            r"^\s*\(config\)",  # Config mode
            r"^\s*interface\s+",
            r"^\s*ip\s+address\s+",
            r"^\s*show\s+\w+",
            r"^\s*enable\s*$",
            r"^\s*configure\s+terminal",
        ]
        cli_count = sum(
            len(re.findall(pattern, content, re.MULTILINE | re.IGNORECASE))
            for pattern in cli_patterns
        )

        # Numbered steps
        step_pattern = r"^\s*\d+[\.\)]\s+"
        numbered_steps = len(re.findall(step_pattern, content, re.MULTILINE))

        # List items (bullets)
        list_pattern = r"^\s*[-*•]\s+"
        list_items = len(re.findall(list_pattern, content, re.MULTILINE))
        list_items += numbered_steps

        # Bold terms (markdown)
        bold_pattern = r"\*\*([^*]+)\*\*"
        bold_terms = re.findall(bold_pattern, content)

        # Technical terms (acronyms, capitalized terms)
        tech_pattern = r"\b[A-Z]{2,}\b"
        tech_terms = re.findall(tech_pattern, content)

        # Comparison keywords
        comparison_keywords = [
            "vs",
            "versus",
            "compared to",
            "unlike",
            "whereas",
            "in contrast",
            "similar to",
            "different from",
        ]
        comp_count = sum(1 for kw in comparison_keywords if kw.lower() in content.lower())

        # Definition pattern (term: definition or term - definition)
        def_pattern = r"^\s*\w+[\w\s]*[:\-]\s+\w+"
        has_definitions = bool(re.search(def_pattern, content, re.MULTILINE))

        # Code blocks
        code_pattern = r"```[\s\S]*?```"
        code_blocks = re.findall(code_pattern, content)
        code_lines = sum(block.count("\n") for block in code_blocks)

        # Table detection
        table_pattern = r"\|[^|]+\|"
        has_table = bool(re.search(table_pattern, content))

        # Determine content type hints
        is_factual = (
            len(tech_terms) > 0 or bool(re.search(r"\bis\b|\bare\b|\bhas\b|\bhave\b", content))
        ) and cli_count == 0

        is_procedural = (
            cli_count > 0
            or numbered_steps >= 2
            or bool(re.search(r"\bstep\b|\bfirst\b|\bthen\b|\bnext\b", content.lower()))
        )

        is_conceptual = comp_count > 0 or bool(
            re.search(r"\bwhy\b|\bhow\b|\brelationship\b|\bdifference\b", content.lower())
        )

        return ContentFeatures(
            word_count=len(words),
            sentence_count=len([s for s in sentences if s.strip()]),
            char_count=len(content),
            has_cli_commands=cli_count > 0,
            cli_command_count=cli_count,
            has_definition_list=has_definitions,
            list_item_count=list_items,
            has_numbered_steps=numbered_steps > 0,
            step_count=numbered_steps,
            has_bold_terms=len(bold_terms) > 0,
            technical_term_count=len(tech_terms),
            has_comparison_table=has_table and comp_count > 0,
            comparison_keyword_count=comp_count,
            has_code_block=len(code_blocks) > 0,
            code_line_count=code_lines,
            concept_count=len(tech_terms),  # Approximate
            has_alternatives=comp_count > 0,
            is_factual=is_factual,
            is_procedural=is_procedural,
            is_conceptual=is_conceptual,
        )

    def _generate_reasoning(
        self,
        atom_type: str,
        knowledge_signal: float,
        structure_signal: float,
        length_signal: float,
        features: ContentFeatures,
    ) -> str:
        """Generate human-readable reasoning for the score."""
        reasons = []

        # Knowledge type
        if knowledge_signal >= 0.8:
            reasons.append(f"Strong knowledge type fit ({knowledge_signal:.2f})")
        elif knowledge_signal >= 0.5:
            reasons.append(f"Moderate knowledge type fit ({knowledge_signal:.2f})")
        else:
            reasons.append(f"Weak knowledge type fit ({knowledge_signal:.2f})")

        # Structure
        if atom_type == "parsons" and features.has_cli_commands:
            reasons.append(f"Contains {features.cli_command_count} CLI commands")
        elif atom_type == "matching" and features.has_definition_list:
            reasons.append("Contains definition-style content")
        elif atom_type == "cloze" and features.has_bold_terms:
            reasons.append("Contains key terms suitable for blanks")
        elif atom_type == "compare" and features.comparison_keyword_count > 0:
            reasons.append(f"Contains {features.comparison_keyword_count} comparison keywords")

        # Length
        if length_signal < 0.7:
            optimal = OPTIMAL_LENGTH.get(atom_type, {})
            if features.word_count < optimal.get("min", 5):
                reasons.append(f"Content too short ({features.word_count} words)")
            elif features.word_count > optimal.get("max", 50):
                reasons.append(f"Content too long ({features.word_count} words)")

        return "; ".join(reasons) if reasons else "Standard scoring"

    def _normalize_knowledge_type(self, knowledge_type: str | None) -> str:
        """Normalize knowledge type to factual/conceptual/procedural."""
        if not knowledge_type:
            return "factual"

        kt = knowledge_type.lower()

        if kt in ["factual", "declarative", "recall"]:
            return "factual"
        elif kt in ["conceptual", "understanding", "comprehension"]:
            return "conceptual"
        elif kt in ["procedural", "application", "applicative", "procedural"]:
            return "procedural"

        return "factual"

    def _fetch_atom_data(self, atom_id: UUID) -> dict | None:
        """Fetch atom data from database."""
        with self._get_session() as session:
            query = text("""
                SELECT
                    front, back, atom_type, knowledge_type
                FROM learning_atoms
                WHERE id = :atom_id
            """)
            result = session.execute(query, {"atom_id": str(atom_id)})
            row = result.fetchone()
            if row:
                return {
                    "front": row.front,
                    "back": row.back,
                    "atom_type": row.atom_type,
                    "knowledge_type": row.knowledge_type,
                }
        return None

    def batch_score(
        self,
        atom_ids: list[UUID],
        save_to_db: bool = True,
    ) -> list[AtomSuitability]:
        """
        Score multiple atoms in batch.

        Args:
            atom_ids: List of atom UUIDs
            save_to_db: Whether to save results to database

        Returns:
            List of AtomSuitability objects
        """
        results = []

        for atom_id in atom_ids:
            try:
                suitability = self.score_atom(atom_id)
                results.append(suitability)

                if save_to_db:
                    self._save_suitability(suitability)
            except Exception as e:
                logger.error(f"Error scoring atom {atom_id}: {e}")

        return results

    def _save_suitability(self, suitability: AtomSuitability) -> None:
        """Save suitability scores to database."""
        with self._get_session() as session:
            query = text("""
                INSERT INTO atom_type_suitability (
                    atom_id, flashcard_score, cloze_score, mcq_score,
                    true_false_score, matching_score, parsons_score,
                    compare_score, ranking_score, sequence_score,
                    recommended_type, current_type, recommendation_confidence,
                    type_mismatch, knowledge_signal, structure_signal,
                    length_signal, content_features, computation_method
                ) VALUES (
                    :atom_id, :flashcard, :cloze, :mcq,
                    :true_false, :matching, :parsons,
                    :compare, :ranking, :sequence,
                    :recommended, :current, :confidence,
                    :mismatch, :knowledge, :structure,
                    :length, :features, 'rule_based'
                )
                ON CONFLICT (atom_id) DO UPDATE SET
                    flashcard_score = EXCLUDED.flashcard_score,
                    cloze_score = EXCLUDED.cloze_score,
                    mcq_score = EXCLUDED.mcq_score,
                    true_false_score = EXCLUDED.true_false_score,
                    matching_score = EXCLUDED.matching_score,
                    parsons_score = EXCLUDED.parsons_score,
                    compare_score = EXCLUDED.compare_score,
                    ranking_score = EXCLUDED.ranking_score,
                    sequence_score = EXCLUDED.sequence_score,
                    recommended_type = EXCLUDED.recommended_type,
                    recommendation_confidence = EXCLUDED.recommendation_confidence,
                    type_mismatch = EXCLUDED.type_mismatch,
                    knowledge_signal = EXCLUDED.knowledge_signal,
                    structure_signal = EXCLUDED.structure_signal,
                    length_signal = EXCLUDED.length_signal,
                    content_features = EXCLUDED.content_features,
                    computed_at = NOW()
            """)

            scores = suitability.scores
            features = suitability.content_features

            try:
                session.execute(
                    query,
                    {
                        "atom_id": str(suitability.atom_id),
                        "flashcard": scores.get(
                            "flashcard", SuitabilityScore("flashcard", 0, 0, 0, 0)
                        ).score,
                        "cloze": scores.get("cloze", SuitabilityScore("cloze", 0, 0, 0, 0)).score,
                        "mcq": scores.get("mcq", SuitabilityScore("mcq", 0, 0, 0, 0)).score,
                        "true_false": scores.get(
                            "true_false", SuitabilityScore("true_false", 0, 0, 0, 0)
                        ).score,
                        "matching": scores.get(
                            "matching", SuitabilityScore("matching", 0, 0, 0, 0)
                        ).score,
                        "parsons": scores.get(
                            "parsons", SuitabilityScore("parsons", 0, 0, 0, 0)
                        ).score,
                        "compare": scores.get(
                            "compare", SuitabilityScore("compare", 0, 0, 0, 0)
                        ).score,
                        "ranking": scores.get(
                            "ranking", SuitabilityScore("ranking", 0, 0, 0, 0)
                        ).score,
                        "sequence": scores.get(
                            "sequence", SuitabilityScore("sequence", 0, 0, 0, 0)
                        ).score,
                        "recommended": suitability.recommended_type,
                        "current": suitability.current_type,
                        "confidence": suitability.recommendation_confidence,
                        "mismatch": suitability.type_mismatch,
                        "knowledge": scores.get(
                            suitability.recommended_type, SuitabilityScore("", 0, 0, 0, 0)
                        ).knowledge_signal,
                        "structure": scores.get(
                            suitability.recommended_type, SuitabilityScore("", 0, 0, 0, 0)
                        ).structure_signal,
                        "length": scores.get(
                            suitability.recommended_type, SuitabilityScore("", 0, 0, 0, 0)
                        ).length_signal,
                        "features": features.to_dict() if features else {},
                    },
                )
                session.commit()
            except Exception as e:
                logger.error(f"Failed to save suitability: {e}")
                session.rollback()

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
