"""
Note Actions Service - Enhanced Study Materials Generation.

Provides actions after viewing a study note:
- Generate comparison tables
- Generate Mermaid diagrams
- Generate flashcards/cloze with smart deduplication
- Create Anki filtered decks

Uses "multiple paths to retention" - allows same concept in different formats.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from src.anki.anki_client import AnkiClient
    from src.ccna.atomizer_service import AtomizerService, GeneratedAtom
    from src.ccna.content_parser import Section
    from src.content.reader import ContentReader
    from src.semantic.embedding_service import EmbeddingService
    from src.semantic.similarity_service import SemanticSimilarityService, SimilarityMatch


# Check for Gemini API
try:
    import google.generativeai as genai

    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

GENAI_API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
DEFAULT_MODEL = "gemini-2.0-flash"


class DuplicationPolicy(str, Enum):
    """How to handle detected duplicates."""

    INSERT = "insert"  # Novel content, insert
    SKIP_EXACT = "skip_exact"  # Same content + type, skip
    ALLOW_CROSS_FORMAT = "allow_cross_format"  # Same concept, different format
    PROMPT_BORDERLINE = "prompt_borderline"  # User decides


@dataclass
class DuplicationResult:
    """Result of checking for duplicates."""

    policy: DuplicationPolicy
    existing_atom_id: UUID | None = None
    existing_front: str | None = None
    existing_type: str | None = None
    similarity_score: float = 0.0


@dataclass
class AtomInsertionResult:
    """Result of attempting to insert generated atoms."""

    section_id: str
    inserted: list[GeneratedAtom] = field(default_factory=list)
    skipped_exact: list[tuple[GeneratedAtom, DuplicationResult]] = field(
        default_factory=list
    )
    allowed_cross_format: list[tuple[GeneratedAtom, DuplicationResult]] = field(
        default_factory=list
    )
    prompted_borderline: list[tuple[GeneratedAtom, DuplicationResult]] = field(
        default_factory=list
    )
    errors: list[str] = field(default_factory=list)

    @property
    def total_generated(self) -> int:
        return (
            len(self.inserted)
            + len(self.skipped_exact)
            + len(self.allowed_cross_format)
            + len(self.prompted_borderline)
        )


# LLM Prompts
COMPARISON_TABLE_PROMPT = """Based on this section content, generate a markdown comparison table.

Section: {section_title}
Content:
{content}

Identify the 2-3 most important concepts that can be compared and create a table with:
- Column headers: Feature/Aspect | Concept A | Concept B [| Concept C if applicable]
- 4-6 comparison rows covering key differences
- Use concise, precise language

Output ONLY the markdown table, no additional text."""

MERMAID_DIAGRAM_PROMPT = """Generate a Mermaid {diagram_type} diagram for this networking concept.

Section: {section_title}
Content:
{content}

Create a {diagram_type} diagram that:
- Shows the main flow/relationship/states
- Uses proper Mermaid syntax
- Is concise (5-10 nodes maximum)
- Labels edges where helpful

Output ONLY the Mermaid code block starting with ```mermaid and ending with ```, no additional text.
Example format:
```mermaid
flowchart TD
    A[Start] --> B[Process]
    B --> C[End]
```"""


class NoteActionsService:
    """
    Orchestrates all note action operations.

    Composes existing services rather than duplicating logic.
    Implements smart deduplication that respects "multiple paths to retention".
    """

    def __init__(
        self,
        db_session: Session,
        content_reader: ContentReader | None = None,
        atomizer: AtomizerService | None = None,
        similarity_service: SemanticSimilarityService | None = None,
        anki_client: AnkiClient | None = None,
        embedding_service: EmbeddingService | None = None,
        model_name: str = DEFAULT_MODEL,
    ):
        """
        Initialize the service with dependencies.

        All dependencies are optional and will be lazy-loaded if not provided.
        """
        self.db = db_session
        self._content_reader = content_reader
        self._atomizer = atomizer
        self._similarity_service = similarity_service
        self._anki_client = anki_client
        self._embedding_service = embedding_service
        self._model = None
        self._model_name = model_name

    @property
    def content_reader(self) -> ContentReader:
        """Lazy-load ContentReader."""
        if self._content_reader is None:
            from src.content.reader import ContentReader

            self._content_reader = ContentReader()
        return self._content_reader

    @property
    def atomizer(self) -> AtomizerService:
        """Lazy-load AtomizerService."""
        if self._atomizer is None:
            from src.ccna.atomizer_service import AtomizerService

            self._atomizer = AtomizerService()
        return self._atomizer

    @property
    def similarity_service(self) -> SemanticSimilarityService:
        """Lazy-load SemanticSimilarityService."""
        if self._similarity_service is None:
            from src.semantic.similarity_service import SemanticSimilarityService

            self._similarity_service = SemanticSimilarityService(self.db)
        return self._similarity_service

    @property
    def anki_client(self) -> AnkiClient:
        """Lazy-load AnkiClient."""
        if self._anki_client is None:
            from src.anki.anki_client import AnkiClient

            self._anki_client = AnkiClient()
        return self._anki_client

    @property
    def embedding_service(self) -> EmbeddingService:
        """Lazy-load EmbeddingService."""
        if self._embedding_service is None:
            from src.semantic.embedding_service import EmbeddingService

            self._embedding_service = EmbeddingService()
        return self._embedding_service

    @property
    def model(self):
        """Lazy-load Gemini model."""
        if self._model is None and HAS_GENAI and GENAI_API_KEY:
            genai.configure(api_key=GENAI_API_KEY)
            self._model = genai.GenerativeModel(self._model_name)
        return self._model

    # =========================================================================
    # Content Generation
    # =========================================================================

    def generate_comparison_table(
        self,
        note: dict,
        concepts_to_compare: list[str] | None = None,
    ) -> tuple[bool, str]:
        """
        Generate a markdown comparison table for concepts in the note's section.

        Args:
            note: Note dict with section_id, module_number
            concepts_to_compare: Optional specific concepts to compare

        Returns:
            Tuple of (success, content_or_error)
        """
        if not self.model:
            return False, "LLM not configured. Set GEMINI_API_KEY environment variable."

        # Get section content
        section = self._get_section_from_note(note)
        if not section:
            return False, f"Section {note.get('section_id')} not found"

        prompt = COMPARISON_TABLE_PROMPT.format(
            section_title=section.title,
            content=section.content[:4000],  # Limit content length
        )

        if concepts_to_compare:
            prompt += f"\n\nFocus on comparing: {', '.join(concepts_to_compare)}"

        try:
            response = self.model.generate_content(prompt)
            return True, response.text
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return False, f"LLM generation failed: {e}"

    def generate_mermaid_diagram(
        self,
        note: dict,
        diagram_type: str = "flowchart",
    ) -> tuple[bool, str]:
        """
        Generate a Mermaid diagram for the note's section content.

        Args:
            note: Note dict with section_id, module_number
            diagram_type: Type of diagram (flowchart, sequence, state)

        Returns:
            Tuple of (success, content_or_error)
        """
        if not self.model:
            return False, "LLM not configured. Set GEMINI_API_KEY environment variable."

        section = self._get_section_from_note(note)
        if not section:
            return False, f"Section {note.get('section_id')} not found"

        prompt = MERMAID_DIAGRAM_PROMPT.format(
            diagram_type=diagram_type,
            section_title=section.title,
            content=section.content[:4000],
        )

        try:
            response = self.model.generate_content(prompt)
            return True, response.text
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return False, f"LLM generation failed: {e}"

    # =========================================================================
    # Atom Generation with Deduplication
    # =========================================================================

    async def generate_atoms_for_note(
        self,
        note: dict,
        atom_types: list[str] | None = None,
    ) -> AtomInsertionResult:
        """
        Generate flashcards and cloze from note's section, with smart dedup.

        Args:
            note: Note dict with section_id, module_number
            atom_types: Types to generate (default: flashcard, cloze)

        Returns:
            AtomInsertionResult with counts for each category
        """
        from src.ccna.atomizer_service import AtomType

        section_id = note.get("section_id", "")
        result = AtomInsertionResult(section_id=section_id)

        # Default to flashcard and cloze
        if atom_types is None:
            atom_types = ["flashcard", "cloze"]

        # Get section content
        section = self._get_section_from_note(note)
        if not section:
            result.errors.append(f"Section {section_id} not found")
            return result

        # Convert string types to AtomType enum
        target_types = []
        for t in atom_types:
            try:
                target_types.append(AtomType(t))
            except ValueError:
                result.errors.append(f"Unknown atom type: {t}")

        if not target_types:
            return result

        # Generate atoms using AtomizerService
        try:
            gen_result = await self.atomizer.atomize_section(section, target_types)
        except Exception as e:
            logger.error(f"Atom generation failed: {e}")
            result.errors.append(f"Atom generation failed: {e}")
            return result

        # Process each generated atom with deduplication
        for atom in gen_result.atoms:
            dedup_result = self.check_for_duplicates(
                front=atom.front,
                back=atom.back,
                atom_type=atom.atom_type.value,
            )

            if dedup_result.policy == DuplicationPolicy.SKIP_EXACT:
                result.skipped_exact.append((atom, dedup_result))
                logger.debug(f"Skipping exact duplicate: {atom.front[:50]}...")

            elif dedup_result.policy == DuplicationPolicy.ALLOW_CROSS_FORMAT:
                # Insert despite similarity - different format = multiple retention paths
                self._insert_atom(atom, section_id)
                result.allowed_cross_format.append((atom, dedup_result))
                result.inserted.append(atom)
                logger.info(
                    f"Allowing cross-format: {atom.atom_type.value} vs existing {dedup_result.existing_type}"
                )

            elif dedup_result.policy == DuplicationPolicy.PROMPT_BORDERLINE:
                # Don't auto-insert, let user decide
                result.prompted_borderline.append((atom, dedup_result))
                logger.debug(f"Borderline duplicate: {atom.front[:50]}...")

            else:  # INSERT - novel content
                self._insert_atom(atom, section_id)
                result.inserted.append(atom)

        return result

    def check_for_duplicates(
        self,
        front: str,
        back: str,
        atom_type: str,
        exact_threshold: float = 0.85,
        borderline_threshold: float = 0.70,
    ) -> DuplicationResult:
        """
        Check if new atom duplicates existing content.

        Implements "multiple paths to retention" logic:
        - Exact duplicate (>0.85 + same type) -> SKIP
        - Cross-format (>0.85 + different type) -> ALLOW
        - Borderline (0.70-0.85) -> PROMPT user
        - Novel (<0.70) -> INSERT

        Args:
            front: Atom front text
            back: Atom back text
            atom_type: Type of the new atom (flashcard, cloze, etc.)
            exact_threshold: Threshold for exact duplicates
            borderline_threshold: Threshold for borderline cases

        Returns:
            DuplicationResult with policy and match details
        """
        combined_text = f"{front} [SEP] {back}"

        try:
            matches = self.similarity_service.find_similar_to_text(
                text=combined_text,
                threshold=borderline_threshold,
                limit=5,
            )
        except Exception as e:
            logger.warning(f"Similarity check failed: {e}")
            return DuplicationResult(policy=DuplicationPolicy.INSERT)

        if not matches:
            return DuplicationResult(policy=DuplicationPolicy.INSERT)

        # Get atom types for matches
        match_types = self._get_atom_types_for_ids(
            [m.atom_id_2 for m in matches]
        )

        # Check best match
        best_match = matches[0]
        best_match_type = match_types.get(best_match.atom_id_2)

        if best_match.similarity_score > exact_threshold:
            if best_match_type == atom_type:
                # Same content + same type = exact duplicate
                return DuplicationResult(
                    policy=DuplicationPolicy.SKIP_EXACT,
                    existing_atom_id=best_match.atom_id_2,
                    existing_front=best_match.front_2,
                    existing_type=best_match_type,
                    similarity_score=best_match.similarity_score,
                )
            else:
                # Same content + different type = allow for multiple retention paths
                return DuplicationResult(
                    policy=DuplicationPolicy.ALLOW_CROSS_FORMAT,
                    existing_atom_id=best_match.atom_id_2,
                    existing_front=best_match.front_2,
                    existing_type=best_match_type,
                    similarity_score=best_match.similarity_score,
                )
        else:
            # Borderline case - let user decide
            return DuplicationResult(
                policy=DuplicationPolicy.PROMPT_BORDERLINE,
                existing_atom_id=best_match.atom_id_2,
                existing_front=best_match.front_2,
                existing_type=best_match_type,
                similarity_score=best_match.similarity_score,
            )

    def _get_atom_types_for_ids(self, atom_ids: list[UUID]) -> dict[UUID, str]:
        """Get atom types for a list of atom IDs."""
        if not atom_ids:
            return {}

        query = text("""
            SELECT id, atom_type
            FROM learning_atoms
            WHERE id = ANY(:ids)
        """)

        try:
            result = self.db.execute(query, {"ids": [str(id) for id in atom_ids]})
            return {UUID(row.id): row.atom_type for row in result.fetchall()}
        except Exception as e:
            logger.warning(f"Failed to get atom types: {e}")
            return {}

    def _insert_atom(self, atom: GeneratedAtom, section_id: str) -> bool:
        """Insert a generated atom into the database."""
        import json
        from uuid import uuid4

        query = text("""
            INSERT INTO learning_atoms (
                id, card_id, atom_type, front, back, ccna_section_id,
                quality_score, source, created_at
            ) VALUES (
                :id, :card_id, :atom_type, :front, :back, :section_id,
                :quality_score, 'note_actions', NOW()
            )
        """)

        try:
            self.db.execute(
                query,
                {
                    "id": str(uuid4()),
                    "card_id": atom.card_id,
                    "atom_type": atom.atom_type.value,
                    "front": atom.front,
                    "back": json.dumps(atom.content_json) if atom.content_json else atom.back,
                    "section_id": section_id,
                    "quality_score": atom.quality_score,
                },
            )
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to insert atom: {e}")
            self.db.rollback()
            return False

    # =========================================================================
    # Anki Integration
    # =========================================================================

    def create_anki_filtered_deck(
        self,
        note: dict,
        card_limit: int = 100,
    ) -> tuple[bool, str]:
        """
        Create Anki filtered deck for note's section.

        Args:
            note: Note dict with section_id, title
            card_limit: Maximum cards in filtered deck

        Returns:
            Tuple of (success, message)
        """
        section_id = note.get("section_id", "")
        title = note.get("title", "Study")

        # Build search query - match cards tagged with this section
        search_query = f'deck:CCNA::ITN::* tag:section:{section_id}'

        # Build deck name
        safe_title = "".join(c if c.isalnum() or c in "-_ " else "" for c in title)
        safe_title = safe_title.replace(" ", "-")[:30]
        deck_name = f"CCNA::Remediation::{section_id}-{safe_title}"

        # Check Anki connection
        if not self.anki_client.check_connection():
            return False, "Anki not running. Start Anki with AnkiConnect and try again."

        # Create filtered deck
        try:
            success = self.anki_client.create_filtered_deck(
                name=deck_name,
                search_query=search_query,
                limit=card_limit,
                order=5,  # Random order
            )

            if success:
                return True, f"Created deck: {deck_name}"
            else:
                return False, f"Failed to create deck. Search query: {search_query}"
        except Exception as e:
            logger.error(f"Anki deck creation failed: {e}")
            return False, f"Anki error: {e}"

    def get_anki_search_query(self, note: dict) -> str:
        """
        Get the Anki search query for a note's section.

        Useful for manual deck creation if AnkiConnect is unavailable.
        """
        section_id = note.get("section_id", "")
        return f'deck:CCNA::ITN::* tag:section:{section_id}'

    # =========================================================================
    # Helpers
    # =========================================================================

    def _get_section_from_note(self, note: dict) -> Section | None:
        """Get Section object from note dict."""
        section_id = note.get("section_id", "")
        module_number = note.get("module_number")

        if not section_id or not module_number:
            return None

        return self.content_reader.get_section(module_number, section_id)

    def insert_borderline_atoms(
        self,
        atoms_with_results: list[tuple[GeneratedAtom, DuplicationResult]],
        section_id: str,
    ) -> int:
        """
        Insert borderline atoms that user has approved.

        Args:
            atoms_with_results: List of (atom, dedup_result) tuples
            section_id: Section ID for linking

        Returns:
            Number of atoms inserted
        """
        inserted = 0
        for atom, _ in atoms_with_results:
            if self._insert_atom(atom, section_id):
                inserted += 1
        return inserted
