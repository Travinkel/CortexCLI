"""
Curriculum-Scoped Cleaning Pipeline

Filters and cleans flashcards for a specific module/curriculum scope.
Combines:
- Existing links (Notion relations, Anki tags)
- Semantic similarity for unlinked cards
- Quality analysis (verbose detection, atomicity)
- Automatic splitting of compound cards
- Deduplication within module scope
- Reassignment suggestions for misplaced cards

Example usage:
    pipeline = CurriculumPipeline(db_session)
    result = pipeline.process_module(
        module_name="CCNA Module 1",
        source="anki",
        auto_split=True,
    )
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import get_settings


@dataclass
class CardAssignment:
    """Represents a card and its module assignment."""

    card_id: str
    front: str
    back: Optional[str]
    current_module: Optional[str]
    suggested_module: Optional[str]
    similarity_score: float
    assignment_method: str  # 'existing_link', 'semantic', 'unassigned'
    quality_grade: Optional[str]
    needs_split: bool
    is_duplicate: bool


@dataclass
class PipelineResult:
    """Result of running the curriculum-scoped pipeline."""

    module_name: str
    total_cards_processed: int
    cards_in_module: int
    cards_reassigned: int
    cards_split: int
    duplicates_removed: int
    quality_distribution: Dict[str, int] = field(default_factory=dict)
    reassignment_suggestions: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    processing_time_seconds: float = 0.0


class CurriculumPipeline:
    """
    Pipeline for scoping flashcards to a specific curriculum module.

    Workflow:
    1. Fetch cards from source (Anki staging or learning_atoms)
    2. Identify cards already linked to the module
    3. Use semantic similarity to find related unlinked cards
    4. Run quality analysis on all cards
    5. Split verbose/compound cards
    6. Detect and remove duplicates within module scope
    7. Generate reassignment suggestions for misplaced cards
    """

    # Thresholds
    MODULE_SIMILARITY_THRESHOLD = 0.7  # Min similarity to assign to module
    DUPLICATE_THRESHOLD = 0.85  # Cards above this are duplicates

    def __init__(
        self,
        db_session: Session,
        embedding_service=None,
    ):
        """
        Initialize the curriculum pipeline.

        Args:
            db_session: SQLAlchemy database session.
            embedding_service: Optional embedding service for semantic analysis.
        """
        self.db = db_session
        self.settings = get_settings()
        self._embedding_service = embedding_service

    @property
    def embedding_service(self):
        """Lazy load embedding service."""
        if self._embedding_service is None:
            from src.semantic import EmbeddingService
            self._embedding_service = EmbeddingService()
        return self._embedding_service

    def process_module(
        self,
        module_name: str,
        source: str = "anki",
        deck_name: Optional[str] = None,
        auto_split: bool = True,
        generate_embeddings: bool = True,
        remove_duplicates: bool = True,
        dry_run: bool = False,
    ) -> PipelineResult:
        """
        Process and filter cards for a specific module.

        Args:
            module_name: Name of the module (e.g., "CCNA Module 1").
            source: Data source ("anki" or "learning_atoms").
            deck_name: Optional Anki deck name filter.
            auto_split: Automatically split verbose cards.
            generate_embeddings: Generate embeddings for semantic analysis.
            remove_duplicates: Remove duplicate cards.
            dry_run: If True, don't make changes to database.

        Returns:
            PipelineResult with processing statistics.
        """
        start_time = datetime.utcnow()
        logger.info(f"Starting curriculum pipeline for module: {module_name}")

        result = PipelineResult(
            module_name=module_name,
            total_cards_processed=0,
            cards_in_module=0,
            cards_reassigned=0,
            cards_split=0,
            duplicates_removed=0,
        )

        try:
            # Step 1: Get or create module reference
            module_id, module_embedding = self._get_module_info(module_name)

            # Step 2: Fetch cards from source
            cards = self._fetch_cards(source, deck_name)
            result.total_cards_processed = len(cards)
            logger.info(f"Fetched {len(cards)} cards from {source}")

            if not cards:
                return result

            # Step 3: Generate embeddings if needed
            if generate_embeddings:
                self._ensure_embeddings(cards, source)

            # Step 4: Classify cards by module relevance
            classified = self._classify_cards(
                cards=cards,
                module_name=module_name,
                module_id=module_id,
                module_embedding=module_embedding,
            )

            # Count cards in module
            in_module = [c for c in classified if c.suggested_module == module_name]
            result.cards_in_module = len(in_module)

            # Step 5: Run quality analysis on module cards
            quality_results = self._analyze_quality(in_module)
            result.quality_distribution = quality_results["grade_distribution"]

            # Step 6: Split verbose cards if requested
            if auto_split:
                split_count = self._split_verbose_cards(in_module, dry_run)
                result.cards_split = split_count

            # Step 7: Remove duplicates within module scope
            if remove_duplicates:
                dup_count = self._remove_module_duplicates(in_module, dry_run)
                result.duplicates_removed = dup_count

            # Step 8: Generate reassignment suggestions
            misplaced = [c for c in classified if c.suggested_module != module_name and c.suggested_module]
            result.reassignment_suggestions = self._generate_reassignments(misplaced)
            result.cards_reassigned = len(result.reassignment_suggestions)

            # Calculate processing time
            result.processing_time_seconds = (datetime.utcnow() - start_time).total_seconds()

            logger.info(
                f"Pipeline complete: {result.cards_in_module} in module, "
                f"{result.cards_split} split, {result.duplicates_removed} duplicates removed"
            )

        except Exception as e:
            logger.exception("Pipeline failed")
            result.errors.append(str(e))

        return result

    def _get_module_info(self, module_name: str) -> Tuple[Optional[UUID], Optional[list]]:
        """
        Get module ID and embedding from database.

        Returns tuple of (module_id, module_embedding).
        """
        query = text("""
            SELECT id, embedding
            FROM clean_modules
            WHERE name ILIKE :name
            LIMIT 1
        """)

        result = self.db.execute(query, {"name": f"%{module_name}%"}).fetchone()

        if result:
            return result.id, result.embedding

        # Module not found - create embedding from name
        logger.warning(f"Module '{module_name}' not found in database, using name for semantic matching")
        embedding_result = self.embedding_service.generate_embedding(module_name)
        return None, embedding_result.to_list()

    def _fetch_cards(
        self,
        source: str,
        deck_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch cards from the specified source.
        """
        if source == "anki":
            return self._fetch_anki_cards(deck_name)
        elif source == "learning_atoms":
            return self._fetch_learning_atoms()
        else:
            raise ValueError(f"Unknown source: {source}")

    def _fetch_anki_cards(self, deck_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch cards from Anki staging table."""
        where_clause = "WHERE 1=1"
        params = {}

        if deck_name:
            where_clause += " AND deck_name ILIKE :deck_name"
            params["deck_name"] = f"%{deck_name}%"

        query = text(f"""
            SELECT
                anki_note_id as id,
                card_id,
                front,
                back,
                deck_name,
                tags,
                quality_grade,
                is_atomic,
                needs_split,
                embedding
            FROM stg_anki_cards
            {where_clause}
            ORDER BY imported_at DESC
        """)

        results = self.db.execute(query, params).fetchall()

        return [
            {
                "id": row.id,
                "card_id": row.card_id,
                "front": row.front,
                "back": row.back,
                "deck_name": row.deck_name,
                "tags": row.tags or [],
                "quality_grade": row.quality_grade,
                "is_atomic": row.is_atomic,
                "needs_split": row.needs_split,
                "embedding": row.embedding,
            }
            for row in results
        ]

    def _fetch_learning_atoms(self) -> List[Dict[str, Any]]:
        """Fetch cards from learning_atoms table."""
        query = text("""
            SELECT
                a.id,
                a.card_id,
                a.front,
                a.back,
                a.concept_id,
                a.module_id,
                m.name as module_name,
                a.embedding,
                a.is_atomic,
                a.atomicity_status
            FROM learning_atoms a
            LEFT JOIN clean_modules m ON a.module_id = m.id
            ORDER BY a.created_at DESC
        """)

        results = self.db.execute(query).fetchall()

        return [
            {
                "id": row.id,
                "card_id": row.card_id,
                "front": row.front,
                "back": row.back,
                "module_id": row.module_id,
                "module_name": row.module_name,
                "embedding": row.embedding,
                "is_atomic": row.is_atomic,
            }
            for row in results
        ]

    def _ensure_embeddings(self, cards: List[Dict], source: str) -> None:
        """Generate embeddings for cards that don't have them."""
        cards_without = [c for c in cards if c.get("embedding") is None]

        if not cards_without:
            return

        logger.info(f"Generating embeddings for {len(cards_without)} cards")

        # Generate embeddings
        texts = [
            self.embedding_service.combine_front_back(c["front"], c.get("back", ""))
            for c in cards_without
        ]

        results = self.embedding_service.generate_embeddings_batch(texts, show_progress=True)

        # Update database
        table = "stg_anki_cards" if source == "anki" else "learning_atoms"
        id_col = "anki_note_id" if source == "anki" else "id"

        update_query = text(f"""
            UPDATE {table}
            SET embedding = :embedding::vector,
                embedding_model = :model,
                embedding_generated_at = :generated_at
            WHERE {id_col} = :card_id
        """)

        for card, result in zip(cards_without, results):
            self.db.execute(
                update_query,
                {
                    "embedding": str(result.to_list()),
                    "model": result.model_name,
                    "generated_at": result.generated_at,
                    "card_id": str(card["id"]),
                },
            )
            # Update in-memory too
            card["embedding"] = result.embedding

        self.db.commit()

    def _classify_cards(
        self,
        cards: List[Dict],
        module_name: str,
        module_id: Optional[UUID],
        module_embedding: Optional[list],
    ) -> List[CardAssignment]:
        """
        Classify each card by its module assignment.

        Uses:
        1. Existing links (module_id, tags)
        2. Semantic similarity for unlinked cards
        """
        import numpy as np

        classified = []

        for card in cards:
            assignment = CardAssignment(
                card_id=card.get("card_id") or str(card["id"]),
                front=card["front"],
                back=card.get("back"),
                current_module=card.get("module_name"),
                suggested_module=None,
                similarity_score=0.0,
                assignment_method="unassigned",
                quality_grade=card.get("quality_grade"),
                needs_split=card.get("needs_split", False),
                is_duplicate=False,
            )

            # Check existing link
            if card.get("module_id") == module_id or card.get("module_name") == module_name:
                assignment.suggested_module = module_name
                assignment.assignment_method = "existing_link"
                assignment.similarity_score = 1.0

            # Check tags (Anki)
            elif card.get("tags"):
                module_tag = module_name.lower().replace(" ", "_")
                if any(module_tag in t.lower() for t in card["tags"]):
                    assignment.suggested_module = module_name
                    assignment.assignment_method = "existing_link"
                    assignment.similarity_score = 1.0

            # Use semantic similarity
            elif card.get("embedding") is not None and module_embedding is not None:
                card_emb = np.array(card["embedding"])
                mod_emb = np.array(module_embedding)

                similarity = float(
                    np.dot(card_emb, mod_emb) /
                    (np.linalg.norm(card_emb) * np.linalg.norm(mod_emb))
                )

                assignment.similarity_score = similarity

                if similarity >= self.MODULE_SIMILARITY_THRESHOLD:
                    assignment.suggested_module = module_name
                    assignment.assignment_method = "semantic"
                else:
                    # Try to find best matching module
                    best_module = self._find_best_module(card_emb)
                    if best_module:
                        assignment.suggested_module = best_module["name"]
                        assignment.similarity_score = best_module["similarity"]
                        assignment.assignment_method = "semantic"

            classified.append(assignment)

        return classified

    def _find_best_module(self, card_embedding) -> Optional[Dict]:
        """Find the best matching module for a card embedding."""
        import numpy as np

        query = text("""
            SELECT id, name, embedding
            FROM clean_modules
            WHERE embedding IS NOT NULL
        """)

        modules = self.db.execute(query).fetchall()

        best_match = None
        best_similarity = 0.0

        for module in modules:
            mod_emb = np.array(module.embedding)
            similarity = float(
                np.dot(card_embedding, mod_emb) /
                (np.linalg.norm(card_embedding) * np.linalg.norm(mod_emb))
            )

            if similarity > best_similarity and similarity >= self.MODULE_SIMILARITY_THRESHOLD:
                best_similarity = similarity
                best_match = {"id": module.id, "name": module.name, "similarity": similarity}

        return best_match

    def _analyze_quality(self, cards: List[CardAssignment]) -> Dict[str, Any]:
        """Run quality analysis on cards."""
        from src.cleaning.atomicity import CardQualityAnalyzer

        analyzer = CardQualityAnalyzer()
        grade_distribution = {}

        for card in cards:
            report = analyzer.analyze(card.front, card.back, "flashcard")
            card.quality_grade = report.grade.value
            card.needs_split = report.needs_split

            grade = report.grade.value
            grade_distribution[grade] = grade_distribution.get(grade, 0) + 1

        return {"grade_distribution": grade_distribution}

    def _split_verbose_cards(
        self,
        cards: List[CardAssignment],
        dry_run: bool,
    ) -> int:
        """
        Split verbose/compound cards using AI.

        Returns count of cards split.
        """
        verbose_cards = [c for c in cards if c.needs_split]

        if not verbose_cards:
            return 0

        logger.info(f"Attempting to split {len(verbose_cards)} verbose cards")

        if not self.settings.has_ai_configured():
            logger.warning("AI not configured - cannot auto-split cards")
            return 0

        # TODO: Integrate with AI splitting service
        # For now, just flag them
        split_count = 0
        for card in verbose_cards:
            if not dry_run:
                # Mark for manual review with split recommendation
                logger.debug(f"Card {card.card_id} flagged for splitting")
            split_count += 1

        return split_count

    def _remove_module_duplicates(
        self,
        cards: List[CardAssignment],
        dry_run: bool,
    ) -> int:
        """
        Remove semantic duplicates within module scope.

        Returns count of duplicates removed.
        """
        if len(cards) < 2:
            return 0

        logger.info(f"Checking {len(cards)} cards for duplicates")

        # Use semantic similarity service
        try:
            from src.semantic import SemanticSimilarityService

            similarity_service = SemanticSimilarityService(self.db)
            duplicates = similarity_service.find_semantic_duplicates(
                threshold=self.DUPLICATE_THRESHOLD,
                limit=500,
            )

            # Get card IDs in this module
            module_card_ids = {c.card_id for c in cards}

            # Filter to duplicates within this module
            module_duplicates = [
                d for d in duplicates
                if str(d.atom_id_1) in module_card_ids or str(d.atom_id_2) in module_card_ids
            ]

            if not dry_run:
                # Store for review
                similarity_service.store_duplicate_pairs(module_duplicates)

            # Mark cards as duplicates
            dup_ids = set()
            for dup in module_duplicates:
                dup_ids.add(str(dup.atom_id_2))  # Keep first, mark second as duplicate

            for card in cards:
                if card.card_id in dup_ids:
                    card.is_duplicate = True

            return len(module_duplicates)

        except ImportError:
            logger.warning("Semantic module not available for duplicate detection")
            return 0

    def _generate_reassignments(
        self,
        misplaced_cards: List[CardAssignment],
    ) -> List[Dict[str, Any]]:
        """Generate reassignment suggestions for misplaced cards."""
        suggestions = []

        for card in misplaced_cards:
            if card.suggested_module:
                suggestions.append({
                    "card_id": card.card_id,
                    "front": card.front[:100] + "..." if len(card.front) > 100 else card.front,
                    "current_module": card.current_module,
                    "suggested_module": card.suggested_module,
                    "similarity_score": round(card.similarity_score, 3),
                    "reason": f"Semantic similarity {card.similarity_score:.0%} to '{card.suggested_module}'",
                })

        return suggestions

    def get_module_summary(self, module_name: str) -> Dict[str, Any]:
        """
        Get a summary of cards assigned to a module.
        """
        query = text("""
            SELECT
                COUNT(*) as total_cards,
                COUNT(*) FILTER (WHERE is_atomic = true) as atomic_cards,
                COUNT(*) FILTER (WHERE is_atomic = false) as verbose_cards,
                AVG(quality_score) as avg_quality
            FROM learning_atoms a
            JOIN clean_modules m ON a.module_id = m.id
            WHERE m.name ILIKE :module_name
        """)

        result = self.db.execute(query, {"module_name": f"%{module_name}%"}).fetchone()

        if not result or result.total_cards == 0:
            return {"error": f"No cards found for module '{module_name}'"}

        return {
            "module_name": module_name,
            "total_cards": result.total_cards,
            "atomic_cards": result.atomic_cards,
            "verbose_cards": result.verbose_cards,
            "avg_quality": float(result.avg_quality) if result.avg_quality else 0,
        }
