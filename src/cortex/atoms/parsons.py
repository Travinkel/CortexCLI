"""
Parsons Problem atom handler.

User reorders scrambled code/steps into correct sequence.
Supports partial credit based on how many items are in correct position.
"""

import os
import random
import re
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown

from src.delivery.cortex_visuals import (
    CORTEX_THEME,
    STYLES,
    get_asi_prompt,
)

from . import AtomType, register
from .base import AnswerResult, is_dont_know

# --- LLM Integration Prompts ---

EXPLAIN_ERROR_SYSTEM_PROMPT = """
You are an expert programming and networking instructor. Your task is to explain a user's error in a Parsons problem.

1.  **Identify the first critical error** in the user's sequence.
2.  **Explain WHY it's an error** based on logical or procedural rules (e.g., "You need to enter configuration mode before you can configure an interface.").
3.  **Briefly state the correct step** that should have been taken at that point.
4.  Keep the explanation concise (2-3 sentences). Be encouraging.
"""

EXPLAIN_ERROR_USER_PROMPT = """
A student made a mistake on a sequencing problem. Please explain their error.

**Problem:** {problem_description}

**Correct Sequence:**
{correct_sequence}

**Student's Incorrect Sequence:**
{user_sequence}

Analyze the student's sequence and provide a brief, encouraging explanation of their first major mistake.
"""


@register(AtomType.PARSONS)
class ParsonsHandler:
    """Handler for Parsons problem atoms."""

    def __init__(self):
        self._llm_client = None
        self._api_key = os.getenv("GEMINI_API_KEY")

    def _initialize_llm(self):
        if self._api_key and self._llm_client is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self._api_key)
                self._llm_client = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    system_instruction=EXPLAIN_ERROR_SYSTEM_PROMPT
                )
            except (ImportError, Exception) as e:
                self._llm_client = None


    def validate(self, atom: dict) -> bool:
        """Check if atom has required Parsons fields (steps or back with separators)."""
        if atom.get("steps"):
            return len(atom["steps"]) >= 2
        back = atom.get("back", "")
        return bool(back and ("->" in back or "→" in back or "\n" in back))

    def present(self, atom: dict, console: Console) -> None:
        """Display the Parsons problem context."""
        front = atom.get("front", "Arrange in correct order:")
        panel = Panel(
            front,
            title="[bold cyan]SEQUENCE CHALLENGE[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Display scrambled blocks and get user ordering. Press 'h' for hints."""
        steps = atom.get("steps") or self._split_steps(atom.get("back", ""))

        if not steps:
            console.print("[yellow]No steps found[/yellow]")
            return {"skipped": True, "steps": []}

        # Preserve scrambled order across retries
        if "_scrambled" not in atom:
            scrambled = steps.copy()
            random.shuffle(scrambled)
            atom["_scrambled"] = scrambled
        scrambled = atom["_scrambled"]

        # Display scrambled blocks with ASI styling
        step_content = Text()
        for i, s in enumerate(scrambled):
            step_content.append(f"  [{i + 1}] ", style=STYLES["cortex_warning"])
            step_content.append(f"{s}\n", style=Style(color=CORTEX_THEME["white"]))

        step_panel = Panel(
            step_content,
            title="[bold yellow][*] SEQUENCE BLOCKS[/bold yellow]",
            border_style=Style(color=CORTEX_THEME["warning"]),
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(step_panel)
        console.print("[dim]'h'=hint, '?'=I don't know, or enter sequence (e.g., 3 1 2 4)[/dim]")
        console.print("[dim italic]Note: Blocks are shuffled - arrange them in the CORRECT order[/dim italic]")

        hint_count = 0
        last_user_order = None

        while True:
            seq = Prompt.ask(
                get_asi_prompt("parsons", "(e.g., 3 1 2 4)"),
            )

            if not seq or not seq.strip():
                console.print("[yellow]Please enter a sequence (e.g., 3 1 2 4)[/yellow]")
                continue

            if is_dont_know(seq):
                return {
                    "dont_know": True,
                    "correct_order": steps,
                    "source": atom.get("source_fact_basis"),
                    "hints_used": hint_count,
                }

            if seq.lower() == "h":
                hint_count += 1
                hint_text = self.hint(atom, hint_count, last_user_order)
                if hint_text:
                    console.print(f"[yellow]Hint {hint_count}:[/yellow] {hint_text}")
                else:
                    console.print("[dim]No more hints available[/dim]")
                continue

            try:
                indices = [int(x) - 1 for x in seq.replace(",", " ").split()]
                last_user_order = [scrambled[i] for i in indices if 0 <= i < len(scrambled)]
            except (ValueError, IndexError):
                console.print("[red]Invalid sequence. Please use numbers corresponding to the blocks.[/red]")
                continue

            break

        return {
            "user_order": last_user_order,
            "correct_order": steps,
            "scrambled": scrambled,
            "user_input": seq,
            "source": atom.get("source_fact_basis"),
            "hints_used": hint_count,
        }

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check if user ordering matches correct sequence."""
        if answer.get("skipped"):
            return AnswerResult(
                correct=True,
                feedback="Skipped - no steps available",
                user_answer="skipped",
                correct_answer="",
            )

        if answer.get("dont_know"):
            correct_order = answer.get("correct_order", [])
            correct_str = " -> ".join(correct_order)
            return AnswerResult(
                correct=False,
                feedback="Let's learn this one!",
                user_answer="I don't know",
                correct_answer=correct_str,
                explanation=answer.get("source"),
                dont_know=True,
            )

        user_order = answer.get("user_order", [])
        correct_order = answer.get("correct_order", [])
        user_input = answer.get("user_input", "")

        is_correct = user_order == correct_order

        if not is_correct and console:
            self.render_diff(user_order, correct_order, console)
            self.explain_error(atom, user_order, correct_order, console)


        correct_positions = sum(
            1 for i, step in enumerate(user_order)
            if i < len(correct_order) and step == correct_order[i]
        )
        partial_score = correct_positions / len(correct_order) if correct_order else 0

        correct_str = " -> ".join(correct_order)

        return AnswerResult(
            correct=is_correct,
            feedback="Correct sequence!" if is_correct else f"Incorrect. {correct_positions}/{len(correct_order)} in position.",
            user_answer=user_input,
            correct_answer=correct_str,
            partial_score=partial_score,
            explanation=answer.get("source") if not is_correct else None,
        )

    def hint(self, atom: dict, attempt: int, last_user_order: list[str] | None = None) -> str | None:
        """Progressive hints for Parsons problems."""
        steps = atom.get("steps") or self._split_steps(atom.get("back", ""))
        if not steps:
            return None

        if last_user_order:
            correct_prefix = 0
            for i, step in enumerate(last_user_order):
                if i < len(steps) and step == steps[i]:
                    correct_prefix += 1
                else:
                    break
            if correct_prefix > 0:
                return f"You have the first {correct_prefix} step(s) correct. The next step is: {steps[correct_prefix][:40]}..."

        if attempt == 1:
            return f"The first step is: {steps[0][:40]}..."
        elif attempt == 2:
            return f"The last step is: {steps[-1][:40]}..."
        elif attempt == 3 and len(steps) > 2:
            mid = len(steps) // 2
            return f"Step {mid + 1} should be: {steps[mid][:30]}..."

        return None

    def render_diff(self, user_order: list, correct_order: list, console: Console) -> None:
        """Render visual diff between user and correct ordering with three states."""
        diff_table = Table(
            box=box.MINIMAL_HEAVY_HEAD,
            border_style=Style(color=CORTEX_THEME["error"]),
            show_header=False,
        )
        diff_table.add_column("Status", width=2)
        diff_table.add_column("Your Sequence", overflow="fold")

        correct_set = set(correct_order)

        for i, user_step in enumerate(user_order):
            icon = ""
            style = ""
            
            if i < len(correct_order) and user_step == correct_order[i]:
                # Green: Correct step in the correct position
                icon = "✓"
                style = STYLES["cortex_success"]
            elif user_step in correct_set:
                # Yellow: Correct step in the wrong position
                icon = "•"
                style = STYLES["cortex_warning"]
            else:
                # Red: Incorrect step
                icon = "✗"
                style = STYLES["cortex_error"]

            diff_table.add_row(Text(icon, style=style), Text(user_step, style=style))

        console.print(
            Panel(
                diff_table,
                title="[bold red]SEQUENCE ANALYSIS[/bold red]",
                border_style=Style(color=CORTEX_THEME["error"]),
                box=box.HEAVY,
            )
        )

    def explain_error(self, atom: dict, user_order: list, correct_order: list, console: Console):
        """Use an LLM to explain the first critical error in the user's sequence."""
        self._initialize_llm()
        if not self._llm_client:
            return

        # Format sequences for the prompt
        correct_sequence_str = "\n".join(f"- {step}" for step in correct_order)
        user_sequence_str = "\n".join(f"- {step}" for step in user_order)

        prompt = EXPLAIN_ERROR_USER_PROMPT.format(
            problem_description=atom.get("front", "N/A"),
            correct_sequence=correct_sequence_str,
            user_sequence=user_sequence_str,
        )

        try:
            with console.status("[dim]Analyzing error...[/dim]", spinner="dots"):
                response = self._llm_client.generate_content(prompt)
                explanation = response.text.strip()

            console.print(
                Panel(
                    Markdown(explanation),
                    title="[bold yellow]Instructor's Note[/bold yellow]",
                    border_style="yellow",
                    box=box.ROUNDED,
                    padding=(1, 2)
                )
            )
        except Exception as e:
            # Fallback or log error
            pass


    def _split_steps(self, back: str) -> list[str]:
        """Split a back field into ordered steps."""
        parts = re.split(r"\s*(?:->|→)+\s*|\n+", back.strip())
        steps = [p.strip() for p in parts if p.strip()]
        return steps
