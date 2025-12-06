"""
CCNA Learning Atom Factory - Assembly Line Architecture.

End-to-end pipeline for generating high-quality learning atoms from CCNA modules.
Implements "Clean on Generation" philosophy with section-based chunking.

Pipeline Stages (Assembly Line):
1. INPUT: Raw Module TXT file
2. STATION 1 (Chunking): CCNAChunker splits into ~30 semantic chunks per module
3. STATION 2 (Routing): Module-specific rules (Math Validator for M5/M11)
4. STATION 3 (Generation): RobustGenerator processes chunks in parallel
5. STATION 4 (Quality Gate): EnhancedQualityValidator checks structure/math/perplexity
6. OUTPUT: Clean JSON dataset with source_refs traceability

Usage:
    factory = CCNAAtomFactory()

    # Process single module
    result = await factory.process_module(module_number=5)

    # Dry run on specific modules
    results = await factory.dry_run([1, 5, 6])
"""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from config import get_settings
from src.processing.chunker import (
    CCNAChunker,
    TextChunk,
    ChunkType,
    analyze_chunks,
)
from src.generation.schemas import (
    get_array_schema,
    get_generation_config,
    validate_against_schema,
)
from src.generation.enhanced_quality_validator import (
    EnhancedQualityValidator,
    EnhancedValidationResult,
    ValidationSeverity,
    NumberSystemValidator,
    get_math_validator,
    validate_atom,
)
from src.generation.prompts import (
    SYSTEM_PROMPT,
    get_prompt,
)


# =============================================================================
# Configuration Constants
# =============================================================================

# Modules that require Math Validation (binary/hex/subnet calculations)
MATH_VALIDATION_MODULES = {5, 11}  # Module 5: Number Systems, Module 11: Subnetting

# Default concurrency limit for Vertex AI calls
DEFAULT_CONCURRENCY = 5

# Minimum quality score for acceptance
MIN_QUALITY_SCORE = 60.0

# Atom types to generate
ANKI_TYPES = ["flashcard", "cloze"]
NSL_TYPES = ["mcq", "true_false", "parsons", "matching"]
ALL_ATOM_TYPES = ANKI_TYPES + NSL_TYPES


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SourceReference:
    """Traceability link from atom back to source content."""
    chunk_id: str                    # e.g., "10.1.1"
    section_title: str               # e.g., "Basic Router Configuration Steps"
    parent_context: str              # e.g., "Module 10 > Configure Initial Router Settings"
    source_text_excerpt: str         # 10-30 word excerpt
    source_tag_ids: list[int] = field(default_factory=list)  # [source:XXX] tag IDs if present


@dataclass
class GeneratedAtom:
    """A generated and validated learning atom with full traceability."""
    id: str
    card_id: str
    atom_type: str
    front: str
    back: str

    # Source traceability (Golden Thread)
    source_refs: list[SourceReference] = field(default_factory=list)
    module_number: int = 0

    # Type-specific content
    content_json: Optional[dict] = None

    # Quality metrics
    quality_score: float = 100.0
    quality_grade: str = "A"
    validation_passed: bool = True
    validation_issues: list[str] = field(default_factory=list)

    # Metadata
    tags: list[str] = field(default_factory=list)
    knowledge_type: str = "factual"
    difficulty: int = 3
    blooms_level: str = "understand"
    derived_from_visual: bool = False

    # Fidelity Tracking (Hydration Audit)
    is_hydrated: bool = False
    fidelity_type: str = "verbatim_extract"  # verbatim_extract | rephrased_fact | ai_scenario_enrichment
    source_fact_basis: Optional[str] = None  # Raw fact used as anchor for hydrated content

    # Tracking
    generated_at: datetime = field(default_factory=datetime.now)
    generation_attempt: int = 1

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export."""
        return {
            "id": self.id,
            "card_id": self.card_id,
            "atom_type": self.atom_type,
            "front": self.front,
            "back": self.back,
            "source_refs": [
                {
                    "section_id": ref.chunk_id,
                    "section_title": ref.section_title,
                    "source_text_excerpt": ref.source_text_excerpt,
                }
                for ref in self.source_refs
            ],
            "content_json": self.content_json,
            "quality_score": self.quality_score,
            "quality_grade": self.quality_grade,
            "tags": self.tags,
            "metadata": {
                "knowledge_type": self.knowledge_type,
                "difficulty": self.difficulty,
                "blooms_level": self.blooms_level,
                "derived_from_visual": self.derived_from_visual,
                "module_number": self.module_number,
                # Fidelity Tracking (Hydration Audit)
                "is_hydrated": self.is_hydrated,
                "fidelity_type": self.fidelity_type,
                "source_fact_basis": self.source_fact_basis,
            },
        }


@dataclass
class ChunkProcessingResult:
    """Result of processing a single chunk."""
    chunk_id: str
    chunk_title: str
    atoms_generated: int = 0
    atoms_approved: int = 0
    atoms_rejected: int = 0
    atoms: list[GeneratedAtom] = field(default_factory=list)
    rejected_atoms: list[GeneratedAtom] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class ModuleProcessingResult:
    """Result of processing an entire CCNA module."""
    module_number: int
    module_title: str

    # Chunk statistics
    total_chunks: int = 0
    chunks_processed: int = 0
    chunks_skipped: int = 0

    # Atom statistics
    total_atoms_generated: int = 0
    total_atoms_approved: int = 0
    total_atoms_rejected: int = 0
    atoms_by_type: dict = field(default_factory=dict)

    # Quality metrics
    avg_quality_score: float = 0.0
    grade_distribution: dict = field(default_factory=dict)
    approval_rate: float = 0.0

    # Results
    atoms: list[GeneratedAtom] = field(default_factory=list)
    rejected_atoms: list[GeneratedAtom] = field(default_factory=list)
    chunk_results: list[ChunkProcessingResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Module-specific settings
    math_validation_enabled: bool = False

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0

    def to_summary_dict(self) -> dict:
        """Get summary for logging/reporting."""
        return {
            "module": self.module_number,
            "title": self.module_title,
            "chunks": f"{self.chunks_processed}/{self.total_chunks}",
            "atoms": {
                "generated": self.total_atoms_generated,
                "approved": self.total_atoms_approved,
                "rejected": self.total_atoms_rejected,
            },
            "by_type": self.atoms_by_type,
            "quality": {
                "avg_score": round(self.avg_quality_score, 1),
                "grades": self.grade_distribution,
                "approval_rate": f"{self.approval_rate:.1f}%",
            },
            "math_validation": self.math_validation_enabled,
            "duration_seconds": round(self.duration_seconds, 1),
            "errors": len(self.errors),
        }


# =============================================================================
# CCNA Atom Factory (Assembly Line)
# =============================================================================

class CCNAAtomFactory:
    """
    Assembly Line factory for generating learning atoms from CCNA modules.

    Architecture:
    - Station 1: CCNAChunker for section-based parsing
    - Station 2: Module routing (enable Math Validator for M5/M11)
    - Station 3: Parallel generation with concurrency control
    - Station 4: Quality validation with full traceability
    """

    # Default paths
    DEFAULT_CCNA_DIR = Path("docs/CCNA")

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        ccna_dir: Optional[Path] = None,
        concurrency: int = DEFAULT_CONCURRENCY,
        min_quality_score: float = MIN_QUALITY_SCORE,
    ):
        """
        Initialize the factory.

        Args:
            api_key: Gemini API key (uses settings if not provided)
            model_name: Model for generation (default: gemini-2.0-flash)
            ccna_dir: Directory containing CCNA TXT files
            concurrency: Max concurrent API calls (default: 5)
            min_quality_score: Minimum score for atom approval (default: 60)
        """
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model_name or settings.ai_model
        self.ccna_dir = ccna_dir or Path(settings.ccna_modules_path)
        self.min_quality_score = min_quality_score

        if not self.api_key:
            raise ValueError("Gemini API key required")

        # Initialize components
        self._client = None
        self.chunker = CCNAChunker(min_chunk_words=50)
        self.validator = EnhancedQualityValidator(
            use_perplexity=False,  # Disable for speed, enable for production
            use_grammar=False,
        )
        self.math_validator = get_math_validator()

        # Concurrency control
        self.semaphore = asyncio.Semaphore(concurrency)

        logger.info(f"CCNAAtomFactory initialized (model={self.model_name}, concurrency={concurrency})")

    @property
    def client(self):
        """Lazy-load Gemini client."""
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=SYSTEM_PROMPT,
            )
        return self._client

    # =========================================================================
    # Station 1: Chunking
    # =========================================================================

    def chunk_module(self, module_number: int) -> list[TextChunk]:
        """
        Station 1: Parse module into semantic chunks.

        Args:
            module_number: Module number (1-17)

        Returns:
            List of TextChunk objects ready for processing
        """
        module_path = self.ccna_dir / f"CCNA Module {module_number}.txt"

        if not module_path.exists():
            raise FileNotFoundError(f"Module file not found: {module_path}")

        chunks = self.chunker.parse_file(module_path)

        # Filter to chunks suitable for atom generation
        suitable_chunks = [c for c in chunks if c.is_suitable_for_atoms]

        logger.info(
            f"📦 Chunked Module {module_number}: "
            f"{len(suitable_chunks)}/{len(chunks)} chunks suitable"
        )

        return suitable_chunks

    # =========================================================================
    # Station 2: Routing (Module-Specific Settings)
    # =========================================================================

    def get_module_settings(self, module_number: int) -> dict:
        """
        Station 2: Determine module-specific processing settings.

        Args:
            module_number: Module number

        Returns:
            Dict with processing settings
        """
        settings = {
            "validate_math": module_number in MATH_VALIDATION_MODULES,
            "atom_types": ALL_ATOM_TYPES.copy(),
        }

        # Module 5 (Number Systems): Include numeric type, enable math
        if module_number == 5:
            settings["atom_types"] = ["flashcard", "cloze", "mcq", "true_false", "numeric"]
            logger.info(f"🔢 Module {module_number}: Math validation ENABLED + numeric atoms")

        # Module 11 (Subnetting): Include numeric type, enable math
        elif module_number == 11:
            settings["validate_math"] = True
            settings["atom_types"] = ["flashcard", "cloze", "mcq", "true_false", "numeric"]
            logger.info(f"🔢 Module {module_number}: Math validation ENABLED + numeric atoms")

        # Modules with heavy CLI content: Include Parsons
        elif module_number in {10, 12, 16, 17}:
            settings["atom_types"] = ALL_ATOM_TYPES  # Include Parsons
            logger.info(f"⌨️ Module {module_number}: CLI-heavy, including Parsons")

        return settings

    # =========================================================================
    # Station 3: Generation
    # =========================================================================

    async def generate_atoms_for_chunk(
        self,
        chunk: TextChunk,
        atom_types: list[str],
        validate_math: bool = False,
    ) -> ChunkProcessingResult:
        """
        Station 3: Generate atoms for a single chunk.

        Uses semaphore for concurrency control.

        Args:
            chunk: TextChunk to process
            atom_types: Types of atoms to generate
            validate_math: Enable math validation (for M5/M11)

        Returns:
            ChunkProcessingResult with atoms and statistics
        """
        result = ChunkProcessingResult(
            chunk_id=chunk.chunk_id,
            chunk_title=chunk.title,
        )

        async with self.semaphore:
            for atom_type in atom_types:
                # Skip Parsons if no CLI content
                if atom_type == "parsons" and not chunk.has_cli_commands:
                    continue

                # Skip matching if no tables
                if atom_type == "matching" and not chunk.has_tables:
                    continue

                try:
                    atoms = await self._generate_type_for_chunk(
                        chunk=chunk,
                        atom_type=atom_type,
                        validate_math=validate_math,
                    )

                    for atom in atoms:
                        result.atoms_generated += 1

                        if atom.validation_passed:
                            result.atoms_approved += 1
                            result.atoms.append(atom)
                        else:
                            result.atoms_rejected += 1
                            result.rejected_atoms.append(atom)

                except Exception as e:
                    error_msg = f"Error generating {atom_type} for {chunk.chunk_id}: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

        return result

    async def _generate_type_for_chunk(
        self,
        chunk: TextChunk,
        atom_type: str,
        validate_math: bool,
    ) -> list[GeneratedAtom]:
        """Generate atoms of a specific type for a chunk."""
        # Build prompt with context injection
        prompt = self._build_prompt(chunk, atom_type)

        try:
            response = self.client.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.8,
                    "max_output_tokens": 4096,
                },
            )

            if not response.text:
                return []

            # Parse response
            raw_atoms = self._parse_response(response.text)

            # Validate and create atoms
            validated_atoms = []
            for raw in raw_atoms:
                atom = self._create_and_validate_atom(
                    raw=raw,
                    atom_type=atom_type,
                    chunk=chunk,
                    validate_math=validate_math,
                )
                if atom:
                    validated_atoms.append(atom)

            return validated_atoms

        except Exception as e:
            logger.error(f"Generation failed for {atom_type}/{chunk.chunk_id}: {e}")
            return []

    def _build_prompt(self, chunk: TextChunk, atom_type: str) -> str:
        """Build generation prompt with context injection."""
        # Get the type-specific prompt template
        base_prompt = get_prompt(atom_type, chunk.chunk_id, chunk.content)

        # Inject parent context at the top
        context_header = f"""=== CONTEXT ===
{chunk.parent_context}
Section: {chunk.chunk_id} - {chunk.title}
Content Type: {chunk.chunk_type.value}
"""

        # Add visual handling hint if chunk has visuals
        if chunk.has_visuals:
            context_header += """
NOTE: This section contains visual/diagram descriptions.
Transform visual concepts into scenario-based questions.
Set metadata.derived_from_visual = true for these atoms.
"""

        return context_header + "\n" + base_prompt

    def _parse_response(self, response: str) -> list[dict]:
        """Parse LLM response into raw atom dicts."""
        # Try to extract JSON array
        json_match = re.search(r"\[[\s\S]*\]", response)
        if not json_match:
            # Try code block
            code_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
            if code_match:
                json_str = code_match.group(1).strip()
            else:
                return []
        else:
            json_str = json_match.group(0)

        try:
            data = json.loads(json_str)
            if isinstance(data, dict) and "atoms" in data:
                data = data["atoms"]
            if not isinstance(data, list):
                data = [data]
            return data
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            return []

    # =========================================================================
    # Station 4: Quality Gate
    # =========================================================================

    def _create_and_validate_atom(
        self,
        raw: dict,
        atom_type: str,
        chunk: TextChunk,
        validate_math: bool,
    ) -> Optional[GeneratedAtom]:
        """
        Station 4: Create atom and run through quality validation.

        Returns None if atom fails critical validation.
        """
        try:
            # Extract fields
            front = raw.get("front", "")
            back = raw.get("back", "")

            if not front:
                return None

            # Handle type-specific structures
            content_json = self._extract_content_json(raw, atom_type)
            if atom_type in ["mcq", "true_false", "parsons", "matching"]:
                back = self._extract_back_from_content(raw, atom_type, content_json)

            # Run quality validation
            validation = validate_atom(
                front=front,
                back=back,
                atom_type=atom_type,
                content_json=content_json,
                validate_math=validate_math,
            )

            # Additional math validation for Module 5/11
            math_issues = []
            if validate_math:
                math_issues = self.math_validator.validate_atom_math(front, back)
                for issue in math_issues:
                    if issue.severity == ValidationSeverity.ERROR:
                        validation.is_valid = False
                        validation.score -= 30

            # Build source reference (Golden Thread)
            source_ref = SourceReference(
                chunk_id=chunk.chunk_id,
                section_title=chunk.title,
                parent_context=chunk.parent_context,
                source_text_excerpt=self._extract_source_excerpt(raw, chunk),
                source_tag_ids=[tag.tag_id for tag in chunk.source_tags],
            )

            # Generate IDs
            atom_id = str(uuid.uuid4())
            type_prefix = {"flashcard": "FC", "cloze": "CL", "mcq": "MCQ",
                          "true_false": "TF", "parsons": "PAR", "matching": "MAT",
                          "numeric": "NUM"}.get(atom_type, "AT")
            card_id = raw.get("card_id", f"{chunk.chunk_id}-{type_prefix}-{uuid.uuid4().hex[:6]}")

            # Check if derived from visual
            derived_from_visual = (
                raw.get("metadata", {}).get("derived_from_visual", False) or
                chunk.has_visuals and "[IMAGE" in front
            )

            # Extract Fidelity Tracking fields from LLM response
            metadata = raw.get("metadata", {})
            is_hydrated = metadata.get("is_hydrated", False)
            fidelity_type = metadata.get("fidelity_type", "verbatim_extract")
            source_fact_basis = metadata.get("source_fact_basis", None)

            # Validate fidelity coherence: if hydrated, must have source_fact_basis
            if is_hydrated and not source_fact_basis:
                # Flag as validation warning (not critical, but trackable)
                logger.warning(
                    f"Atom {card_id}: is_hydrated=True but no source_fact_basis provided"
                )

            # Collect validation issues
            validation_issues = [f"{i.code}: {i.message}" for i in validation.issues]
            validation_issues.extend([f"MATH: {i.message}" for i in math_issues])

            return GeneratedAtom(
                id=atom_id,
                card_id=card_id,
                atom_type=atom_type,
                front=front,
                back=back,
                source_refs=[source_ref],
                module_number=chunk.module_number,
                content_json=content_json,
                quality_score=max(0, validation.score),
                quality_grade=self._score_to_grade(validation.score),
                validation_passed=validation.is_valid and validation.score >= self.min_quality_score,
                validation_issues=validation_issues,
                tags=raw.get("tags", [f"ccna-m{chunk.module_number}", chunk.chunk_id]),
                knowledge_type=raw.get("knowledge_type", raw.get("metadata", {}).get("knowledge_type", "factual")),
                difficulty=raw.get("difficulty", raw.get("metadata", {}).get("difficulty", 3)),
                blooms_level=raw.get("blooms_level", raw.get("metadata", {}).get("blooms_level", "understand")),
                derived_from_visual=derived_from_visual,
                # Fidelity Tracking
                is_hydrated=is_hydrated,
                fidelity_type=fidelity_type,
                source_fact_basis=source_fact_basis,
            )

        except Exception as e:
            logger.error(f"Error creating atom: {e}")
            return None

    def _extract_content_json(self, raw: dict, atom_type: str) -> Optional[dict]:
        """Extract type-specific content from raw atom."""
        if atom_type == "mcq":
            return {
                "options": raw.get("options", []),
                "correct_index": raw.get("correct_index", 0),
                "explanation": raw.get("explanation", ""),
                "distractors_rationale": raw.get("distractors_rationale", []),
            }
        elif atom_type == "true_false":
            return {
                "correct": raw.get("correct", True),
                "explanation": raw.get("explanation", ""),
            }
        elif atom_type == "parsons":
            return {
                "blocks": raw.get("correct_sequence", []),
                "distractors": raw.get("distractors", []),
                "starting_mode": raw.get("starting_mode", "user EXEC"),
            }
        elif atom_type == "matching":
            return {
                "pairs": raw.get("pairs", []),
                "category": raw.get("category", ""),
            }
        return None

    def _extract_back_from_content(self, raw: dict, atom_type: str, content_json: dict) -> str:
        """Extract 'back' field from type-specific content."""
        if atom_type == "mcq":
            options = content_json.get("options", [])
            correct_idx = content_json.get("correct_index", 0)
            return options[correct_idx] if options and 0 <= correct_idx < len(options) else ""
        elif atom_type == "true_false":
            return "True" if content_json.get("correct", True) else "False"
        elif atom_type == "parsons":
            blocks = content_json.get("blocks", [])
            return " → ".join(blocks)
        elif atom_type == "matching":
            pairs = content_json.get("pairs", [])
            return "\n".join([f"{p.get('left', '')} → {p.get('right', '')}" for p in pairs])
        return raw.get("back", "")

    def _extract_source_excerpt(self, raw: dict, chunk: TextChunk) -> str:
        """Extract source text excerpt for traceability."""
        # First try to get from raw atom (if LLM provided it)
        source_refs = raw.get("source_refs", [])
        if source_refs and isinstance(source_refs, list) and source_refs[0].get("source_text_excerpt"):
            return source_refs[0]["source_text_excerpt"]

        # Fallback: use first 100 chars of chunk content
        return chunk.content[:150].strip() + "..."

    def _score_to_grade(self, score: float) -> str:
        """Convert score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 75:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 40:
            return "D"
        return "F"

    # =========================================================================
    # Module Processing (Full Pipeline)
    # =========================================================================

    async def process_module(
        self,
        module_number: int,
        chunk_limit: Optional[int] = None,
    ) -> ModuleProcessingResult:
        """
        Process an entire CCNA module through the assembly line.

        Args:
            module_number: Module number (1-17)
            chunk_limit: Limit chunks for testing (default: all)

        Returns:
            ModuleProcessingResult with all atoms and statistics
        """
        result = ModuleProcessingResult(
            module_number=module_number,
            module_title=f"Module {module_number}",
            started_at=datetime.now(),
        )

        try:
            # Station 1: Chunking
            chunks = self.chunk_module(module_number)
            result.total_chunks = len(chunks)

            # Apply limit if specified
            if chunk_limit:
                chunks = chunks[:chunk_limit]

            # Station 2: Get module settings
            settings = self.get_module_settings(module_number)
            result.math_validation_enabled = settings["validate_math"]

            # Station 3 & 4: Parallel generation with quality gate
            logger.info(f"🏭 Processing {len(chunks)} chunks for Module {module_number}...")

            tasks = [
                self.generate_atoms_for_chunk(
                    chunk=chunk,
                    atom_types=settings["atom_types"],
                    validate_math=settings["validate_math"],
                )
                for chunk in chunks
            ]

            chunk_results = await asyncio.gather(*tasks)

            # Aggregate results
            for chunk_result in chunk_results:
                result.chunk_results.append(chunk_result)
                result.chunks_processed += 1

                result.total_atoms_generated += chunk_result.atoms_generated
                result.total_atoms_approved += chunk_result.atoms_approved
                result.total_atoms_rejected += chunk_result.atoms_rejected

                result.atoms.extend(chunk_result.atoms)
                result.rejected_atoms.extend(chunk_result.rejected_atoms)
                result.errors.extend(chunk_result.errors)

                # Track by type
                for atom in chunk_result.atoms:
                    if atom.atom_type not in result.atoms_by_type:
                        result.atoms_by_type[atom.atom_type] = 0
                    result.atoms_by_type[atom.atom_type] += 1

            # Calculate quality metrics
            if result.atoms:
                result.avg_quality_score = sum(a.quality_score for a in result.atoms) / len(result.atoms)

                for atom in result.atoms:
                    grade = atom.quality_grade
                    result.grade_distribution[grade] = result.grade_distribution.get(grade, 0) + 1

                ab_count = result.grade_distribution.get("A", 0) + result.grade_distribution.get("B", 0)
                result.approval_rate = (ab_count / len(result.atoms)) * 100

            result.completed_at = datetime.now()

            logger.info(
                f"✅ Module {module_number} complete: "
                f"{result.total_atoms_approved}/{result.total_atoms_generated} atoms approved "
                f"({result.approval_rate:.1f}%) in {result.duration_seconds:.1f}s"
            )

        except Exception as e:
            error_msg = f"Error processing module {module_number}: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            result.completed_at = datetime.now()

        return result

    async def dry_run(
        self,
        modules: list[int] = None,
        chunks_per_module: int = 2,
    ) -> list[ModuleProcessingResult]:
        """
        Dry run on selected modules for testing.

        Args:
            modules: Module numbers to test (default: [1, 5, 6])
            chunks_per_module: Chunks to process per module

        Returns:
            List of ModuleProcessingResult
        """
        if modules is None:
            modules = [1, 5, 6]  # Recommended test modules

        logger.info(f"🧪 Dry run: Modules {modules}, {chunks_per_module} chunks each")

        results = []
        for module_num in modules:
            result = await self.process_module(
                module_number=module_num,
                chunk_limit=chunks_per_module,
            )
            results.append(result)

            # Print summary
            print(f"\n{'-' * 50}")
            print(f"Module {module_num}: {result.module_title}")
            print(f"  Chunks: {result.chunks_processed}/{result.total_chunks}")
            print(f"  Atoms: {result.total_atoms_approved}/{result.total_atoms_generated} approved")
            print(f"  By type: {result.atoms_by_type}")
            print(f"  Quality: {result.avg_quality_score:.1f} avg, {result.approval_rate:.1f}% A/B")
            print(f"  Math validation: {'ON' if result.math_validation_enabled else 'OFF'}")

        return results

    async def process_all_modules(
        self,
        module_numbers: list[int] = None,
    ) -> list[ModuleProcessingResult]:
        """
        Process all CCNA modules.

        Args:
            module_numbers: Specific modules (default: 1-17)

        Returns:
            List of ModuleProcessingResult
        """
        if module_numbers is None:
            module_numbers = list(range(1, 18))

        results = []
        for num in module_numbers:
            try:
                result = await self.process_module(num)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process module {num}: {e}")

        # Summary
        total_atoms = sum(r.total_atoms_approved for r in results)
        total_rejected = sum(r.total_atoms_rejected for r in results)

        logger.info(
            f"🏁 All modules complete: {total_atoms} atoms approved, "
            f"{total_rejected} rejected across {len(results)} modules"
        )

        return results

    def export_results(
        self,
        result: ModuleProcessingResult,
        output_dir: Path = None,
    ) -> Path:
        """
        Export results to JSON file.

        Args:
            result: ModuleProcessingResult to export
            output_dir: Output directory (default: outputs/)

        Returns:
            Path to exported file
        """
        if output_dir is None:
            output_dir = Path("outputs")
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"module_{result.module_number}_atoms_{timestamp}.json"

        export_data = {
            "summary": result.to_summary_dict(),
            "atoms": [atom.to_dict() for atom in result.atoms],
            "rejected_atoms": [atom.to_dict() for atom in result.rejected_atoms],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"📤 Exported to {output_path}")
        return output_path


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import sys

    # Fix Windows console encoding for emoji output
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

    async def main():
        # Parse args
        mode = sys.argv[1] if len(sys.argv) > 1 else "dry"
        module_num = int(sys.argv[2]) if len(sys.argv) > 2 else None

        print("\n" + "=" * 60)
        print("🏭 CCNA Atom Factory - Assembly Line")
        print("=" * 60)

        factory = CCNAAtomFactory()

        if mode == "dry":
            # Dry run on test modules
            modules = [module_num] if module_num else [1, 5, 6]
            results = await factory.dry_run(modules=modules, chunks_per_module=2)

        elif mode == "module" and module_num:
            # Process single module
            result = await factory.process_module(module_num)
            factory.export_results(result)

            print(f"\n=== Module {module_num} Results ===")
            print(json.dumps(result.to_summary_dict(), indent=2))

        elif mode == "all":
            # Process all modules
            results = await factory.process_all_modules()

            print("\n=== Summary ===")
            for r in results:
                print(f"M{r.module_number}: {r.total_atoms_approved} atoms ({r.approval_rate:.0f}%)")

        else:
            print("Usage:")
            print("  python ccna_atom_factory.py dry          # Dry run on M1, M5, M6")
            print("  python ccna_atom_factory.py dry 5        # Dry run on M5 only")
            print("  python ccna_atom_factory.py module 5     # Full run on M5")
            print("  python ccna_atom_factory.py all          # Full run on all modules")

    asyncio.run(main())
