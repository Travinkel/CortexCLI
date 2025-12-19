"""
True/False atom handler.

Binary choice questions. User responds T/F to a statement.
"""

import json
import os
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown

from src.delivery.cortex_visuals import get_asi_prompt
from . import AtomType, register
from .base import AnswerResult, is_dont_know

# --- LLM Integration Prompts ---

EXPLAIN_TF_ERROR_SYSTEM_PROMPT = """
You are an expert instructor explaining why a True/False statement is incorrect.

1.  **State the correct answer** (True or False).
2.  **Provide a concise, clear explanation** (1-2 sentences) for why the statement is incorrect, focusing on the core concept.
3.  **Use an analogy** if it helps clarify the concept.
4.  Be encouraging and direct.
"""

EXPLAIN_TF_ERROR_USER_PROMPT = """
A student answered a True/False question incorrectly. Please provide a simple explanation.

**Statement:** "{statement}"

**Student's Answer:** {user_answer}
**Correct Answer:** {correct_answer}

Explain why the statement is {correct_answer} and why the student's answer is wrong.
"""


@register(AtomType.TRUE_FALSE)
class TrueFalseHandler:
    """Handler for true/false atoms."""

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
                    system_instruction=EXPLAIN_TF_ERROR_SYSTEM_PROMPT
                )
            except (ImportError, Exception) as e:
                self._llm_client = None

    def validate(self, atom: dict) -> bool:
        """Check if atom has required T/F fields."""
        return bool(atom.get("front") and atom.get("back"))

    def present(self, atom: dict, console: Console) -> None:
        """Display the statement to evaluate."""
        front = atom.get("front", "No statement")
        panel = Panel(
            front,
            title="[bold cyan]TRUE OR FALSE[/bold cyan]",
            border_style="cyan",
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(panel)

    def get_input(self, atom: dict, console: Console) -> dict:
        """Get T/F response from user. '?' for I don't know."""
        console.print("[dim]T/F or '?' if you don't know[/dim]")

        while True:
            response = Prompt.ask(
                get_asi_prompt("flashcard", "[T/F/?]"),
                default="",
            ).strip().lower()

            if is_dont_know(response):
                return {"dont_know": True}

            if response in ("t", "true"):
                return {"answer": "True", "dont_know": False}
            elif response in ("f", "false"):
                return {"answer": "False", "dont_know": False}
            else:
                console.print("[yellow]Please enter T, F, or ? (don't know)[/yellow]")
                continue

    def check(self, atom: dict, answer: Any, console: Console | None = None) -> AnswerResult:
        """Check if user's answer matches correct answer."""
        if isinstance(answer, dict):
            if answer.get("dont_know"):
                correct_answer = self._parse_correct_answer(atom)
                return AnswerResult(
                    correct=False,
                    feedback="Let's learn this one!",
                    user_answer="I don't know",
                    correct_answer=correct_answer,
                    explanation=self._get_explanation(atom),
                    dont_know=True,
                )
            user_answer = answer.get("answer", "")
        else:
            user_answer = str(answer)

        correct_answer = self._parse_correct_answer(atom)
        is_correct = user_answer == correct_answer
        explanation = self._get_explanation(atom)

        if not is_correct and console:
            feedback = f"Incorrect. The correct answer is [bold]{correct_answer}[/bold]."
            # Use human-written explanation if available and substantial
            if explanation and len(explanation) > 15:
                console.print(
                    Panel(
                        Markdown(explanation),
                        title="[bold yellow]Explanation[/bold yellow]",
                        border_style="yellow",
                        box=box.ROUNDED,
                        padding=(1, 2)
                    )
                )
                # Set explanation to None to prevent the main loop from printing it again
                explanation = None
            else:
                # Otherwise, generate one with the LLM
                self.explain_error(atom, user_answer, correct_answer, console)
                explanation = None # Prevent double printing
        else:
            feedback = "Correct!"


        return AnswerResult(
            correct=is_correct,
            feedback=feedback,
            user_answer=user_answer,
            correct_answer=correct_answer,
            explanation=explanation, # This will only be non-null if correct or no console
        )

    def explain_error(self, atom: dict, user_answer: str, correct_answer: str, console: Console):
        """Use an LLM to explain the error for a True/False question."""
        self._initialize_llm()
        if not self._llm_client:
            return

        prompt = EXPLAIN_TF_ERROR_USER_PROMPT.format(
            statement=atom.get("front", ""),
            user_answer=user_answer,
            correct_answer=correct_answer,
        )

        try:
            with console.status("[dim]Generating explanation...[/dim]", spinner="dots"):
                response = self._llm_client.generate_content(prompt)
                explanation = response.text.strip()

            console.print(
                Panel(
                    Markdown(explanation),
                    title="[bold yellow]Explanation[/bold yellow]",
                    border_style="yellow",
                    box=box.ROUNDED,
                    padding=(1, 2)
                )
            )
        except Exception:
            # Fallback if LLM fails
            pass

    def _get_explanation(self, atom: dict) -> str:
        """Extract explanation from atom, handling JSON format."""
        if atom.get("explanation"):
            return atom["explanation"]
        back = atom.get("back", "").strip()
        if back.startswith("{"):
            try:
                data = json.loads(back)
                return data.get("explanation", "")
            except (json.JSONDecodeError, TypeError):
                pass
        # If 'back' is not JSON, but the answer is, the explanation might be after the answer
        # e.g. "True - because..."
        answer = self._parse_correct_answer(atom)
        if back.lower().startswith(answer.lower()):
            explanation = back[len(answer):].lstrip(" -:–") # Strip separators
            if len(explanation) > 10:
                return explanation.strip()
        return ""


    def hint(self, atom: dict, attempt: int) -> str | None:
        """Hints for true/false - usually the explanation."""
        if attempt == 1:
            explanation = self._get_explanation(atom)
            if explanation:
                words = explanation.split()
                if len(words) > 5:
                    return f"Think about: {' '.join(words[:5])}..."
        return None

    def _parse_correct_answer(self, atom: dict) -> str:
        """Parse expected answer from back field."""
        back = atom.get("back", "").strip()
        if back.startswith("{"):
            try:
                data = json.loads(back)
                answer = data.get("answer")
                if isinstance(answer, bool):
                    return "True" if answer else "False"
                elif isinstance(answer, str):
                    return "True" if answer.lower() in ("true", "t", "yes") else "False"
            except (json.JSONDecodeError, TypeError):
                pass
        back_lower = back.lower()
        if back_lower.startswith("true") or back_lower in ("t", "yes", "correct"):
            return "True"
        elif back_lower.startswith("false") or back_lower in ("f", "no", "incorrect"):
            return "False"
        return "True"
