"""Data models for curriculum parsing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class LearningObjective:
    """Learning objective from curriculum (K1, S3, C3, etc.)."""

    code: str  # K1, S1, S2, S3, S4, C1, C2, C3
    category: Literal["knowledge", "skills", "competency"]
    description: str = ""

    @classmethod
    def from_code(cls, code: str) -> LearningObjective:
        """Create from code like K1, S3, C2."""
        code = code.strip().upper()
        if code.startswith("K"):
            return cls(code=code, category="knowledge")
        elif code.startswith("S"):
            return cls(code=code, category="skills")
        elif code.startswith("C"):
            return cls(code=code, category="competency")
        else:
            return cls(code=code, category="knowledge")


@dataclass
class Week:
    """A week in the curriculum."""

    number: int
    topic: str
    learning_objectives: list[LearningObjective] = field(default_factory=list)
    content: str = ""  # Raw content for that week
    before_class: str = ""
    during_class: str = ""
    workshop: str = ""
    resources: list[str] = field(default_factory=list)


@dataclass
class Course:
    """A course in the curriculum."""

    code: str  # SDE2, PROGII, CDS.Networking
    name: str
    description: str = ""
    weeks: list[Week] = field(default_factory=list)
    raw_content: str = ""


@dataclass
class GeneratedAtom:
    """An atom generated from curriculum content."""

    front: str
    back: str
    atom_type: Literal["flashcard", "cloze", "mcq", "true_false"] = "flashcard"
    concept: str = ""
    course_code: str = ""
    week_number: int | None = None
    learning_objectives: list[str] = field(default_factory=list)
    source_line: int | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "front": self.front,
            "back": self.back,
            "atom_type": self.atom_type,
            "concept": self.concept,
            "course_code": self.course_code,
            "week_number": self.week_number,
            "learning_objectives": self.learning_objectives,
        }
