"""
CCNA Generation Pipeline.

End-to-end orchestration of CCNA content generation:
1. Parse module content
2. Load existing cards
3. Identify cards to preserve/replace
4. Generate new atoms for gaps
5. QA check all generated content
6. Migrate learning state
7. Save results to database

Usage:
    pipeline = CCNAGenerationPipeline()
    result = await pipeline.process_module(Path("docs/CCNA/CCNA Module 1.txt"))
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import get_settings
from src.ccna.anki_migration import (
    AnkiMigrationService,
    CardLearningState,
    MigrationReport,
)
from src.ccna.atomizer_service import (
    AtomizerService,
    AtomType,
    GeneratedAtom,
    KnowledgeType,
)
from src.ccna.content_parser import CCNAContentParser, ModuleContent, Section
from src.ccna.curriculum_linker import CurriculumLinker, CurriculumMapping
from src.ccna.qa_pipeline import QAPipeline, QAReport, QAResult
from src.db.database import get_session, session_scope
from src.db.models.canonical import CleanAtom, CleanConcept
from src.db.models.quiz import QuizQuestion


@dataclass
class GenerationJobResult:
    """Result of a generation job for a single module."""

    job_id: str
    module_id: str
    status: str  # 'completed', 'failed', 'partial'
    started_at: datetime
    completed_at: datetime | None = None

    # Content stats
    sections_total: int = 0
    sections_processed: int = 0

    # Generation results
    atoms_generated: int = 0
    atoms_passed_qa: int = 0
    atoms_flagged: int = 0
    atoms_rejected: int = 0

    # Type breakdown
    flashcards_generated: int = 0
    mcq_generated: int = 0
    cloze_generated: int = 0
    parsons_generated: int = 0

    # Quality metrics
    avg_quality_score: float = 0.0
    grade_distribution: dict[str, int] = field(default_factory=dict)

    # Migration stats
    cards_preserved: int = 0
    cards_replaced: int = 0
    migrations_successful: int = 0

    # Outputs
    atoms: list[GeneratedAtom] = field(default_factory=list)
    qa_results: list[QAResult] = field(default_factory=list)
    migration_report: MigrationReport | None = None

    # Errors
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "module_id": self.module_id,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "sections_total": self.sections_total,
            "sections_processed": self.sections_processed,
            "atoms_generated": self.atoms_generated,
            "atoms_passed_qa": self.atoms_passed_qa,
            "atoms_flagged": self.atoms_flagged,
            "atoms_rejected": self.atoms_rejected,
            "avg_quality_score": self.avg_quality_score,
            "grade_distribution": self.grade_distribution,
            "cards_preserved": self.cards_preserved,
            "cards_replaced": self.cards_replaced,
            "migrations_successful": self.migrations_successful,
            "error_count": len(self.errors),
        }


@dataclass
class FullGenerationReport:
    """Report from processing all modules."""

    total_modules: int
    modules_completed: int
    modules_failed: int
    total_atoms_generated: int
    total_atoms_approved: int
    overall_pass_rate: float
    module_results: list[GenerationJobResult]
    started_at: datetime
    completed_at: datetime | None = None


class CCNAGenerationPipeline:
    """
    End-to-end CCNA content generation pipeline.

    Orchestrates:
    - Content parsing
    - AI-powered atom generation
    - Quality assurance
    - Learning state migration
    - Database persistence
    """

    def __init__(self, db_session: Session | None = None):
        """
        Initialize the generation pipeline.

        Args:
            db_session: SQLAlchemy session (optional, will create if not provided)
        """
        settings = get_settings()

        self.parser = CCNAContentParser(settings.ccna_modules_path)
        self.atomizer = AtomizerService()
        self.qa_pipeline = QAPipeline(min_grade=settings.ccna_min_quality_grade)
        self.migration_service = AnkiMigrationService()
        self.curriculum_linker = CurriculumLinker()

        self._db_session = db_session
        self.regeneration_attempts = settings.ccna_regeneration_attempts
        self.batch_size = settings.ccna_generation_batch_size

        # Cached mappings (loaded on first use)
        self._curriculum_mapping: CurriculumMapping | None = None
        self._section_concept_map: dict[str, str] = {}  # section_id → concept_id

    @property
    def db(self) -> Session:
        """Get database session."""
        if self._db_session is None:
            self._db_session = next(get_session())
        return self._db_session

    async def process_module(
        self,
        module_path: Path | str,
        preserve_good_cards: bool = True,
        include_migration: bool = True,
        dry_run: bool = False,
    ) -> GenerationJobResult:
        """
        Process a single CCNA module.

        Args:
            module_path: Path to module TXT file
            preserve_good_cards: Keep Grade A/B cards instead of regenerating
            include_migration: Attempt to migrate learning state
            dry_run: Don't save to database

        Returns:
            GenerationJobResult with all stats and generated atoms
        """
        job_id = str(uuid4())
        started_at = datetime.utcnow()

        result = GenerationJobResult(
            job_id=job_id,
            module_id="",
            status="running",
            started_at=started_at,
            grade_distribution={"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
        )

        try:
            # 1. Parse module content
            logger.info(f"Parsing module: {module_path}")
            module = self.parser.parse_module(Path(module_path))
            result.module_id = module.module_id
            result.sections_total = module.section_count

            # 2. Load existing cards
            existing_cards: list[CardLearningState] = []
            if include_migration:
                logger.info(f"Loading existing cards for {module.module_id}")
                existing_cards = await self.migration_service.export_learning_states(
                    module_id=module.module_id
                )

            # 3. Identify cards to preserve/replace
            cards_to_preserve: list[CardLearningState] = []
            cards_to_replace: list[CardLearningState] = []

            if preserve_good_cards and existing_cards:
                quality_grades = await self._get_existing_quality_grades(module.module_id)
                cards_to_preserve = self.migration_service.get_preservation_candidates(
                    existing_cards, quality_grades
                )
                cards_to_replace = self.migration_service.get_replacement_candidates(
                    existing_cards, quality_grades
                )
                result.cards_preserved = len(cards_to_preserve)
                result.cards_replaced = len(cards_to_replace)

            # 4. Generate new atoms for each section
            all_atoms: list[GeneratedAtom] = []

            for section in module.sections:
                section_atoms = await self._process_section(section, result)
                all_atoms.extend(section_atoms)
                result.sections_processed += 1

            # 5. QA check all generated atoms
            logger.info(f"QA checking {len(all_atoms)} atoms")
            qa_report = self.qa_pipeline.batch_qa(all_atoms)

            result.atoms_generated = qa_report.total_processed
            result.atoms_passed_qa = qa_report.passed
            result.atoms_flagged = qa_report.flagged
            result.atoms_rejected = qa_report.rejected
            result.grade_distribution = qa_report.grade_distribution
            result.qa_results = qa_report.results

            # Calculate average score
            if qa_report.results:
                result.avg_quality_score = sum(r.quality_score for r in qa_report.results) / len(
                    qa_report.results
                )

            # Count by type
            for atom in all_atoms:
                if atom.atom_type == AtomType.FLASHCARD:
                    result.flashcards_generated += 1
                elif atom.atom_type == AtomType.MCQ:
                    result.mcq_generated += 1
                elif atom.atom_type == AtomType.CLOZE:
                    result.cloze_generated += 1
                elif atom.atom_type == AtomType.PARSONS:
                    result.parsons_generated += 1

            # 6. Migrate learning state for replaced cards
            if include_migration and cards_to_replace:
                approved_atoms = [r.atom for r in qa_report.results if r.is_approved]
                matches = self.migration_service.find_content_matches(
                    cards_to_replace, approved_atoms
                )
                migration_results = await self.migration_service.migrate_states(matches)

                result.migration_report = self.migration_service.generate_migration_report(
                    cards_to_replace, approved_atoms, matches, migration_results
                )
                result.migrations_successful = sum(
                    1 for r in migration_results if r.state_transferred
                )

            # 7. Save to database
            if not dry_run:
                await self._save_results(module, result, qa_report)

            result.atoms = all_atoms
            result.status = "completed"

        except Exception as e:
            logger.exception(f"Pipeline failed for {module_path}")
            result.status = "failed"
            result.errors.append(str(e))

        result.completed_at = datetime.utcnow()
        return result

    async def _process_section(
        self,
        section: Section,
        result: GenerationJobResult,
    ) -> list[GeneratedAtom]:
        """Process a single section and its subsections."""
        atoms = []

        try:
            logger.debug(f"Processing section: {section.id} - {section.title}")

            # Generate atoms for this section
            gen_result = await self.atomizer.atomize_section(section)
            atoms.extend(gen_result.atoms)

            if gen_result.errors:
                result.errors.extend(gen_result.errors)

            # Process subsections recursively
            for subsection in section.subsections:
                sub_atoms = await self._process_section(subsection, result)
                atoms.extend(sub_atoms)

        except Exception as e:
            error_msg = f"Error processing section {section.id}: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)

        return atoms

    async def _get_existing_quality_grades(
        self,
        module_id: str,
    ) -> dict[str, str]:
        """Get existing quality grades from database."""
        grades = {}

        try:
            query = text("""
                SELECT card_id, quality_grade
                FROM stg_anki_cards
                WHERE card_id LIKE :prefix
                AND quality_grade IS NOT NULL
            """)

            result = self.db.execute(query, {"prefix": f"{module_id}%"})

            for row in result:
                grades[row[0]] = row[1]

        except Exception as e:
            logger.warning(f"Could not fetch existing grades: {e}")

        return grades

    async def _save_results(
        self,
        module: ModuleContent,
        result: GenerationJobResult,
        qa_report: QAReport,
    ) -> None:
        """Save generation results to database."""
        try:
            # Save job record
            job_query = text("""
                INSERT INTO ccna_generation_jobs (
                    id, module_id, job_type, status,
                    started_at, completed_at,
                    sections_total, sections_processed,
                    atoms_generated, atoms_passed_qa, atoms_flagged, atoms_rejected,
                    flashcards_generated, mcq_generated, cloze_generated, parsons_generated,
                    avg_quality_score, grade_distribution
                ) VALUES (
                    :id, :module_id, 'full', :status,
                    :started_at, :completed_at,
                    :sections_total, :sections_processed,
                    :atoms_generated, :atoms_passed_qa, :atoms_flagged, :atoms_rejected,
                    :flashcards, :mcq, :cloze, :parsons,
                    :avg_score, CAST(:grade_dist AS jsonb)
                )
            """)

            import json

            self.db.execute(
                job_query,
                {
                    "id": result.job_id,
                    "module_id": result.module_id,
                    "status": result.status,
                    "started_at": result.started_at,
                    "completed_at": result.completed_at,
                    "sections_total": result.sections_total,
                    "sections_processed": result.sections_processed,
                    "atoms_generated": result.atoms_generated,
                    "atoms_passed_qa": result.atoms_passed_qa,
                    "atoms_flagged": result.atoms_flagged,
                    "atoms_rejected": result.atoms_rejected,
                    "flashcards": result.flashcards_generated,
                    "mcq": result.mcq_generated,
                    "cloze": result.cloze_generated,
                    "parsons": result.parsons_generated,
                    "avg_score": result.avg_quality_score,
                    "grade_dist": json.dumps(result.grade_distribution),
                },
            )

            # Update module coverage
            coverage_query = text("""
                INSERT INTO ccna_module_coverage (
                    module_id, module_number, title,
                    total_lines, total_sections, estimated_atoms,
                    actual_atoms, coverage_percentage,
                    grade_a_count, grade_b_count, grade_c_count,
                    grade_d_count, grade_f_count,
                    avg_quality_score, status,
                    last_generation_job_id, last_generated_at
                ) VALUES (
                    :module_id, :module_num, :title,
                    :lines, :sections, :estimated,
                    :actual, :coverage,
                    :grade_a, :grade_b, :grade_c,
                    :grade_d, :grade_f,
                    :avg_score, 'completed',
                    :job_id, NOW()
                )
                ON CONFLICT (module_id) DO UPDATE SET
                    actual_atoms = EXCLUDED.actual_atoms,
                    coverage_percentage = EXCLUDED.coverage_percentage,
                    grade_a_count = EXCLUDED.grade_a_count,
                    grade_b_count = EXCLUDED.grade_b_count,
                    grade_c_count = EXCLUDED.grade_c_count,
                    grade_d_count = EXCLUDED.grade_d_count,
                    grade_f_count = EXCLUDED.grade_f_count,
                    avg_quality_score = EXCLUDED.avg_quality_score,
                    status = EXCLUDED.status,
                    last_generation_job_id = EXCLUDED.last_generation_job_id,
                    last_generated_at = NOW(),
                    updated_at = NOW()
            """)

            estimated = module.estimated_atoms or result.sections_total * 10
            coverage = (result.atoms_generated / estimated * 100) if estimated else 0

            self.db.execute(
                coverage_query,
                {
                    "module_id": module.module_id,
                    "module_num": module.module_number,
                    "title": module.title,
                    "lines": module.total_lines,
                    "sections": module.section_count,
                    "estimated": estimated,
                    "actual": result.atoms_generated,
                    "coverage": round(coverage, 2),
                    "grade_a": result.grade_distribution.get("A", 0),
                    "grade_b": result.grade_distribution.get("B", 0),
                    "grade_c": result.grade_distribution.get("C", 0),
                    "grade_d": result.grade_distribution.get("D", 0),
                    "grade_f": result.grade_distribution.get("F", 0),
                    "avg_score": result.avg_quality_score,
                    "job_id": result.job_id,
                },
            )

            # Save generated atoms
            for qa_result in qa_report.results:
                atom = qa_result.atom
                atom_query = text("""
                    INSERT INTO ccna_generated_atoms (
                        card_id, atom_type, module_id, section_id,
                        generation_job_id, front, back, content_json,
                        knowledge_type, quality_grade, quality_score,
                        quality_details, is_atomic, is_accurate, is_clear,
                        needs_review, tags
                    ) VALUES (
                        :card_id, :atom_type, :module_id, :section_id,
                        :job_id, :front, :back, CAST(:content_json AS jsonb),
                        :knowledge_type, :grade, :score,
                        CAST(:details AS jsonb), :is_atomic, :is_accurate, :is_clear,
                        :needs_review, :tags
                    )
                    ON CONFLICT (card_id) DO UPDATE SET
                        front = EXCLUDED.front,
                        back = EXCLUDED.back,
                        quality_grade = EXCLUDED.quality_grade,
                        quality_score = EXCLUDED.quality_score,
                        is_atomic = EXCLUDED.is_atomic,
                        needs_review = EXCLUDED.needs_review,
                        last_qa_at = NOW()
                """)

                self.db.execute(
                    atom_query,
                    {
                        "card_id": atom.card_id,
                        "atom_type": atom.atom_type.value,
                        "module_id": result.module_id,
                        "section_id": atom.source_section_id,
                        "job_id": result.job_id,
                        "front": atom.front,
                        "back": atom.back,
                        "content_json": json.dumps(atom.content_json)
                        if atom.content_json
                        else None,
                        "knowledge_type": atom.knowledge_type.value,
                        "grade": qa_result.quality_grade,
                        "score": qa_result.quality_score,
                        "details": json.dumps(
                            {
                                "issues": qa_result.issues,
                                "recommendations": qa_result.recommendations,
                            }
                        ),
                        "is_atomic": qa_result.is_atomic,
                        "is_accurate": qa_result.is_accurate,
                        "is_clear": qa_result.is_clear,
                        "needs_review": qa_result.needs_review,
                        "tags": atom.tags,
                    },
                )

            self.db.commit()
            logger.info(f"Saved generation results for {result.module_id}")

        except Exception as e:
            logger.error(f"Failed to save results: {e}")
            self.db.rollback()
            result.errors.append(f"Database save failed: {e}")

    async def process_all_modules(
        self,
        priority_modules: list[int] | None = None,
        dry_run: bool = False,
    ) -> FullGenerationReport:
        """
        Process all available CCNA modules.

        Args:
            priority_modules: Module numbers to process first (e.g., [7, 9, 10, 15, 16])
            dry_run: Don't save to database

        Returns:
            FullGenerationReport with all results
        """
        started_at = datetime.utcnow()

        # Get all available modules
        module_paths = self.parser.get_available_modules()
        logger.info(f"Found {len(module_paths)} CCNA modules")

        # Sort by priority
        if priority_modules:

            def sort_key(path: Path) -> int:
                num = self.parser._extract_module_number(path.stem)
                return (0 if num in priority_modules else 1, num)

            module_paths = sorted(module_paths, key=sort_key)

        results: list[GenerationJobResult] = []
        modules_completed = 0
        modules_failed = 0

        for module_path in module_paths:
            logger.info(f"Processing: {module_path.name}")

            result = await self.process_module(
                module_path,
                preserve_good_cards=True,
                include_migration=True,
                dry_run=dry_run,
            )

            results.append(result)

            if result.status == "completed":
                modules_completed += 1
            else:
                modules_failed += 1

            # Small delay between modules to avoid API rate limits
            await asyncio.sleep(1)

        # Calculate totals
        total_atoms = sum(r.atoms_generated for r in results)
        total_approved = sum(r.atoms_passed_qa for r in results)
        pass_rate = (total_approved / total_atoms * 100) if total_atoms else 0

        return FullGenerationReport(
            total_modules=len(module_paths),
            modules_completed=modules_completed,
            modules_failed=modules_failed,
            total_atoms_generated=total_atoms,
            total_atoms_approved=total_approved,
            overall_pass_rate=round(pass_rate, 2),
            module_results=results,
            started_at=started_at,
            completed_at=datetime.utcnow(),
        )

    def get_module_coverage_summary(self) -> list[dict[str, Any]]:
        """Get coverage summary for all modules from database."""
        try:
            query = text("""
                SELECT * FROM ccna_module_quality_summary
                ORDER BY module_id
            """)

            result = self.db.execute(query)
            columns = result.keys()

            return [dict(zip(columns, row)) for row in result]

        except Exception as e:
            logger.error(f"Failed to get coverage summary: {e}")
            return []

    def ensure_curriculum_setup(self) -> CurriculumMapping:
        """
        Ensure curriculum structure exists (Program, Track, Modules).

        Returns:
            CurriculumMapping with all database UUIDs
        """
        if self._curriculum_mapping is None:
            self._curriculum_mapping = self.curriculum_linker.ensure_curriculum_structure()
        return self._curriculum_mapping

    def _get_module_uuid(self, module_id: str) -> str | None:
        """Get database UUID for a module string ID."""
        mapping = self.ensure_curriculum_setup()
        uuid = mapping.module_id_map.get(module_id)
        return str(uuid) if uuid else None

    def _get_concept_for_section(
        self,
        section_id: str,
        module_id: str,
    ) -> str | None:
        """
        Get concept UUID for a section.

        Falls back to finding a concept in the module's cluster.
        """
        # Check cache first
        if section_id in self._section_concept_map:
            return self._section_concept_map[section_id]

        # Try to find concept by section_id pattern
        try:
            with session_scope() as session:
                # Find concepts in the module's cluster
                # The cluster name should contain module info
                from sqlalchemy import or_

                from src.db.models.canonical import CleanConceptCluster

                # Get cluster for this module
                cluster = (
                    session.query(CleanConceptCluster)
                    .filter(
                        or_(
                            CleanConceptCluster.name.ilike(f"%{module_id}%"),
                            CleanConceptCluster.display_order
                            == int(module_id.replace("NET-M", "")),
                        )
                    )
                    .first()
                )

                if cluster:
                    # Get first concept in cluster as default
                    concept = (
                        session.query(CleanConcept)
                        .filter(CleanConcept.cluster_id == cluster.id)
                        .first()
                    )
                    if concept:
                        concept_id = str(concept.id)
                        self._section_concept_map[section_id] = concept_id
                        return concept_id

        except Exception as e:
            logger.warning(f"Could not find concept for {section_id}: {e}")

        return None

    def _create_clean_atom_and_quiz(
        self,
        atom: GeneratedAtom,
        qa_result: QAResult,
        module_id: str,
        job_id: str,
    ) -> tuple[CleanAtom | None, QuizQuestion | None]:
        """
        Create CleanAtom and optionally QuizQuestion records.

        Args:
            atom: Generated atom
            qa_result: QA result for the atom
            module_id: Module string ID
            job_id: Generation job ID

        Returns:
            Tuple of (CleanAtom, QuizQuestion) - QuizQuestion only for quiz types
        """
        try:
            with session_scope() as session:
                # Get UUIDs
                module_uuid = self._get_module_uuid(module_id)
                concept_id = self._get_concept_for_section(atom.source_section_id, module_id)

                # Create CleanAtom
                clean_atom = CleanAtom(
                    card_id=atom.card_id,
                    atom_type=atom.atom_type.value,
                    front=atom.front,
                    back=atom.back,
                    # Link to concept and module
                    concept_id=concept_id,
                    module_id=module_uuid,
                    # Quality metadata
                    quality_score=qa_result.quality_score / 100.0
                    if qa_result.quality_score
                    else 0.0,
                    is_atomic=qa_result.is_atomic,
                    needs_review=qa_result.needs_review,
                    front_word_count=len(atom.front.split()),
                    back_word_count=len(atom.back.split()),
                    atomicity_status="atomic" if qa_result.is_atomic else "verbose",
                )
                session.add(clean_atom)
                session.flush()  # Get ID

                # Create QuizQuestion for quiz-compatible types
                quiz_question = None
                if atom.atom_type in [AtomType.MCQ, AtomType.TRUE_FALSE, AtomType.MATCHING]:
                    # Map atom type to quiz question type
                    quiz_type_map = {
                        AtomType.MCQ: "mcq",
                        AtomType.TRUE_FALSE: "true_false",
                        AtomType.MATCHING: "matching",
                    }

                    # Map knowledge type
                    knowledge_type_map = {
                        KnowledgeType.FACTUAL: "factual",
                        KnowledgeType.CONCEPTUAL: "conceptual",
                        KnowledgeType.PROCEDURAL: "procedural",
                    }

                    quiz_question = QuizQuestion(
                        atom_id=clean_atom.id,
                        question_type=quiz_type_map[atom.atom_type],
                        question_content=atom.content_json or {},
                        knowledge_type=knowledge_type_map.get(atom.knowledge_type, "conceptual"),
                        difficulty=0.5,  # Default, can be refined
                        intrinsic_load=self._estimate_cognitive_load(atom),
                        points=1,
                        partial_credit=atom.atom_type == AtomType.MATCHING,
                    )
                    session.add(quiz_question)

                session.commit()

                logger.debug(
                    f"Created CleanAtom {clean_atom.id}"
                    + (" with QuizQuestion" if quiz_question else "")
                )

                return clean_atom, quiz_question

        except Exception as e:
            logger.error(f"Failed to create CleanAtom/QuizQuestion for {atom.card_id}: {e}")
            return None, None

    def _estimate_cognitive_load(self, atom: GeneratedAtom) -> int:
        """
        Estimate intrinsic cognitive load (1-5) for a learning atom.

        Based on:
        - Number of elements to process
        - Complexity of relationships
        - Type of knowledge
        """
        load = 2  # Base load

        # Adjust by type
        if atom.atom_type == AtomType.MATCHING:
            # More pairs = higher load
            pairs = atom.content_json.get("pairs", []) if atom.content_json else []
            load = min(5, 2 + len(pairs) // 2)
        elif atom.atom_type == AtomType.MCQ:
            # More options = higher load
            options = atom.content_json.get("options", []) if atom.content_json else []
            load = min(4, 2 + len(options) // 2)
        elif atom.atom_type == AtomType.PARSONS:
            # More steps = higher load
            blocks = atom.content_json.get("blocks", []) if atom.content_json else []
            load = min(5, 2 + len(blocks) // 2)

        # Adjust by knowledge type
        if atom.knowledge_type == KnowledgeType.PROCEDURAL:
            load = min(5, load + 1)

        return load

    async def process_module_with_concept_linking(
        self,
        module_path: Path | str,
        preserve_good_cards: bool = True,
        include_migration: bool = True,
        create_learning_atoms: bool = True,
        dry_run: bool = False,
    ) -> GenerationJobResult:
        """
        Process a module with full concept and curriculum linking.

        This is the enhanced version of process_module that:
        1. Ensures curriculum structure exists
        2. Links atoms to Concepts and Modules
        3. Creates QuizQuestion records for quiz types
        4. Creates CleanAtom records

        Args:
            module_path: Path to module TXT file
            preserve_good_cards: Keep Grade A/B cards
            include_migration: Attempt learning state migration
            create_learning_atoms: Create CleanAtom + QuizQuestion records
            dry_run: Don't save to database

        Returns:
            GenerationJobResult with all stats
        """
        # Ensure curriculum setup
        if create_learning_atoms and not dry_run:
            self.ensure_curriculum_setup()

        # Run standard processing
        result = await self.process_module(
            module_path=module_path,
            preserve_good_cards=preserve_good_cards,
            include_migration=include_migration,
            dry_run=dry_run,
        )

        # Create CleanAtom and QuizQuestion records
        if create_learning_atoms and not dry_run and result.status == "completed":
            atoms_linked = 0
            quiz_questions_created = 0

            for qa_result in result.qa_results:
                if qa_result.is_approved:
                    clean_atom, quiz_q = self._create_clean_atom_and_quiz(
                        qa_result.atom,
                        qa_result,
                        result.module_id,
                        result.job_id,
                    )
                    if clean_atom:
                        atoms_linked += 1
                    if quiz_q:
                        quiz_questions_created += 1

            logger.info(
                f"Created {atoms_linked} CleanAtoms, "
                f"{quiz_questions_created} QuizQuestions for {result.module_id}"
            )

        return result
