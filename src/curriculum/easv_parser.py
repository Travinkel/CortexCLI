"""
EASV Curriculum Parser.

Parses course files (SDE2.txt, PROGII.txt, etc.) and generates learning atoms.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from loguru import logger

from .models import Course, Week, LearningObjective, GeneratedAtom


class EASVParser:
    """Parser for EASV curriculum files."""

    # Patterns for extracting structure
    WEEK_PATTERN = re.compile(
        r"^W?(\d+)[\s\-:]+(.+?)(?:\s+([KSC]\d(?:,\s*[KSC]\d)*))?$",
        re.MULTILINE | re.IGNORECASE,
    )
    LEARNING_OBJ_PATTERN = re.compile(r"([KSC]\d)", re.IGNORECASE)
    TOPIC_PATTERN = re.compile(r"^#+\s*(.+)$", re.MULTILINE)
    BEFORE_CLASS_PATTERN = re.compile(r"Before\s+Class(.+?)(?=During\s+Class|Workshop|$)", re.DOTALL | re.IGNORECASE)
    DURING_CLASS_PATTERN = re.compile(r"During\s+Class(.+?)(?=Workshop|Before\s+Class|$)", re.DOTALL | re.IGNORECASE)
    WORKSHOP_PATTERN = re.compile(r"Workshop(.+?)(?=Before\s+Class|During\s+Class|$)", re.DOTALL | re.IGNORECASE)

    def __init__(self):
        self.courses: list[Course] = []

    def parse_file(self, file_path: Path | str) -> Course:
        """Parse a curriculum file and return a Course object."""
        file_path = Path(file_path)
        content = file_path.read_text(encoding="utf-8", errors="replace")

        # Detect course from filename
        course_code = self._detect_course_code(file_path.stem)
        course_name = self._course_code_to_name(course_code)

        logger.info(f"Parsing course: {course_code} from {file_path.name}")

        course = Course(
            code=course_code,
            name=course_name,
            raw_content=content,
        )

        # Parse weeks from content
        course.weeks = self._parse_weeks(content, course_code)

        self.courses.append(course)
        return course

    def _detect_course_code(self, filename: str) -> str:
        """Detect course code from filename."""
        filename = filename.upper().replace(".TXT", "").replace("_", ".")

        if "SDE2" in filename:
            return "SDE2"
        elif "PROGII" in filename or "PROG" in filename:
            return "PROGII"
        elif "SECURITY" in filename or "CDS.SEC" in filename:
            return "CDS.Security"
        elif "NETWORK" in filename or "CDS.NET" in filename:
            return "CDS.Networking"
        elif "EXAM" in filename:
            return "EXAM"
        elif "TESTING" in filename:
            return "SDE2.Testing"
        else:
            return filename[:20]

    def _course_code_to_name(self, code: str) -> str:
        """Map course code to full name."""
        names = {
            "SDE2": "Systems Development II",
            "PROGII": "Programming II",
            "CDS.Security": "CDS Security",
            "CDS.Networking": "CDS Networking",
            "EXAM": "Exam Information",
            "SDE2.Testing": "Systems Development II - Testing",
        }
        return names.get(code, code)

    def _parse_weeks(self, content: str, course_code: str) -> list[Week]:
        """Parse week structure from content."""
        weeks = []

        # Split content by week headers
        # Look for patterns like "W35", "Week 35", "35 -", etc.
        week_sections = re.split(
            r"(?=W\d+[\s\-:]|Week\s+\d+|^\d+\s+[\-:])",
            content,
            flags=re.MULTILINE | re.IGNORECASE,
        )

        for section in week_sections:
            if not section.strip():
                continue

            # Try to extract week number
            week_match = re.match(r"W?(\d+)[\s\-:]*(.+)?", section.strip(), re.IGNORECASE)
            if not week_match:
                continue

            week_num = int(week_match.group(1))
            rest = section[week_match.end():]

            # Extract topic from first line or header
            topic = self._extract_topic(section)
            if not topic:
                topic = f"Week {week_num}"

            # Extract learning objectives
            objectives = self._extract_learning_objectives(section)

            week = Week(
                number=week_num,
                topic=topic,
                learning_objectives=objectives,
                content=section,
            )

            # Extract structured content
            if before_match := self.BEFORE_CLASS_PATTERN.search(section):
                week.before_class = before_match.group(1).strip()
            if during_match := self.DURING_CLASS_PATTERN.search(section):
                week.during_class = during_match.group(1).strip()
            if workshop_match := self.WORKSHOP_PATTERN.search(section):
                week.workshop = workshop_match.group(1).strip()

            weeks.append(week)

        logger.info(f"Parsed {len(weeks)} weeks from {course_code}")
        return weeks

    def _extract_topic(self, section: str) -> str:
        """Extract main topic from section."""
        # Try to find a header
        lines = section.strip().split("\n")
        for line in lines[:5]:
            line = line.strip()
            # Skip week number lines
            if re.match(r"^W?\d+[\s\-:]", line, re.IGNORECASE):
                continue
            # Skip empty or short lines
            if len(line) < 3:
                continue
            # Remove markdown headers
            line = re.sub(r"^#+\s*", "", line)
            if line and not line.startswith("http"):
                return line[:100]
        return ""

    def _extract_learning_objectives(self, section: str) -> list[LearningObjective]:
        """Extract learning objectives (K1, S3, etc.) from section."""
        objectives = []
        matches = self.LEARNING_OBJ_PATTERN.findall(section)
        seen = set()
        for code in matches:
            code = code.upper()
            if code not in seen:
                seen.add(code)
                objectives.append(LearningObjective.from_code(code))
        return objectives

    def generate_atoms(self, course: Course | None = None) -> Iterator[GeneratedAtom]:
        """Generate learning atoms from parsed courses."""
        courses_to_process = [course] if course else self.courses

        for c in courses_to_process:
            yield from self._generate_course_atoms(c)

    def _generate_course_atoms(self, course: Course) -> Iterator[GeneratedAtom]:
        """Generate atoms for a single course."""
        logger.info(f"Generating atoms for {course.code}")

        for week in course.weeks:
            yield from self._generate_week_atoms(course, week)

    def _generate_week_atoms(self, course: Course, week: Week) -> Iterator[GeneratedAtom]:
        """Generate atoms for a single week."""
        obj_codes = [o.code for o in week.learning_objectives]

        # Generate topic overview atom
        if week.topic and week.topic != f"Week {week.number}":
            yield GeneratedAtom(
                front=f"What is the main topic of {course.code} Week {week.number}?",
                back=week.topic,
                atom_type="flashcard",
                concept=week.topic,
                course_code=course.code,
                week_number=week.number,
                learning_objectives=obj_codes,
            )

        # Extract concepts from content and generate atoms
        yield from self._extract_concepts_from_content(course, week)

    def _extract_concepts_from_content(self, course: Course, week: Week) -> Iterator[GeneratedAtom]:
        """Extract concepts from week content and generate atoms."""
        content = week.content
        obj_codes = [o.code for o in week.learning_objectives]

        # Pattern-based extraction for common structures
        concepts = self._extract_concept_patterns(content)

        for concept_name, concept_desc in concepts:
            if concept_name and concept_desc:
                yield GeneratedAtom(
                    front=f"What is {concept_name}?",
                    back=concept_desc,
                    atom_type="flashcard",
                    concept=concept_name,
                    course_code=course.code,
                    week_number=week.number,
                    learning_objectives=obj_codes,
                )

        # Generate atoms from bullet points
        yield from self._extract_bullet_point_atoms(course, week)

    def _extract_concept_patterns(self, content: str) -> list[tuple[str, str]]:
        """Extract concept patterns from content."""
        concepts = []

        # Look for definition patterns
        # "X: description" or "X - description"
        def_pattern = re.compile(
            r"(?:^|\n)\s*[-•]\s*([A-Z][a-zA-Z\s]+?)[:–-]\s*(.+?)(?=\n|$)",
            re.MULTILINE,
        )
        for match in def_pattern.finditer(content):
            name = match.group(1).strip()
            desc = match.group(2).strip()
            if 3 < len(name) < 50 and len(desc) > 10:
                concepts.append((name, desc))

        return concepts[:20]  # Limit to prevent explosion

    def _extract_bullet_point_atoms(self, course: Course, week: Week) -> Iterator[GeneratedAtom]:
        """Extract atoms from bullet points."""
        content = week.content
        obj_codes = [o.code for o in week.learning_objectives]

        # Look for "How to" patterns
        how_to_pattern = re.compile(
            r"(?:How to|Learn how to|Practice)\s+(.+?)(?=\n|$)",
            re.IGNORECASE,
        )
        for match in how_to_pattern.finditer(content):
            skill = match.group(1).strip().rstrip(".")
            if 10 < len(skill) < 100:
                yield GeneratedAtom(
                    front=f"How do you {skill.lower()}?",
                    back=f"See {course.code} Week {week.number} for detailed instructions.",
                    atom_type="flashcard",
                    concept=skill,
                    course_code=course.code,
                    week_number=week.number,
                    learning_objectives=obj_codes,
                )


def parse_curriculum_file(file_path: Path | str) -> tuple[Course, list[GeneratedAtom]]:
    """
    Parse a curriculum file and return course + generated atoms.

    Convenience function for single-file parsing.
    """
    parser = EASVParser()
    course = parser.parse_file(file_path)
    atoms = list(parser.generate_atoms(course))
    return course, atoms


# Domain-specific atom generators for each course type


def generate_sde2_atoms(content: str, week: Week) -> Iterator[GeneratedAtom]:
    """Generate atoms specific to Systems Development II (Git, CI/CD, etc.)."""
    obj_codes = [o.code for o in week.learning_objectives]

    # Git-specific patterns
    git_commands = re.findall(r"`(git\s+\w+(?:\s+[\w\-]+)?)`", content)
    for cmd in set(git_commands):
        yield GeneratedAtom(
            front=f"What does the command `{cmd}` do?",
            back=f"Explain the {cmd} command in Git.",
            atom_type="flashcard",
            concept="Git Commands",
            course_code="SDE2",
            week_number=week.number,
            learning_objectives=obj_codes,
        )

    # CI/CD concepts
    cicd_terms = ["pipeline", "workflow", "action", "job", "step", "runner", "artifact"]
    for term in cicd_terms:
        if term.lower() in content.lower():
            yield GeneratedAtom(
                front=f"What is a {term} in CI/CD?",
                back=f"A {term} is a component of continuous integration/deployment.",
                atom_type="flashcard",
                concept=f"CI/CD {term.title()}",
                course_code="SDE2",
                week_number=week.number,
                learning_objectives=obj_codes,
            )


def generate_progii_atoms(content: str, week: Week) -> Iterator[GeneratedAtom]:
    """Generate atoms specific to Programming II (React, C# Web API, etc.)."""
    obj_codes = [o.code for o in week.learning_objectives]

    # React concepts
    react_terms = ["component", "props", "state", "hook", "useEffect", "useState", "routing"]
    for term in react_terms:
        if term.lower() in content.lower():
            yield GeneratedAtom(
                front=f"What is a {term} in React?",
                back=f"Explain {term} in the context of React development.",
                atom_type="flashcard",
                concept=f"React {term.title()}",
                course_code="PROGII",
                week_number=week.number,
                learning_objectives=obj_codes,
            )

    # C# Web API concepts
    csharp_terms = ["controller", "dependency injection", "entity framework", "DTO", "validation"]
    for term in csharp_terms:
        if term.lower() in content.lower():
            yield GeneratedAtom(
                front=f"What is {term} in ASP.NET Core?",
                back=f"Explain {term} in the context of C# Web API development.",
                atom_type="flashcard",
                concept=f"ASP.NET {term.title()}",
                course_code="PROGII",
                week_number=week.number,
                learning_objectives=obj_codes,
            )
