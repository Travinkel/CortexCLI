"""
Batch Quality Analyzer

Analyzes multiple learning atoms (cards) for quality issues in batch mode.
Supports different sources (Anki import, Notion sync, manual input).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.cleaning.atomicity import CardQualityAnalyzer, QualityReport
from src.db.database import get_db


class BatchQualityAnalyzer:
    """
    Batch processor for quality analysis of learning atoms.

    Supports analyzing cards from multiple sources:
    - Anki import (stg_anki_cards)
    - Notion sync (notion_flashcards)
    - Manual input (API payloads)
    """

    def __init__(self, analyzer_version: str = "1.0.0"):
        """
        Initialize batch analyzer.

        Args:
            analyzer_version: Version string for tracking.
        """
        self.analyzer = CardQualityAnalyzer(version=analyzer_version)
        self.analyzer_version = analyzer_version

    def analyze_anki_cards(
        self,
        db: Session,
        limit: Optional[int] = None,
        min_grade: Optional[str] = None,
        deck_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze all cards imported from Anki.

        Args:
            db: Database session.
            limit: Maximum number of cards to analyze (None = all).
            min_grade: Only analyze cards with this grade or worse (e.g., "D" = D and F only).
            deck_name: Optional deck name filter.

        Returns:
            Summary dict with:
            - total_analyzed: int
            - grade_distribution: Dict[str, int]
            - issue_counts: Dict[str, int]
            - cards_needing_split: int
            - cards_needing_rewrite: int
        """
        logger.info(
            "Starting batch analysis for Anki cards: limit={}, min_grade={}, deck={}",
            limit,
            min_grade,
            deck_name,
        )

        # Build query
        where_clauses = []
        params = {}

        if deck_name:
            where_clauses.append("deck_name = :deck_name")
            params["deck_name"] = deck_name

        if min_grade:
            # Grade filter: if min_grade='D', include D and F
            grade_order = {"A": 1, "B": 2, "C": 3, "D": 4, "F": 5}
            if min_grade in grade_order:
                min_order = grade_order[min_grade]
                allowed_grades = [g for g, o in grade_order.items() if o >= min_order]
                where_clauses.append(f"quality_grade IN ({','.join(':grade_' + str(i) for i in range(len(allowed_grades)))})")
                for i, g in enumerate(allowed_grades):
                    params[f"grade_{i}"] = g

        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        limit_sql = f"LIMIT {limit}" if limit else ""

        query = text(f"""
            SELECT
                anki_note_id,
                card_id,
                front,
                back,
                deck_name,
                quality_grade
            FROM stg_anki_cards
            {where_sql}
            ORDER BY imported_at DESC
            {limit_sql}
        """)

        results = db.execute(query, params).fetchall()

        if not results:
            logger.warning("No cards found matching criteria")
            return {
                "total_analyzed": 0,
                "grade_distribution": {},
                "issue_counts": {},
                "cards_needing_split": 0,
                "cards_needing_rewrite": 0,
            }

        # Analyze each card
        total_analyzed = 0
        grade_distribution: Dict[str, int] = {}
        issue_counts: Dict[str, int] = {}
        cards_needing_split = 0
        cards_needing_rewrite = 0

        for row in results:
            # Run quality analysis
            report = self.analyzer.analyze(
                front_content=row.front,
                back_content=row.back,
                atom_type="flashcard",
            )

            # Update counts
            total_analyzed += 1
            grade = report.grade.value
            grade_distribution[grade] = grade_distribution.get(grade, 0) + 1

            for issue in report.issues:
                issue_name = issue.value
                issue_counts[issue_name] = issue_counts.get(issue_name, 0) + 1

            if report.needs_split:
                cards_needing_split += 1
            if report.needs_rewrite:
                cards_needing_rewrite += 1

            # Update database with analysis results
            update_query = text("""
                UPDATE stg_anki_cards
                SET
                    quality_grade = :grade,
                    quality_score = :score,
                    is_atomic = :is_atomic,
                    is_verbose = :is_verbose,
                    needs_split = :needs_split,
                    needs_rewrite = :needs_rewrite,
                    front_word_count = :front_words,
                    back_word_count = :back_words,
                    front_char_count = :front_chars,
                    back_char_count = :back_chars,
                    quality_issues = :issues,
                    quality_recommendations = :recommendations,
                    analyzer_version = :version
                WHERE anki_note_id = :note_id
            """)

            db.execute(
                update_query,
                {
                    "grade": report.grade.value,
                    "score": report.score,
                    "is_atomic": report.is_atomic,
                    "is_verbose": report.is_verbose,
                    "needs_split": report.needs_split,
                    "needs_rewrite": report.needs_rewrite,
                    "front_words": report.front_word_count,
                    "back_words": report.back_word_count,
                    "front_chars": report.front_char_count,
                    "back_chars": report.back_char_count,
                    "issues": [issue.value for issue in report.issues],
                    "recommendations": report.recommendations,
                    "version": self.analyzer_version,
                    "note_id": row.anki_note_id,
                },
            )

        db.commit()

        logger.info(
            "Batch analysis complete: analyzed={}, A={}, B={}, C={}, D={}, F={}, needs_split={}",
            total_analyzed,
            grade_distribution.get("A", 0),
            grade_distribution.get("B", 0),
            grade_distribution.get("C", 0),
            grade_distribution.get("D", 0),
            grade_distribution.get("F", 0),
            cards_needing_split,
        )

        return {
            "total_analyzed": total_analyzed,
            "grade_distribution": grade_distribution,
            "issue_counts": issue_counts,
            "cards_needing_split": cards_needing_split,
            "cards_needing_rewrite": cards_needing_rewrite,
        }

    def analyze_single_card(
        self, front: str, back: Optional[str] = None, atom_type: str = "flashcard"
    ) -> QualityReport:
        """
        Analyze a single card (convenience method for API endpoints).

        Args:
            front: Question/prompt content.
            back: Answer/solution content.
            atom_type: Type of learning atom.

        Returns:
            QualityReport with full analysis.
        """
        return self.analyzer.analyze(front, back, atom_type)

    def get_quality_summary(self, db: Session, source: str = "anki") -> Dict[str, Any]:
        """
        Get quality summary statistics for cards from a specific source.

        Args:
            db: Database session.
            source: Source type ("anki", "notion", "manual").

        Returns:
            Summary statistics including grade distribution and issue counts.
        """
        if source == "anki":
            query = text("""
                SELECT
                    COUNT(*) as total_cards,
                    COUNT(*) FILTER (WHERE quality_grade = 'A') as grade_a,
                    COUNT(*) FILTER (WHERE quality_grade = 'B') as grade_b,
                    COUNT(*) FILTER (WHERE quality_grade = 'C') as grade_c,
                    COUNT(*) FILTER (WHERE quality_grade = 'D') as grade_d,
                    COUNT(*) FILTER (WHERE quality_grade = 'F') as grade_f,
                    COUNT(*) FILTER (WHERE is_atomic = false) as non_atomic,
                    COUNT(*) FILTER (WHERE needs_split = true) as needs_split,
                    COUNT(*) FILTER (WHERE needs_rewrite = true) as needs_rewrite,
                    AVG(quality_score) as avg_score
                FROM stg_anki_cards
                WHERE quality_grade IS NOT NULL
            """)

            result = db.execute(query).fetchone()

            if not result or result.total_cards == 0:
                return {"error": "No analyzed cards found"}

            return {
                "total_cards": result.total_cards,
                "grade_distribution": {
                    "A": result.grade_a,
                    "B": result.grade_b,
                    "C": result.grade_c,
                    "D": result.grade_d,
                    "F": result.grade_f,
                },
                "non_atomic_count": result.non_atomic,
                "needs_split_count": result.needs_split,
                "needs_rewrite_count": result.needs_rewrite,
                "average_score": float(result.avg_score) if result.avg_score else 0.0,
            }

        else:
            return {"error": f"Unsupported source: {source}"}

    def analyze_with_semantic(
        self,
        db: Session,
        semantic_threshold: float = 0.85,
        generate_embeddings: bool = True,
        detect_duplicates: bool = True,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Run full analysis including semantic duplicate detection.

        Combines quality analysis with Phase 2.5 semantic features:
        1. Generate embeddings for cards without them
        2. Find semantic duplicates above threshold
        3. Store duplicate pairs for review

        Args:
            db: Database session.
            semantic_threshold: Cosine similarity threshold for duplicates.
            generate_embeddings: Generate embeddings for new cards.
            detect_duplicates: Run semantic duplicate detection.
            limit: Maximum cards to process.

        Returns:
            Combined summary with quality and semantic analysis results.
        """
        logger.info(
            "Starting combined quality + semantic analysis: threshold={}, generate={}, detect={}",
            semantic_threshold,
            generate_embeddings,
            detect_duplicates,
        )

        # Run standard quality analysis first
        quality_results = self.analyze_anki_cards(db, limit=limit)

        # Initialize semantic results
        semantic_results = {
            "embeddings_generated": 0,
            "semantic_duplicates_found": 0,
            "semantic_duplicates_stored": 0,
        }

        try:
            # Generate embeddings if requested
            if generate_embeddings:
                from src.semantic import BatchEmbeddingProcessor

                processor = BatchEmbeddingProcessor(db)
                embedding_result = processor.generate_embeddings(
                    source="stg_anki_cards",
                    regenerate=False,  # Only generate for new cards
                )
                semantic_results["embeddings_generated"] = embedding_result.get("records_processed", 0)

            # Detect semantic duplicates if requested
            if detect_duplicates:
                from src.semantic import SemanticSimilarityService

                similarity_service = SemanticSimilarityService(db)
                duplicates = similarity_service.find_semantic_duplicates(
                    threshold=semantic_threshold,
                    limit=500,  # Cap at 500 pairs
                )
                semantic_results["semantic_duplicates_found"] = len(duplicates)

                # Store for review
                if duplicates:
                    stored = similarity_service.store_duplicate_pairs(duplicates)
                    semantic_results["semantic_duplicates_stored"] = stored

        except ImportError as e:
            logger.warning(f"Semantic module not available: {e}")
            semantic_results["error"] = "Semantic module not available"
        except Exception as e:
            logger.exception("Semantic analysis failed")
            semantic_results["error"] = str(e)

        # Combine results
        return {
            **quality_results,
            "semantic": semantic_results,
        }

    def get_combined_summary(self, db: Session) -> Dict[str, Any]:
        """
        Get combined quality and semantic summary statistics.

        Returns quality metrics plus embedding coverage and duplicate counts.
        """
        # Get quality summary
        quality_summary = self.get_quality_summary(db, source="anki")

        # Add semantic summary
        semantic_summary = {}
        try:
            from src.semantic import BatchEmbeddingProcessor, SemanticSimilarityService

            # Embedding coverage
            processor = BatchEmbeddingProcessor(db)
            coverage = processor.get_embedding_coverage()
            semantic_summary["embedding_coverage"] = coverage

            # Duplicate stats
            similarity_service = SemanticSimilarityService(db)
            duplicate_stats = similarity_service.get_duplicate_stats()
            semantic_summary["duplicate_stats"] = duplicate_stats

        except ImportError:
            semantic_summary["error"] = "Semantic module not available"
        except Exception as e:
            semantic_summary["error"] = str(e)

        return {
            "quality": quality_summary,
            "semantic": semantic_summary,
        }
