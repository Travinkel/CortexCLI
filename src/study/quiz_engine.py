"""
Quiz Engine for In-App Learning Atoms.

.. deprecated::
    This module is deprecated in favor of the modular atom handlers in
    ``src/cortex/atoms/``. New code should use the handler registry pattern:

        from src.cortex.atoms import get_handler
        handler = get_handler("mcq")
        handler.present(atom)

    This file is retained for backward compatibility with existing code
    that imports QuizEngine or AtomType. It will be removed in a future version.

Handles presentation and scoring of:
- MCQ (Multiple Choice Questions)
- True/False
- Matching (term-definition pairs)
- Parsons (procedure ordering)

These atom types are presented INSIDE NLS, not sent to Anki.
Only flashcard and cloze go to Anki for FSRS scheduling.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from loguru import logger
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from sqlalchemy import text

from src.db.database import session_scope

console = Console()


class AtomType(str, Enum):
    """Atom types handled by quiz engine."""

    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    MATCHING = "matching"
    PARSONS = "parsons"
    NUMERIC = "numeric"


@dataclass
class QuizAtom:
    """A single quiz atom to present."""

    id: str
    card_id: str
    atom_type: AtomType
    front: str  # Question
    back: str  # Answer/options JSON
    concept_name: str
    section_id: str | None = None
    difficulty: float = 0.5
    last_response: str | None = None
    correct_streak: int = 0

    # Parsed content
    options: list[str] = field(default_factory=list)
    correct_answer: str = ""
    explanation: str = ""  # Explanation for T/F answers
    pairs: list[tuple[str, str]] = field(default_factory=list)  # For matching
    steps: list[str] = field(default_factory=list)  # For Parsons
    # Numeric question fields
    numeric_answer: float = 0.0
    numeric_tolerance: float = 0.0
    numeric_unit: str = ""
    numeric_steps: list[str] = field(default_factory=list)


@dataclass
class QuizResult:
    """Result of answering a quiz atom."""

    atom_id: str
    is_correct: bool
    response_time_ms: int
    user_answer: str
    correct_answer: str
    feedback: str


class QuizEngine:
    """
    Engine for presenting and scoring quiz atoms.

    Handles MCQ, True/False, Matching, and Parsons problems
    directly in the CLI interface.
    """

    def __init__(self):
        self.current_session_correct = 0
        self.current_session_total = 0
        self.session_start = datetime.now()

    def fetch_atoms(
        self,
        atom_types: list[AtomType],
        section_id: str | None = None,
        concept_id: str | None = None,
        limit: int = 10,
        difficulty_range: tuple[float, float] = (0.0, 1.0),
        prioritize_weak: bool = True,
    ) -> list[QuizAtom]:
        """
        Fetch atoms for quiz from database.

        Args:
            atom_types: Types to include (mcq, true_false, matching, parsons)
            section_id: Filter by CCNA section (e.g., "11.5.1")
            concept_id: Filter by concept UUID
            limit: Max atoms to fetch
            difficulty_range: (min, max) difficulty
            prioritize_weak: Sort by lowest mastery first

        Returns:
            List of QuizAtom ready for presentation
        """
        type_list = [t.value for t in atom_types]

        with session_scope() as session:
            # Build query
            query = """
                SELECT
                    ca.id,
                    ca.card_id,
                    ca.atom_type,
                    ca.front,
                    ca.back,
                    cc.name as concept_name,
                    ca.ccna_section_id,
                    COALESCE(ca.anki_difficulty, 0.5) as difficulty,
                    ca.anki_review_count,
                    ca.anki_lapses
                FROM learning_atoms ca
                LEFT JOIN concepts cc ON ca.concept_id = cc.id
                WHERE ca.atom_type = ANY(:types)
                  AND ca.front IS NOT NULL
                  AND ca.front != ''
            """
            params = {"types": type_list}

            if section_id:
                query += " AND ca.ccna_section_id LIKE :section"
                params["section"] = f"{section_id}%"

            if concept_id:
                query += " AND ca.concept_id = :concept_id"
                params["concept_id"] = concept_id

            # Order by weakness if prioritizing
            if prioritize_weak:
                query += """
                    ORDER BY
                        COALESCE(ca.anki_lapses, 0) DESC,
                        COALESCE(ca.anki_review_count, 0) ASC,
                        RANDOM()
                """
            else:
                query += " ORDER BY RANDOM()"

            query += " LIMIT :limit"
            params["limit"] = limit

            result = session.execute(text(query), params)

            atoms = []
            for row in result:
                atom = QuizAtom(
                    id=str(row.id),
                    card_id=row.card_id,
                    atom_type=AtomType(row.atom_type),
                    front=row.front,
                    back=row.back or "",
                    concept_name=row.concept_name or "Unknown",
                    section_id=row.ccna_section_id,
                    difficulty=row.difficulty or 0.5,
                )

                # Parse atom content based on type
                self._parse_atom_content(atom)
                atoms.append(atom)

            return atoms

    def _parse_atom_content(self, atom: QuizAtom) -> None:
        """Parse the back field based on atom type."""

        if atom.atom_type == AtomType.MCQ:
            self._parse_mcq(atom)
        elif atom.atom_type == AtomType.TRUE_FALSE:
            self._parse_true_false(atom)
        elif atom.atom_type == AtomType.MATCHING:
            self._parse_matching(atom)
        elif atom.atom_type == AtomType.PARSONS:
            self._parse_parsons(atom)
        elif atom.atom_type == AtomType.NUMERIC:
            self._parse_numeric(atom)

    def _parse_mcq(self, atom: QuizAtom) -> None:
        """Parse MCQ options from back field."""
        back = atom.back

        # Try JSON format first
        try:
            data = json.loads(back)
            if isinstance(data, dict):
                atom.options = data.get("options", [])
                atom.correct_answer = data.get("correct", "")
                return
        except json.JSONDecodeError:
            pass

        # Parse text format: options with asterisk for correct
        # Format: "A) Option1 *B) CorrectOption C) Option3"
        # Or: "* Correct answer\n- Wrong answer\n- Wrong answer"
        lines = back.strip().split("\n")
        options = []
        correct = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for asterisk marker
            is_correct = line.startswith("*") or line.startswith("✓")
            if is_correct:
                line = line[1:].strip()

            # Remove common prefixes
            line = re.sub(r"^[A-D]\)\s*", "", line)
            line = re.sub(r"^[-•]\s*", "", line)

            if line:
                options.append(line)
                if is_correct:
                    correct = line

        # If no asterisk found, assume first line is correct
        if not correct and options:
            correct = options[0]

        atom.options = options
        atom.correct_answer = correct

    def _parse_true_false(self, atom: QuizAtom) -> None:
        """Parse True/False answer."""
        # First try JSON format: {"answer": true/false, "explanation": "..."}
        try:
            data = json.loads(atom.back)
            if isinstance(data, dict) and "answer" in data:
                answer = data["answer"]
                if isinstance(answer, bool):
                    atom.correct_answer = "True" if answer else "False"
                elif isinstance(answer, str):
                    atom.correct_answer = (
                        "True" if answer.lower() in ("true", "t", "yes") else "False"
                    )
                else:
                    atom.correct_answer = "True" if answer else "False"
                # Store explanation for feedback
                atom.explanation = data.get("explanation", "")
                atom.options = ["True", "False"]
                return
        except json.JSONDecodeError:
            pass

        # Fallback to plain text parsing
        back = atom.back.strip().lower()

        # Common patterns
        if back in ("true", "t", "yes", "correct", "✓"):
            atom.correct_answer = "True"
        elif back in ("false", "f", "no", "incorrect", "✗"):
            atom.correct_answer = "False"
        else:
            # Try to parse explanation format: "True. Because..."
            if back.startswith("true"):
                atom.correct_answer = "True"
            elif back.startswith("false"):
                atom.correct_answer = "False"
            else:
                atom.correct_answer = "Unknown"  # Better fallback than truncated JSON

        atom.options = ["True", "False"]

    def _parse_matching(self, atom: QuizAtom) -> None:
        """Parse matching pairs from back field."""
        try:
            data = json.loads(atom.back)
            if isinstance(data, list):
                atom.pairs = [(p.get("term", ""), p.get("definition", "")) for p in data]
            elif isinstance(data, dict):
                atom.pairs = list(data.items())
            return
        except json.JSONDecodeError:
            pass

        # Parse text format: "Term1 - Definition1\nTerm2 - Definition2"
        pairs = []
        for line in atom.back.strip().split("\n"):
            if " - " in line:
                parts = line.split(" - ", 1)
                pairs.append((parts[0].strip(), parts[1].strip()))
            elif ": " in line:
                parts = line.split(": ", 1)
                pairs.append((parts[0].strip(), parts[1].strip()))

        atom.pairs = pairs

    def _parse_parsons(self, atom: QuizAtom) -> None:
        """Parse Parsons problem steps."""
        try:
            data = json.loads(atom.back)
            if isinstance(data, list):
                atom.steps = data
                return
        except json.JSONDecodeError:
            pass

        # Parse numbered steps
        steps = []
        for line in atom.back.strip().split("\n"):
            line = line.strip()
            # Remove numbering
            line = re.sub(r"^\d+[\.\)]\s*", "", line)
            if line:
                steps.append(line)

        atom.steps = steps

    def _parse_numeric(self, atom: QuizAtom) -> None:
        """Parse numeric answer question from back field."""
        try:
            data = json.loads(atom.back)
            if isinstance(data, dict):
                atom.numeric_answer = float(data.get("answer", 0))
                atom.numeric_tolerance = float(data.get("tolerance", 0.01))
                atom.numeric_unit = data.get("unit", "")
                atom.numeric_steps = data.get("steps", [])
                atom.explanation = data.get("explanation", "")
                return
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: try to parse a simple numeric value from back
        try:
            # Remove common units and parse number
            cleaned = re.sub(r"[^\d.\-]", "", atom.back.split()[0] if atom.back else "0")
            atom.numeric_answer = float(cleaned) if cleaned else 0.0
            atom.numeric_tolerance = 0.01  # 1% tolerance by default
        except (ValueError, IndexError):
            atom.numeric_answer = 0.0
            atom.numeric_tolerance = 0.0

    # ========================================
    # PRESENTATION METHODS
    # ========================================

    def present_atom(self, atom: QuizAtom) -> QuizResult:
        """
        Present a single atom and get user response.

        Returns:
            QuizResult with correctness and feedback
        """
        start_time = datetime.now()

        # Show header
        console.print()
        console.print(f"[dim]Concept: {atom.concept_name}[/dim]")
        if atom.section_id:
            console.print(f"[dim]Section: {atom.section_id}[/dim]")
        console.print()

        # Dispatch to type-specific presenter
        if atom.atom_type == AtomType.MCQ:
            result = self._present_mcq(atom)
        elif atom.atom_type == AtomType.TRUE_FALSE:
            result = self._present_true_false(atom)
        elif atom.atom_type == AtomType.NUMERIC:
            result = self._present_numeric(atom)
        elif atom.atom_type == AtomType.MATCHING:
            result = self._present_matching(atom)
        elif atom.atom_type == AtomType.PARSONS:
            result = self._present_parsons(atom)
        else:
            rprint(f"[red]Unknown atom type: {atom.atom_type}[/red]")
            return QuizResult(
                atom_id=atom.id,
                is_correct=False,
                response_time_ms=0,
                user_answer="",
                correct_answer="",
                feedback="Unknown atom type",
            )

        # Calculate response time
        elapsed = datetime.now() - start_time
        result.response_time_ms = int(elapsed.total_seconds() * 1000)

        # Update session stats
        self.current_session_total += 1
        if result.is_correct:
            self.current_session_correct += 1

        # Show result
        self._show_result(result)

        # Record to database
        self._record_response(atom, result)

        return result

    def _present_mcq(self, atom: QuizAtom) -> QuizResult:
        """Present MCQ and get response."""
        # Show question
        panel = Panel(
            atom.front,
            title="[bold cyan]Multiple Choice[/bold cyan]",
            border_style="cyan",
        )
        console.print(panel)

        # Show options
        if not atom.options:
            rprint("[yellow]No options found for this question[/yellow]")
            return QuizResult(
                atom_id=atom.id,
                is_correct=False,
                response_time_ms=0,
                user_answer="",
                correct_answer=atom.correct_answer,
                feedback="Malformed question",
            )

        # Shuffle options but track correct
        options = atom.options.copy()
        random.shuffle(options)

        console.print()
        for i, opt in enumerate(options, 1):
            console.print(f"  [bold]{i}[/bold]) {opt}")

        console.print()

        # Get response
        try:
            choice = IntPrompt.ask(
                "[bold]Your answer[/bold]",
                choices=[str(i) for i in range(1, len(options) + 1)],
            )
            user_answer = options[choice - 1]
        except (ValueError, IndexError, KeyboardInterrupt):
            user_answer = ""

        is_correct = user_answer == atom.correct_answer

        return QuizResult(
            atom_id=atom.id,
            is_correct=is_correct,
            response_time_ms=0,
            user_answer=user_answer,
            correct_answer=atom.correct_answer,
            feedback="Correct!" if is_correct else f"The correct answer was: {atom.correct_answer}",
        )

    def _present_true_false(self, atom: QuizAtom) -> QuizResult:
        """Present True/False question."""
        panel = Panel(
            atom.front,
            title="[bold yellow]True or False[/bold yellow]",
            border_style="yellow",
        )
        console.print(panel)
        console.print()

        # Get response
        response = Prompt.ask(
            "[bold]True or False?[/bold]",
            choices=["t", "f", "true", "false"],
            default="t",
        ).lower()

        user_answer = "True" if response in ("t", "true") else "False"
        is_correct = user_answer == atom.correct_answer

        # Build feedback with explanation if available
        if is_correct:
            feedback = "Correct!"
        else:
            feedback = f"The statement is {atom.correct_answer}."
            if atom.explanation:
                feedback += f" {atom.explanation}"

        return QuizResult(
            atom_id=atom.id,
            is_correct=is_correct,
            response_time_ms=0,
            user_answer=user_answer,
            correct_answer=atom.correct_answer,
            feedback=feedback,
        )

    def _present_numeric(self, atom: QuizAtom) -> QuizResult:
        """Present numeric calculation question."""
        panel = Panel(
            atom.front,
            title="[bold blue]Calculation[/bold blue]",
            border_style="blue",
        )
        console.print(panel)

        # Show steps/hints if available
        if atom.numeric_steps:
            console.print("\n[dim]Calculation steps to consider:[/dim]")
            for i, step in enumerate(atom.numeric_steps, 1):
                console.print(f"  [dim]{i}. {step}[/dim]")

        unit_hint = f" ({atom.numeric_unit})" if atom.numeric_unit else ""
        console.print()

        try:
            response = Prompt.ask(f"[bold]Your answer{unit_hint}[/bold]")

            # Parse numeric response (remove units if present)
            cleaned = re.sub(r"[^\d.\-]", "", response)
            user_value = float(cleaned) if cleaned else 0.0

            # Check within tolerance
            if atom.numeric_tolerance > 0:
                # Percentage tolerance
                tolerance_amt = abs(atom.numeric_answer * atom.numeric_tolerance)
                is_correct = abs(user_value - atom.numeric_answer) <= tolerance_amt
            else:
                # Exact match (with small float tolerance)
                is_correct = abs(user_value - atom.numeric_answer) < 0.001

            user_answer = str(user_value)

        except (ValueError, KeyboardInterrupt):
            is_correct = False
            user_answer = response if "response" in dir() else ""
            user_value = 0.0

        # Build feedback
        unit_str = f" {atom.numeric_unit}" if atom.numeric_unit else ""
        if is_correct:
            feedback = "Correct!"
        else:
            feedback = f"The correct answer is {atom.numeric_answer}{unit_str}"
            if atom.explanation:
                feedback += f"\n{atom.explanation}"

        return QuizResult(
            atom_id=atom.id,
            is_correct=is_correct,
            response_time_ms=0,
            user_answer=user_answer,
            correct_answer=f"{atom.numeric_answer}{unit_str}",
            feedback=feedback,
        )

    def _present_matching(self, atom: QuizAtom) -> QuizResult:
        """Present matching exercise."""
        panel = Panel(
            atom.front,
            title="[bold magenta]Matching[/bold magenta]",
            border_style="magenta",
        )
        console.print(panel)

        if not atom.pairs:
            rprint("[yellow]No matching pairs found[/yellow]")
            return QuizResult(
                atom_id=atom.id,
                is_correct=False,
                response_time_ms=0,
                user_answer="",
                correct_answer="",
                feedback="Malformed question",
            )

        # Show terms on left, shuffled definitions on right
        terms = [p[0] for p in atom.pairs]
        definitions = [p[1] for p in atom.pairs]
        shuffled_defs = definitions.copy()
        random.shuffle(shuffled_defs)

        console.print("\n[bold]Terms:[/bold]")
        for i, term in enumerate(terms, 1):
            console.print(f"  {i}. {term}")

        console.print("\n[bold]Definitions:[/bold]")
        for i, defn in enumerate(shuffled_defs, 1):
            console.print(f"  {chr(64 + i)}. {defn}")

        console.print("\n[dim]Match each term number to a definition letter (e.g., 1A 2B 3C)[/dim]")

        try:
            response = Prompt.ask("[bold]Your matches[/bold]")

            # Parse response like "1A 2B 3C"
            user_matches = {}
            for part in response.upper().split():
                if len(part) >= 2:
                    num = int(part[0]) - 1
                    letter = ord(part[1]) - ord("A")
                    if 0 <= num < len(terms) and 0 <= letter < len(shuffled_defs):
                        user_matches[num] = shuffled_defs[letter]

            # Check correctness
            correct_count = 0
            for i, (term, defn) in enumerate(atom.pairs):
                if user_matches.get(i) == defn:
                    correct_count += 1

            is_correct = correct_count == len(atom.pairs)

        except (ValueError, KeyboardInterrupt):
            is_correct = False
            correct_count = 0

        correct_matches = ", ".join(f"{p[0]}→{p[1]}" for p in atom.pairs)

        return QuizResult(
            atom_id=atom.id,
            is_correct=is_correct,
            response_time_ms=0,
            user_answer=response if "response" in dir() else "",
            correct_answer=correct_matches,
            feedback=f"Got {correct_count}/{len(atom.pairs)} correct"
            if not is_correct
            else "Perfect matching!",
        )

    def _present_parsons(self, atom: QuizAtom) -> QuizResult:
        """Present Parsons ordering problem."""
        panel = Panel(
            atom.front,
            title="[bold green]Order the Steps[/bold green]",
            border_style="green",
        )
        console.print(panel)

        if not atom.steps:
            rprint("[yellow]No steps found[/yellow]")
            return QuizResult(
                atom_id=atom.id,
                is_correct=False,
                response_time_ms=0,
                user_answer="",
                correct_answer="",
                feedback="Malformed question",
            )

        # Shuffle steps
        correct_order = atom.steps.copy()
        shuffled = atom.steps.copy()
        random.shuffle(shuffled)

        console.print("\n[bold]Put these steps in the correct order:[/bold]")
        for i, step in enumerate(shuffled, 1):
            console.print(f"  {i}. {step}")

        console.print("\n[dim]Enter the correct order as numbers (e.g., 3 1 2 4)[/dim]")

        try:
            response = Prompt.ask("[bold]Correct order[/bold]")

            # Parse order
            order_nums = [int(x) - 1 for x in response.split()]
            user_order = [shuffled[i] for i in order_nums if 0 <= i < len(shuffled)]

            is_correct = user_order == correct_order

        except (ValueError, IndexError, KeyboardInterrupt):
            is_correct = False
            user_order = []

        return QuizResult(
            atom_id=atom.id,
            is_correct=is_correct,
            response_time_ms=0,
            user_answer=" ".join(str(i) for i in order_nums) if "order_nums" in dir() else "",
            correct_answer=" → ".join(correct_order),
            feedback="Perfect order!"
            if is_correct
            else "Correct order: "
            + " → ".join(f"{i + 1}. {s}" for i, s in enumerate(correct_order)),
        )

    def _show_result(self, result: QuizResult) -> None:
        """Display result feedback."""
        console.print()
        if result.is_correct:
            console.print("[bold green]✓ CORRECT![/bold green]")
        else:
            console.print("[bold red]✗ INCORRECT[/bold red]")
            console.print(f"[dim]{result.feedback}[/dim]")

        # Show session progress
        accuracy = (
            (self.current_session_correct / self.current_session_total * 100)
            if self.current_session_total > 0
            else 0
        )
        console.print(
            f"\n[dim]Session: {self.current_session_correct}/{self.current_session_total} ({accuracy:.0f}%)[/dim]"
        )

    def _record_response(self, atom: QuizAtom, result: QuizResult) -> None:
        """Record response to database for mastery tracking."""
        try:
            with session_scope() as session:
                session.execute(
                    text("""
                    INSERT INTO atom_responses (
                        atom_id, user_id, is_correct, response_time_ms,
                        user_answer, responded_at
                    ) VALUES (
                        :atom_id, 'default', :is_correct, :response_time,
                        :user_answer, NOW()
                    )
                """),
                    {
                        "atom_id": atom.id,
                        "is_correct": result.is_correct,
                        "response_time": result.response_time_ms,
                        "user_answer": result.user_answer[:500] if result.user_answer else "",
                    },
                )
                session.commit()
        except Exception as e:
            logger.debug(f"Could not record response: {e}")

    def get_session_summary(self) -> dict:
        """Get summary of current quiz session."""
        elapsed = datetime.now() - self.session_start
        accuracy = (
            (self.current_session_correct / self.current_session_total * 100)
            if self.current_session_total > 0
            else 0
        )

        return {
            "total": self.current_session_total,
            "correct": self.current_session_correct,
            "accuracy": round(accuracy, 1),
            "duration_minutes": int(elapsed.total_seconds() / 60),
        }

    def reset_session(self) -> None:
        """Reset session counters."""
        self.current_session_correct = 0
        self.current_session_total = 0
        self.session_start = datetime.now()
