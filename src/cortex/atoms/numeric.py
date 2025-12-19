"""
Numeric atom handler.

Handles numeric answers including:
- Decimal numbers
- Binary (0b prefix or raw binary string)
- Hexadecimal (0x prefix or h suffix)
- IP addresses (dotted decimal)
- CIDR notation (/24)

Supports tolerance for approximate answers.
"""

from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.style import Style
from rich.text import Text

from src.delivery.cortex_visuals import (
    CORTEX_THEME,
    STYLES,
    cortex_result_panel,
    get_asi_prompt,
)
from . import AtomType, register
from .base import AnswerResult, is_dont_know


@register(AtomType.NUMERIC)
class NumericHandler:
    """Handler for numeric atoms."""

    def validate(self, atom: dict) -> bool:
        """Check if atom has required numeric fields."""
        return bool(atom.get("front") and atom.get("back"))

    def present(self, atom: dict, console: Console) -> None:
        """Display the numeric question."""
        front = atom.get("front", "No question")

        # Check if we should show a formula hint
        hint = self._get_formula_hint(atom)

        content = front
        if hint:
            content += f"\n\n[dim]Hint: {hint}[/dim]"

        panel = Panel(
            content,
            title="[bold cyan]CALCULATE[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Get numeric input from user. Press 'h' for hints, '?' for I don't know."""
        console.print("[dim]'h'=hint, '?'=I don't know, or enter your answer[/dim]")

        hint_count = 0
        while True:
            user_input = Prompt.ask(get_asi_prompt("numeric"))

            # Check for "I don't know"
            if is_dont_know(user_input):
                return {"dont_know": True, "hints_used": hint_count}

            if user_input.lower() == "h":
                hint_count += 1
                hint_text = self.hint(atom, hint_count)
                if hint_text:
                    console.print(f"[yellow]Hint {hint_count}:[/yellow] {hint_text}")
                else:
                    console.print("[dim]No more hints available[/dim]")
                continue

            return {"answer": user_input, "hints_used": hint_count, "dont_know": False}

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check numeric answer with tolerance."""
        # Handle "I don't know"
        if isinstance(answer, dict) and answer.get("dont_know"):
            back = atom.get("back", "")
            steps = atom.get("numeric_steps") or back.split("\n")
            return AnswerResult(
                correct=False,
                feedback="Let's learn this one!",
                user_answer="I don't know",
                correct_answer=back,
                explanation="\n".join(steps) if steps else None,
                dont_know=True,
            )

        # Handle both dict (with hints) and str (direct) input
        if isinstance(answer, dict):
            user_input = str(answer.get("answer", ""))
        else:
            user_input = str(answer)
        user_val = self._normalize(user_input)

        # Get correct answer
        correct_val = atom.get("numeric_answer")
        if correct_val is None:
            back_text = atom.get("back", "")
            # First try direct normalization
            correct_val = self._normalize(back_text)
            # If normalization returned the raw string (not a number), try extracting from explanation
            if isinstance(correct_val, str) and len(correct_val) > 20:
                extracted = self._extract_answer_from_explanation(back_text)
                if extracted:
                    correct_val = self._normalize(extracted)
        elif isinstance(correct_val, str):
            correct_val = self._normalize(correct_val)

        # Check with tolerance
        tolerance = atom.get("numeric_tolerance", 0)
        is_correct = self._compare(user_val, correct_val, tolerance)

        back = atom.get("back", "")
        steps = atom.get("numeric_steps") or back.split("\n")

        return AnswerResult(
            correct=is_correct,
            feedback="Correct!" if is_correct else f"Incorrect. Expected: {back}",
            user_answer=user_input,
            correct_answer=back,
            explanation="\n".join(steps) if not is_correct and steps else None,
        )

    def hint(self, atom: dict, attempt: int) -> str | None:
        """Progressive hints for numeric questions."""
        if attempt == 1:
            # Formula/approach hint
            return self._get_formula_hint(atom)
        elif attempt == 2:
            # Show partial answer
            back = atom.get("back", "")
            if back:
                # Show first digit(s)
                digits = "".join(c for c in back if c.isdigit())
                if len(digits) > 1:
                    return f"The answer starts with: {digits[0]}..."
        elif attempt == 3:
            # Show steps
            steps = atom.get("numeric_steps", [])
            if steps:
                return f"Step 1: {steps[0]}"
        return None

    def _get_formula_hint(self, atom: dict) -> str | None:
        """Get contextual formula hint based on question content."""
        front = atom.get("front", "").lower()

        # Common CCNA formulas
        formulas = {
            "subnet": "Hosts = 2^(32-prefix) - 2",
            "subnetting": "Hosts = 2^(32-prefix) - 2",
            "cidr": "Hosts = 2^(32-prefix) - 2",
            "hosts": "Hosts = 2^n - 2 where n = host bits",
            "network": "Network = IP AND Subnet Mask",
            "broadcast": "Broadcast = Network OR (NOT Subnet Mask)",
            "binary": "Convert each octet: 128 64 32 16 8 4 2 1",
            "hexadecimal": "Hex digits: 0-9, A=10, B=11, ..., F=15",
            "bandwidth": "Bandwidth = Data Size / Time",
            "throughput": "Throughput = Actual Data / Time",
            "latency": "RTT = 2 * One-way delay",
            "wildcard": "Wildcard = 255.255.255.255 - Subnet Mask",
        }

        for keyword, formula in formulas.items():
            if keyword in front:
                return formula

        return None

    def _extract_answer_from_explanation(self, text: str) -> str | None:
        """
        Extract numeric answer from explanation text.

        Looks for patterns like:
        - "= 8193." (final result ending with period)
        - "= 8193" at end or followed by period/space
        - "is 181" / "equals 181" / "equal to 181"
        """
        import re

        # Pattern 1: "= NUMBER." (final answer followed by period) - most reliable
        match = re.search(r'=\s*(\d+(?:\.\d+)?)\s*\.(?:\s|$)', text)
        if match:
            return match.group(1)

        # Pattern 2: All "= NUMBER" matches, take the last one (usually the final answer)
        matches = re.findall(r'=\s*(\d+(?:\.\d+)?)', text)
        if matches:
            return matches[-1]

        # Pattern 3: "is NUMBER" / "equals NUMBER" / "equal to NUMBER" / "is equal to NUMBER"
        # Look for the last occurrence with a period after
        match = re.search(r'(?:is\s+equal\s+to|equal\s+to|equals|is)\s+(?:the\s+)?(?:decimal\s+)?(?:number\s+)?(\d+(?:\.\d+)?)\s*\.', text, re.IGNORECASE)
        if match:
            return match.group(1)

        # Pattern 4: Last number before period at end of sentence
        match = re.search(r'(\d+(?:\.\d+)?)\s*\.\s*$', text)
        if match:
            return match.group(1)

        return None

    def _normalize(self, raw: str) -> int | float | str:
        """Normalize numeric answers for comparison."""
        value = raw.strip().lower().replace("_", "").replace(" ", "")

        # IP addresses
        if "." in value:
            parts = value.split(".")
            if len(parts) == 4 and all(
                p.isdigit() and 0 <= int(p) <= 255 for p in parts if p
            ):
                return ".".join(str(int(p)) for p in parts)

        # Hex with 0x prefix
        if value.startswith("0x"):
            try:
                return int(value, 16)
            except ValueError:
                pass

        # Binary with 0b prefix
        if value.startswith("0b"):
            try:
                return int(value, 2)
            except ValueError:
                pass

        # Binary without prefix (string of 0s and 1s, at least 4 chars)
        if len(value) >= 4 and set(value).issubset({"0", "1"}):
            try:
                return int(value, 2)
            except ValueError:
                pass

        # Hex with h suffix
        if value.endswith("h") and len(value) > 1:
            try:
                return int(value[:-1], 16)
            except ValueError:
                pass

        # CIDR notation
        if value.startswith("/") and value[1:].isdigit():
            return value

        # Regular decimal
        try:
            if "." not in value and "e" not in value:
                return int(value)
            return float(value)
        except ValueError:
            return raw.strip()

    def _compare(
        self,
        user: int | float | str,
        correct: int | float | str,
        tolerance: float = 0,
    ) -> bool:
        """Compare numeric answers with type-aware logic."""
        # String comparison for IPs, CIDR, etc.
        if isinstance(user, str) and isinstance(correct, str):
            return user.strip().lower() == correct.strip().lower()

        # Mixed types don't match
        if isinstance(user, str) or isinstance(correct, str):
            return False

        # Integer comparison (exact for binary/hex)
        if isinstance(user, int) and isinstance(correct, int):
            return user == correct

        # Float comparison with tolerance
        try:
            user_float = float(user)
            correct_float = float(correct)

            if tolerance > 0 and correct_float != 0:
                return abs(user_float - correct_float) <= abs(correct_float * tolerance)
            return user_float == correct_float
        except (ValueError, TypeError):
            return False
