"""
Content importer - converts local content to learning atoms.

Supports multiple formats:
- Q/A pairs (Q: ... A: ...)
- Markdown headers (## Question\nAnswer)
- Cloze deletions ({{c1::answer}})
- MCQ format (A) B) C) D) with * marking correct)
"""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from src.db.database import engine

from .parser import ContentParser, ContentSection, ParsedContent


@dataclass
class ImportedAtom:
    """An atom ready for database insertion."""

    front: str
    back: str
    atom_type: str
    source_file: str
    source_section: str = ""
    options: list[str] | None = None  # For MCQ
    correct_answer: str | None = None  # For MCQ
    steps: list[str] | None = None  # For Parsons


@dataclass
class ImportResult:
    """Result of an import operation."""

    total_parsed: int = 0
    total_imported: int = 0
    duplicates_skipped: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class ContentImporter:
    """
    Import local content files as learning atoms.

    Detects atom type from content structure:
    - Q: A: pairs -> flashcard
    - {{cloze}} markers -> cloze
    - A) B) C) D) options -> mcq
    - Step sequences -> parsons
    """

    def __init__(self, dry_run: bool = False):
        """
        Initialize importer.

        Args:
            dry_run: If True, parse and validate but don't insert into DB
        """
        self.dry_run = dry_run
        self.parser = ContentParser()

    def import_file(self, path: Path | str) -> ImportResult:
        """Import atoms from a single file."""
        content = self.parser.parse_file(path)
        return self._import_content(content)

    def import_directory(
        self, path: Path | str, pattern: str = "*.txt"
    ) -> ImportResult:
        """Import atoms from all matching files in a directory."""
        path = Path(path)
        results = ImportResult()

        for file_path in sorted(path.glob(pattern)):
            try:
                file_result = self.import_file(file_path)
                results.total_parsed += file_result.total_parsed
                results.total_imported += file_result.total_imported
                results.duplicates_skipped += file_result.duplicates_skipped
                results.errors.extend(file_result.errors)
            except Exception as e:
                results.errors.append(f"{file_path}: {e}")

        return results

    def _import_content(self, content: ParsedContent) -> ImportResult:
        """Import atoms from parsed content."""
        result = ImportResult()
        atoms = []

        # Try to extract atoms from raw text first (for Q/A format)
        raw_atoms = self._extract_qa_pairs(content.raw_text, content.source_path)
        atoms.extend(raw_atoms)

        # Also try section-based extraction
        for section in content.sections:
            section_atoms = self._extract_from_section(section)
            atoms.extend(section_atoms)

        result.total_parsed = len(atoms)

        # Insert into database
        if not self.dry_run and atoms:
            imported, duplicates = self._insert_atoms(atoms)
            result.total_imported = imported
            result.duplicates_skipped = duplicates
        else:
            result.total_imported = 0

        return result

    def _extract_qa_pairs(self, text: str, source: str) -> list[ImportedAtom]:
        """Extract Q/A pairs from text."""
        atoms = []

        # Pattern 1: Q: ... A: ... format
        qa_pattern = r"Q:\s*(.+?)\s*A:\s*(.+?)(?=Q:|$)"
        for match in re.finditer(qa_pattern, text, re.DOTALL | re.IGNORECASE):
            front = match.group(1).strip()
            back = match.group(2).strip()

            if front and back:
                atom_type = self._detect_type(front, back)
                atoms.append(
                    ImportedAtom(
                        front=front,
                        back=back,
                        atom_type=atom_type,
                        source_file=source,
                    )
                )

        return atoms

    def _extract_from_section(self, section: ContentSection) -> list[ImportedAtom]:
        """Extract atoms from a content section."""
        atoms = []
        content = section.content

        # Check for cloze deletions
        if "{{" in content:
            atoms.extend(self._extract_cloze(section))

        # Check for MCQ format
        if re.search(r"[A-D]\)", content) or re.search(r"\*\s*[A-D]\)", content):
            mcq = self._extract_mcq(section)
            if mcq:
                atoms.append(mcq)

        # If nothing specific found, treat as flashcard if it has a question-like title
        if not atoms and self._looks_like_question(section.title):
            atoms.append(
                ImportedAtom(
                    front=section.title,
                    back=content,
                    atom_type="flashcard",
                    source_file=section.source_file,
                    source_section=section.title,
                )
            )

        return atoms

    def _extract_cloze(self, section: ContentSection) -> list[ImportedAtom]:
        """Extract cloze deletions from content."""
        atoms = []
        content = section.content

        # Pattern: {{c1::answer}} or {{answer}}
        pattern = r"\{\{(?:c\d+::)?([^}]+)\}\}"

        if re.search(pattern, content):
            atoms.append(
                ImportedAtom(
                    front=content,  # Keep cloze markers in front
                    back=re.sub(pattern, r"\1", content),  # Replace with answers
                    atom_type="cloze",
                    source_file=section.source_file,
                    source_section=section.title,
                )
            )

        return atoms

    def _extract_mcq(self, section: ContentSection) -> ImportedAtom | None:
        """Extract MCQ from content."""
        content = section.content
        question = section.title

        # Find options (A) B) C) D) or a) b) c) d))
        option_pattern = r"([A-Da-d])\)\s*(.+?)(?=[A-Da-d]\)|$)"
        matches = re.findall(option_pattern, content, re.DOTALL)

        if len(matches) < 2:
            return None

        options = [m[1].strip() for m in matches]
        correct_idx = 0

        # Find correct answer (marked with *)
        for i, (_, opt) in enumerate(matches):
            if "*" in opt or opt.strip().endswith("*"):
                correct_idx = i
                options[i] = opt.replace("*", "").strip()
                break

        return ImportedAtom(
            front=question,
            back=options[correct_idx],
            atom_type="mcq",
            source_file=section.source_file,
            source_section=section.title,
            options=options,
            correct_answer=options[correct_idx],
        )

    def _detect_type(self, front: str, back: str) -> str:
        """Detect atom type from content."""
        combined = f"{front} {back}".lower()

        # Cloze
        if "{{" in front:
            return "cloze"

        # True/False
        if back.lower() in ("true", "false", "t", "f", "yes", "no"):
            return "true_false"

        # Numeric (contains numbers as answer)
        if re.match(r"^\d+\.?\d*$", back.strip()):
            return "numeric"

        # Parsons (sequence indicators)
        if " -> " in back or re.match(r"^\d+\.", back):
            return "parsons"

        # Default to flashcard
        return "flashcard"

    def _looks_like_question(self, text: str) -> bool:
        """Check if text looks like a question."""
        text = text.strip()
        return (
            text.endswith("?")
            or text.lower().startswith(("what", "how", "why", "when", "where", "which"))
            or text.lower().startswith(("explain", "describe", "define", "list"))
        )

    def _insert_atoms(self, atoms: list[ImportedAtom]) -> tuple[int, int]:
        """Insert atoms into database, returning (inserted, duplicates)."""
        inserted = 0
        duplicates = 0

        with engine.begin() as conn:
            for atom in atoms:
                # Check for duplicate (same front text)
                existing = conn.execute(
                    text("SELECT id FROM learning_atoms WHERE front = :front"),
                    {"front": atom.front},
                ).fetchone()

                if existing:
                    duplicates += 1
                    continue

                # Generate card_id
                card_id = f"local_{uuid.uuid4().hex[:8]}"

                # Insert atom
                conn.execute(
                    text("""
                        INSERT INTO learning_atoms
                        (card_id, front, back, atom_type, source_fact_basis, created_at)
                        VALUES (:card_id, :front, :back, :atom_type, :source, :created_at)
                    """),
                    {
                        "card_id": card_id,
                        "front": atom.front,
                        "back": atom.back,
                        "atom_type": atom.atom_type,
                        "source": f"{atom.source_file}:{atom.source_section}"
                        if atom.source_section
                        else atom.source_file,
                        "created_at": datetime.utcnow(),
                    },
                )
                inserted += 1

        return inserted, duplicates


def preview_import(path: Path | str) -> list[ImportedAtom]:
    """Preview what would be imported from a file (dry run)."""
    importer = ContentImporter(dry_run=True)
    content = importer.parser.parse_file(path)

    atoms = []
    raw_atoms = importer._extract_qa_pairs(content.raw_text, content.source_path)
    atoms.extend(raw_atoms)

    for section in content.sections:
        section_atoms = importer._extract_from_section(section)
        atoms.extend(section_atoms)

    return atoms
