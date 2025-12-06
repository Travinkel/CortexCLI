"""
The Cortex CLI: ASI-themed neural study interface for CCNA mastery.

Visual Identity: "Digital Neocortex"
- Cyan/Electric Blue color scheme
- Pulsing brain ASCII art animations
- Futuristic ">_ INPUT VECTOR:" prompts
- Google Calendar integration for scheduling

Modes:
- nls cortex start --mode adaptive (default)  -> adaptive interleaved session
- nls cortex start --mode war                 -> cram mode (modules 11-17, immediate retries)
- nls cortex schedule --time "tomorrow 9am"   -> schedule on Google Calendar
- nls cortex agenda                            -> show upcoming sessions
"""
from __future__ import annotations

import os
import sys

# Fix Windows encoding issues for Unicode characters (ASCII art, box drawing)
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import random
import re
import time
from datetime import datetime, timedelta
from typing import Iterable, List, Optional

import typer
from dateutil import parser as date_parser
from rich import box
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.status import Status
from rich.style import Style
from rich.table import Table
from rich.text import Text
from sqlalchemy import text

from config import get_settings
from src.db.database import engine
from src.study.quiz_engine import QuizEngine, AtomType as QuizAtomType
from src.study.study_service import StudyService

# ASI Visual Components
from src.delivery.cortex_visuals import (
    CORTEX_THEME,
    STYLES,
    cortex_boot_sequence,
    cortex_question_panel,
    cortex_result_panel,
    get_asi_prompt,
    CortexSpinner,
    create_neurolink_panel,
    create_compact_neurolink,
    create_struggle_heatmap,
)

# Google Calendar Integration
from src.integrations.google_calendar import CortexCalendar

# Neuro-Cognitive Diagnosis Engine (NCDE)
from src.adaptive.ncde_pipeline import (
    NCDEPipeline,
    SessionContext,
    RawInteractionEvent,
    create_raw_event,
    FatigueVector,
    RemediationType,
)
from src.adaptive.neuro_model import (
    CognitiveDiagnosis,
    FailMode,
    SuccessMode,
    CognitiveState,
)

cortex_app = typer.Typer(
    help="The Cortex: ASI-themed neural study interface with calendar scheduling",
    no_args_is_help=True,
)

console = Console()


def _normalize_numeric(raw: str) -> int | float | str:
    """
    Normalize numeric answers for comparison (supports hex/binary/decimal).

    Returns:
        - int for binary/hex values (preserves precision for large numbers)
        - float for decimal values
        - str for non-numeric values (e.g., IP addresses like "192.168.1.0")

    Hardening:
    - Uses int instead of float for binary/hex to avoid precision loss
    - Handles IP addresses as strings for exact matching
    - Returns original string for complex values (subnet masks, etc.)
    """
    value = raw.strip().lower().replace("_", "").replace(" ", "")

    # Handle IP addresses (dotted decimal notation)
    if "." in value and all(
        part.isdigit() and 0 <= int(part) <= 255
        for part in value.split(".")
        if part
    ):
        # Return as normalized IP string for exact comparison
        try:
            parts = value.split(".")
            if len(parts) == 4:
                return ".".join(str(int(p)) for p in parts)
        except ValueError:
            pass

    # Hex with 0x prefix - use int for precision
    if value.startswith("0x"):
        try:
            return int(value, 16)
        except ValueError:
            pass

    # Binary with 0b prefix - use int for precision
    if value.startswith("0b"):
        try:
            return int(value, 2)
        except ValueError:
            pass

    # Binary without prefix (string of 0s and 1s, at least 4 chars)
    # Must be all 0s and 1s to be considered binary
    if len(value) >= 4 and set(value).issubset({"0", "1"}):
        try:
            return int(value, 2)
        except ValueError:
            pass

    # Hex with h suffix (e.g., "FFh")
    if value.endswith("h") and len(value) > 1:
        try:
            return int(value[:-1], 16)
        except ValueError:
            pass

    # CIDR notation (e.g., "/24") - return as string
    if value.startswith("/") and value[1:].isdigit():
        return value

    # Regular decimal number
    try:
        # Try int first for whole numbers
        if "." not in value and "e" not in value:
            return int(value)
        return float(value)
    except ValueError:
        # Return as string for non-numeric (allows string comparison)
        return raw.strip()


def _compare_numeric_answers(user_answer: int | float | str, correct_answer: int | float | str, tolerance: float = 0) -> bool:
    """
    Compare numeric answers with type-aware logic.

    Args:
        user_answer: Normalized user answer
        correct_answer: Normalized correct answer
        tolerance: Fractional tolerance for float comparison (0 = exact)

    Returns:
        True if answers match within tolerance
    """
    # String comparison for IP addresses, CIDR, etc.
    if isinstance(user_answer, str) or isinstance(correct_answer, str):
        return str(user_answer).strip().lower() == str(correct_answer).strip().lower()

    # Integer comparison (exact match for binary/hex)
    if isinstance(user_answer, int) and isinstance(correct_answer, int):
        return user_answer == correct_answer

    # Float comparison with tolerance
    try:
        user_float = float(user_answer)
        correct_float = float(correct_answer)

        if tolerance > 0 and correct_float != 0:
            return abs(user_float - correct_float) <= abs(correct_float * tolerance)
        return user_float == correct_float
    except (ValueError, TypeError):
        return False


def _split_parsons_steps(back: str) -> list[str]:
    """Split a Parsons back field into ordered steps."""
    # Common delimiters: arrow (unicode or ASCII), newline, numbered list
    # Use alternation instead of character class to avoid range interpretation
    parts = re.split(r"\s*(?:->|→)+\s*|\n+", back.strip())
    steps = [p.strip() for p in parts if p.strip()]
    return steps


# Cortex only supports quiz-style atom types (not flashcards/cloze - those are for Anki)
CORTEX_SUPPORTED_TYPES = {"mcq", "true_false", "matching", "parsons"}


class CortexSession:
    """
    Interactive session runner for Cortex with NCDE integration.

    Uses StudyService as the unified backend for:
    - Fetching atoms (get_war_session / get_adaptive_session)
    - Recording interactions (record_interaction)
    - Updating mastery metrics (FSRS stability, section mastery)

    The NCDE (Neuro-Cognitive Diagnosis Engine) pipeline provides:
    - Real-time cognitive state estimation (PSI, Fatigue Vector)
    - Error classification (Encoding, Discrimination, Integration, Executive)
    - Dynamic remediation routing (Force Z, PLM, Micro-Breaks)

    Architecture:
    - The run loop is an Event-Driven Cognitive Loop
    - Interactions are intercepted and processed through NCDE middleware
    - Remediation strategies can inject nodes or switch modes

    Supported atom types: MCQ, True/False, Matching, Parsons
    (Flashcards and Cloze are for Anki only)
    """

    def __init__(
        self,
        modules: list[int],
        limit: int = 20,
        war_mode: bool = False,
        enable_ncde: bool = True,
    ):
        self.modules = modules
        self.limit = limit
        self.war_mode = war_mode
        self.enable_ncde = enable_ncde
        self.start_time = time.monotonic()
        self.correct = 0
        self.incorrect = 0
        self.current_index = 0
        self.queue: list[dict] = []
        self.settings = get_settings()

        # Unified backend - all interactions go through StudyService
        self.study_service = StudyService()
        self.quiz_engine = QuizEngine()  # Keep for parsing atom content

        # NCDE Pipeline - The Cognitive Brain
        self.ncde = NCDEPipeline() if enable_ncde else None
        self.session_context: Optional[SessionContext] = None

        # Suspension stack for Force Z backtracking
        self._suspension_stack: list[dict] = []

        # Error streak tracking for fatigue detection
        self._error_streak = 0

    def load_queue(self) -> None:
        """
        Load atoms for the session via StudyService.

        War Mode: Uses get_war_session() - prioritizes quiz types, ignores FSRS
        Adaptive Mode: Uses get_adaptive_session() - uses FSRS scheduling + interleaving

        Only loads supported quiz types: MCQ, True/False, Matching, Parsons
        (Flashcards and Cloze are for Anki only)
        """
        with CortexSpinner(console, "Priming neural pathways..."):
            if self.war_mode:
                # War Mode: aggressive mastery, ignores due dates
                atoms = self.study_service.get_war_session(
                    modules=self.modules,
                    limit=self.limit * 2,  # Request extra to account for filtering
                    prioritize_types=list(CORTEX_SUPPORTED_TYPES),
                )
            else:
                # Adaptive Mode: FSRS-scheduled + interleaved
                atoms = self.study_service.get_adaptive_session(
                    limit=self.limit * 2,  # Request extra to account for filtering
                    include_new=True,
                    interleave=True,
                )

            # Filter to only Cortex-supported types (MCQ, T/F, Matching, Parsons)
            atoms = [a for a in atoms if a.get("atom_type") in CORTEX_SUPPORTED_TYPES]

            # Parse atom content for presentation (MCQ options, Parsons steps, etc.)
            # Also validates content - removes invalid atoms (e.g., MCQs without options)
            valid_atoms = []
            for atom in atoms:
                if self._hydrate_atom(atom):
                    valid_atoms.append(atom)

            # Trim to requested limit
            self.queue = valid_atoms[:self.limit]

        # War mode bias: duplicate harder types for forced repetition
        if self.war_mode and self.queue:
            hard_types = ["parsons", "matching"]
            extras = [q for q in self.queue if q.get("atom_type") in hard_types]
            if extras:
                self.queue.extend(random.sample(extras, k=min(len(extras), 5)))

        random.shuffle(self.queue)

    def _hydrate_atom(self, atom: dict) -> bool:
        """
        Parse atom content based on type (MCQ options, Parsons steps, etc.).

        Adds parsed fields to the atom dict for presentation.

        Returns:
            True if atom is valid and should be included, False to skip it
        """
        atom_type = atom.get("atom_type", "")
        back = atom.get("back", "")

        if atom_type == "mcq":
            import json

            # First check for quiz_content from quiz_questions table
            quiz_content = atom.get("quiz_content")
            if quiz_content:
                try:
                    if isinstance(quiz_content, str):
                        data = json.loads(quiz_content)
                    else:
                        data = quiz_content
                    options = data.get("options", [])
                    correct_idx = data.get("correct_index", 0)
                    if len(options) >= 2:
                        atom["options"] = options
                        atom["correct_answer"] = options[correct_idx] if 0 <= correct_idx < len(options) else options[0]
                        atom["explanation"] = data.get("explanation", "")
                        return True
                except (json.JSONDecodeError, TypeError):
                    pass

            # Fallback: Parse MCQ options from back field - try JSON first
            try:
                data = json.loads(back)
                if isinstance(data, dict):
                    options = data.get("options", [])
                    if len(options) >= 2:
                        atom["options"] = options
                        atom["correct_answer"] = data.get("correct", options[0] if options else "")
                        return True
            except (json.JSONDecodeError, TypeError):
                pass

            # Line-based parsing (last resort)
            options = [o.strip() for o in re.split(r"\n+|- ", back) if o.strip()]

            # MCQ must have at least 2 options to be valid
            if len(options) < 2:
                return False  # Skip invalid MCQs

            atom["options"] = options
            atom["correct_answer"] = options[0] if options else back
            return True

        elif atom_type == "true_false":
            # True/False questions - back should be "True" or "False"
            atom["correct_answer"] = back.strip().lower() in ("true", "t", "yes", "1")
            return True

        elif atom_type == "matching":
            # Matching questions - parse pairs from back
            try:
                import json
                data = json.loads(back)
                if isinstance(data, dict) and "pairs" in data:
                    atom["pairs"] = data["pairs"]
                    return True
            except (json.JSONDecodeError, TypeError):
                pass
            # Fallback: skip malformed matching questions
            return False

        elif atom_type == "parsons":
            steps = _split_parsons_steps(back)
            if len(steps) < 2:
                return False  # Need at least 2 steps
            atom["steps"] = steps
            return True

        # Unsupported type
        return False

    def run(self) -> None:
        """
        Run the interactive loop with ASI boot sequence and NCDE integration.

        The run loop is an Event-Driven Cognitive Loop:
        1. Render question
        2. Capture interaction with telemetry
        3. Process through NCDE pipeline
        4. Execute remediation strategy (if needed)
        5. Update learner persona

        Reference: Section 1.2 - From FSM to Event-Driven Cognitive Loops
        """
        # ASI Boot Sequence Animation
        cortex_boot_sequence(console, war_mode=self.war_mode)

        if not self.queue:
            self.load_queue()

        if not self.queue:
            console.print(Panel(
                "[bold red]No atoms found for selected modules.[/bold red]\n"
                "Ensure atoms have been generated and synced.",
                border_style=Style(color=CORTEX_THEME["error"]),
                box=box.HEAVY,
            ))
            return

        # Initialize NCDE session context
        if self.ncde:
            self.session_context = SessionContext(
                session_id=f"session_{int(time.time())}",
                learner_id="default_learner",  # Would come from auth
                queue_size=len(self.queue),
            )

        idx = 0
        while idx < len(self.queue):
            note = self.queue[idx]
            self.current_index = idx + 1
            self._render_question(note)

            # Time the response
            response_start = time.monotonic()
            is_correct, user_answer = self._ask(note)
            response_time_ms = int((time.monotonic() - response_start) * 1000)

            # Update error streak
            if is_correct:
                self._error_streak = 0
            else:
                self._error_streak += 1

            # === NCDE INTERCEPTION LAYER ===
            if self.ncde and self.session_context:
                # Create raw interaction event
                raw_event = create_raw_event(
                    atom_id=str(note.get("id", "")),
                    atom_type=note.get("atom_type", "flashcard"),
                    is_correct=is_correct,
                    user_answer=user_answer,
                    correct_answer=note.get("back", ""),
                    response_time_ms=response_time_ms,
                    session_duration_seconds=int(time.monotonic() - self.start_time),
                    session_index=idx,
                    selected_distractor_id=note.get("_selected_distractor"),
                )

                # Store in history
                self.session_context.interaction_history.append(raw_event)
                self.session_context.queue_position = idx

                # Process through NCDE pipeline
                diagnosis, strategy = self.ncde.process(raw_event, self.session_context)

                # Display cognitive diagnosis (if not correct)
                if not is_correct:
                    self._display_diagnosis(diagnosis)

                # Execute remediation strategy
                should_continue = self._execute_remediation(strategy, note)

                # Update session context stats
                if is_correct:
                    self.session_context.correct_count += 1
                else:
                    self.session_context.incorrect_count += 1
                    self.session_context.error_streak = self._error_streak

                # Handle strategy outcomes
                if strategy.name == "micro_break":
                    self._trigger_micro_break(strategy)
                    # Reset fatigue after break
                    self.session_context.fatigue = FatigueVector()
                elif strategy.name == "plm" and not is_correct:
                    # PLM would be handled by a separate mode
                    self._trigger_plm_hint(diagnosis)

            # Record interaction via StudyService (updates FSRS + section mastery)
            atom_id = note.get("id")
            if atom_id:
                session_type = "war" if self.war_mode else "adaptive"
                self.study_service.record_interaction(
                    atom_id=atom_id,
                    is_correct=is_correct,
                    response_time_ms=response_time_ms,
                    user_answer=user_answer,
                    session_type=session_type,
                )

            if is_correct:
                self.correct += 1
            else:
                self.incorrect += 1
                if self.war_mode:
                    # Immediate retry: push back to next position
                    self.queue.insert(idx + 1, note)

            idx += 1

        # Session complete with ASI styling + NCDE summary
        self._display_session_summary()

    def _display_diagnosis(self, diagnosis: CognitiveDiagnosis) -> None:
        """Display cognitive diagnosis to learner with ASI styling."""
        if not diagnosis.fail_mode:
            return

        # Map fail modes to user-friendly messages
        mode_messages = {
            FailMode.ENCODING_ERROR: (
                "💭 ENCODING GAP",
                "This concept hasn't fully consolidated. Return to source material.",
                CORTEX_THEME["warning"],
            ),
            FailMode.DISCRIMINATION_ERROR: (
                "🔀 PATTERN CONFUSION",
                "You're confusing similar concepts. Let's train discrimination.",
                CORTEX_THEME["accent"],
            ),
            FailMode.INTEGRATION_ERROR: (
                "🧩 INTEGRATION GAP",
                "The pieces aren't connecting. Let's walk through step-by-step.",
                CORTEX_THEME["secondary"],
            ),
            FailMode.EXECUTIVE_ERROR: (
                "⚡ TOO FAST",
                "You answered before fully processing. Slow down and read carefully.",
                CORTEX_THEME["warning"],
            ),
            FailMode.RETRIEVAL_ERROR: (
                "📦 RETRIEVAL LAPSE",
                "Normal forgetting. Spaced repetition will strengthen this trace.",
                CORTEX_THEME["dim"],
            ),
            FailMode.FATIGUE_ERROR: (
                "😴 COGNITIVE FATIGUE",
                "Your brain needs rest. Consider taking a break.",
                CORTEX_THEME["error"],
            ),
        }

        title, message, color = mode_messages.get(
            diagnosis.fail_mode,
            ("📊 DIAGNOSIS", diagnosis.explanation or "Continue learning.", CORTEX_THEME["primary"])
        )

        diagnosis_text = Text()
        diagnosis_text.append(f"{title}\n", style=Style(color=color, bold=True))
        diagnosis_text.append(f"\n{message}\n", style=Style(color=CORTEX_THEME["white"]))

        if diagnosis.confidence > 0.7:
            diagnosis_text.append(
                f"\n[Confidence: {diagnosis.confidence:.0%}]",
                style=STYLES["cortex_dim"]
            )

        console.print(Panel(
            diagnosis_text,
            border_style=Style(color=color),
            box=box.ROUNDED,
            padding=(0, 1),
        ))

    def _execute_remediation(self, strategy, note: dict) -> bool:
        """
        Execute remediation strategy and return whether to continue.

        Returns:
            True to continue with next question, False to break/modify loop
        """
        if strategy.name == "standard":
            return True

        if strategy.name == "micro_break":
            return False  # Will trigger break

        if strategy.name == "force_z":
            # Inject prerequisite nodes
            result = strategy.execute(self.session_context)
            if result.nodes_to_inject:
                # Push current context to suspension stack
                self._suspension_stack.append({
                    "node": note,
                    "position": self.current_index,
                })
                # Inject remediation nodes at head of queue
                for prereq in reversed(result.nodes_to_inject):
                    self.queue.insert(self.current_index, prereq)

        return True

    def _trigger_micro_break(self, strategy) -> None:
        """Display and enforce a micro-break."""
        result = strategy.execute(self.session_context)

        break_text = Text()
        break_text.append("🧠 COGNITIVE RECOVERY MODE\n\n", style=STYLES["cortex_primary"])
        break_text.append(result.message + "\n\n", style=Style(color=CORTEX_THEME["white"]))
        break_text.append(
            "Take a short walk, hydrate, or close your eyes.\n",
            style=STYLES["cortex_dim"]
        )
        break_text.append(
            "Press Enter when ready to continue...",
            style=STYLES["cortex_accent"]
        )

        console.print(Panel(
            Align.center(break_text),
            border_style=Style(color=CORTEX_THEME["secondary"]),
            box=box.DOUBLE,
            padding=(1, 2),
        ))

        # Wait for user
        Prompt.ask("", default="", show_default=False)

    def _trigger_plm_hint(self, diagnosis: CognitiveDiagnosis) -> None:
        """Display PLM hint for discrimination training."""
        if diagnosis.fail_mode != FailMode.DISCRIMINATION_ERROR:
            return

        plm_text = Text()
        plm_text.append("🎯 DISCRIMINATION TRAINING TIP\n\n", style=STYLES["cortex_warning"])
        plm_text.append(
            "Focus on the KEY DIFFERENCE between confusable concepts.\n",
            style=Style(color=CORTEX_THEME["white"])
        )
        plm_text.append(
            "Ask yourself: What makes this DIFFERENT from similar items?",
            style=STYLES["cortex_dim"]
        )

        console.print(Panel(
            plm_text,
            border_style=Style(color=CORTEX_THEME["warning"]),
            box=box.ROUNDED,
            padding=(0, 1),
        ))

    def _display_session_summary(self) -> None:
        """Display session summary with NCDE cognitive insights."""
        accuracy = (self.correct / max(1, self.correct + self.incorrect)) * 100

        result_text = Text()
        result_text.append("[*] SESSION COMPLETE [*]\n\n", style=STYLES["cortex_primary"])
        result_text.append(f"Accuracy: {accuracy:.1f}%\n", style=STYLES["cortex_success"])
        result_text.append(f"Processed: {self.correct + self.incorrect} atoms\n", style=STYLES["cortex_accent"])
        result_text.append(f"Correct: {self.correct}  |  Errors: {self.incorrect}\n", style=STYLES["cortex_dim"])

        # Add NCDE insights if available
        if self.ncde and self.session_context:
            result_text.append("\n── COGNITIVE INSIGHTS ──\n", style=STYLES["cortex_secondary"])

            # Fatigue summary
            fatigue = self.session_context.fatigue
            if fatigue.norm > 0.3:
                fatigue_status = "⚠️ Elevated" if fatigue.norm > 0.5 else "📊 Moderate"
                result_text.append(
                    f"Fatigue Level: {fatigue_status} ({fatigue.norm:.0%})\n",
                    style=STYLES["cortex_warning"] if fatigue.norm > 0.5 else STYLES["cortex_dim"]
                )

            # Error pattern summary
            if self.session_context.diagnosis_history:
                fail_counts = {}
                for diag in self.session_context.diagnosis_history:
                    if diag.fail_mode:
                        mode = diag.fail_mode.value
                        fail_counts[mode] = fail_counts.get(mode, 0) + 1

                if fail_counts:
                    top_mode = max(fail_counts, key=fail_counts.get)
                    result_text.append(
                        f"Primary Error Pattern: {top_mode.upper()}\n",
                        style=STYLES["cortex_accent"]
                    )

            # PSI summary
            if self.session_context.psi_scores:
                low_psi = [c for c, p in self.session_context.psi_scores.items() if p < 0.5]
                if low_psi:
                    result_text.append(
                        f"Concepts needing discrimination: {len(low_psi)}\n",
                        style=STYLES["cortex_warning"]
                    )

        console.print(Panel(
            Align.center(result_text),
            border_style=Style(color=CORTEX_THEME["success"]),
            box=box.DOUBLE,
            padding=(1, 2),
        ))

    # ==============================
    # Rendering helpers
    # ==============================

    def _timer_panel(self, prefix: str = "Mode") -> Panel:
        elapsed = time.monotonic() - self.start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        mode = "W A R" if self.war_mode else "A D A P T I V E"
        mode_color = CORTEX_THEME["error"] if self.war_mode else CORTEX_THEME["primary"]

        txt = Text()
        txt.append("[*] CORTEX ", style=Style(color=CORTEX_THEME["primary"], bold=True))
        txt.append(f"{prefix}: ", style=STYLES["cortex_dim"])
        txt.append(f"{mode} MODE\n", style=Style(color=mode_color, bold=True))
        txt.append(f"⏱ {minutes:02d}:{seconds:02d}", style=Style(color=CORTEX_THEME["accent"]))
        txt.append(f"  │  ", style=STYLES["cortex_dim"])
        accuracy = (self.correct / max(1, self.correct + self.incorrect)) * 100
        txt.append(f"✓ {accuracy:.1f}%", style=Style(color=CORTEX_THEME["success"]))
        txt.append(f"  │  ", style=STYLES["cortex_dim"])
        txt.append(f"Q: {self.current_index}/{len(self.queue)}", style=STYLES["cortex_secondary"])

        return Panel(
            txt,
            padding=(0, 1),
            border_style=Style(color=mode_color),
            box=box.HEAVY,
        )

    def _stats_panel(self) -> Panel:
        table = Table.grid(padding=0)
        table.add_row(
            Text("PROCESSED", style=STYLES["cortex_dim"]),
            Text(f"{self.correct + self.incorrect}", style=Style(color=CORTEX_THEME["white"]))
        )
        table.add_row(
            Text("CORRECT", style=STYLES["cortex_dim"]),
            Text(f"{self.correct}", style=STYLES["cortex_success"])
        )
        table.add_row(
            Text("ERRORS", style=STYLES["cortex_dim"]),
            Text(f"{self.incorrect}", style=STYLES["cortex_error"])
        )
        streak = max(0, self.correct - self.incorrect)
        table.add_row(
            Text("MOMENTUM", style=STYLES["cortex_dim"]),
            Text(f"{streak} [*]", style=STYLES["cortex_warning"])
        )
        table.add_row(
            Text("MODULES", style=STYLES["cortex_dim"]),
            Text(", ".join(str(m) for m in self.modules), style=STYLES["cortex_secondary"])
        )
        return Panel(
            table,
            title="[bold cyan][*] TELEMETRY[/bold cyan]",
            border_style=Style(color=CORTEX_THEME["secondary"]),
            box=box.HEAVY,
            padding=(1, 1),
        )

    def _neurolink_panel(self) -> Panel:
        """Generate the neuro-link status panel from current cognitive state."""
        if self.ncde and self.session_context:
            # Get cognitive state from NCDE
            fatigue = self.session_context.fatigue
            fatigue_level = fatigue.norm if fatigue else 0.0

            # Calculate encoding from recent accuracy
            history = self.session_context.interaction_history
            if history and len(history) >= 3:
                recent = history[-5:]
                encoding = sum(1 for h in recent if h.is_correct) / len(recent)
            else:
                encoding = 1.0

            # Calculate integration from complex question performance
            complex_responses = [h for h in history if h.atom_type in ("parsons", "matching")]
            if complex_responses:
                integration = sum(1 for h in complex_responses if h.is_correct) / len(complex_responses)
            else:
                integration = 1.0

            # Focus from response time consistency
            focus = 1.0 - min(self._error_streak / 5, 1.0)

            # Get diagnosis if available
            diagnosis = ""
            strategy = ""
            if self.session_context.diagnosis_history:
                last_diag = self.session_context.diagnosis_history[-1]
                if last_diag.fail_mode:
                    diagnosis = last_diag.fail_mode.value
                    strategy = last_diag.strategy.value if last_diag.strategy else ""

            return create_neurolink_panel(
                encoding=encoding,
                integration=integration,
                focus=focus,
                fatigue=fatigue_level,
                diagnosis=diagnosis,
                strategy=strategy,
            )

        # Default panel when NCDE not active
        return create_neurolink_panel()

    def _layout(self, question_panel: Panel) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="top", size=5),
            Layout(name="body", ratio=3),
        )
        layout["body"].split_row(
            Layout(name="question", ratio=3),
            Layout(name="sidebar", size=36),
        )
        # Split sidebar into stats and neuro-link
        layout["sidebar"].split_column(
            Layout(name="stats", ratio=1),
            Layout(name="neurolink", ratio=1),
        )
        layout["top"].update(self._timer_panel())
        layout["stats"].update(self._stats_panel())
        layout["neurolink"].update(self._neurolink_panel())
        layout["question"].update(question_panel)
        return layout

    def _render_question(self, note: dict) -> None:
        """Render the dashboard with current question."""
        header = f"{note.get('atom_type','note').upper()} · {note.get('card_id','')}"
        body = Text(note.get("front", "").strip() or "No prompt", style="bold")

        panel = Panel(
            body,
            title=header,
            border_style="cyan",
            box=box.ROUNDED,
            padding=(0, 1),
        )
        console.clear()
        console.print(self._layout(panel))

    # ==============================
    # Question handlers
    # ==============================

    def _ask(self, note: dict) -> tuple[bool, str]:
        """
        Route to appropriate question handler.

        Returns:
            Tuple of (is_correct, user_answer)
        """
        atom_type = note.get("atom_type", "")
        if atom_type == "mcq":
            return self._ask_mcq(note)
        if atom_type == "parsons":
            return self._ask_parsons(note)
        if atom_type == "true_false":
            return self._ask_true_false(note)
        if atom_type == "matching":
            return self._ask_matching(note)
        # Fallback (shouldn't happen with proper filtering)
        console.print(f"[yellow]Unsupported type: {atom_type}[/yellow]")
        return (True, "skipped")

    def _ask_flashcard(self, note: dict) -> tuple[bool, str]:
        """Front -> flip -> self-check."""
        _ = Prompt.ask("\nPress Enter to flip", default="", show_default=False)
        self._flip_animation(note.get("front", ""))
        console.print(
            Panel(
                note.get("back", "No answer"),
                title="Back (Note view)",
                border_style="green",
                box=box.HEAVY,
            )
        )
        good = Confirm.ask("Did you retrieve it?", default=True)
        return (bool(good), "yes" if good else "no")

    def _flip_animation(self, front: str) -> None:
        """Minimal flip effect by clearing/redrawing."""
        for dots in ["·", "··", "···"]:
            console.clear()
            console.print(
                Panel(
                    Align.center(Text(f"Flipping {dots}", style="cyan")),
                    border_style="cyan",
                    box=box.HEAVY,
                )
            )
            time.sleep(0.12)
        console.clear()

    def _ask_mcq(self, note: dict) -> tuple[bool, str]:
        # Use pre-parsed options if available, otherwise parse from back
        options = note.get("options") or [
            o.strip() for o in re.split(r"\n+|- ", note.get("back", "")) if o.strip()
        ]
        correct = note.get("correct_answer") or (options[0] if options else note.get("back", ""))
        random.shuffle(options)

        option_table = Table(box=box.SQUARE, border_style=Style(color=CORTEX_THEME["accent"]))
        option_table.add_column("", justify="center", width=4, style=Style(color=CORTEX_THEME["warning"]))
        option_table.add_column("OPTION", overflow="fold", style=Style(color=CORTEX_THEME["white"]))
        for idx, opt in enumerate(options, start=1):
            option_table.add_row(f"[{idx}]", opt)

        panel = Panel(
            option_table,
            title="[bold yellow]SELECT TARGET[/bold yellow]",
            border_style=Style(color=CORTEX_THEME["accent"]),
            box=box.HEAVY
        )
        console.print(panel)

        # ASI-style prompt
        choice = Prompt.ask(
            get_asi_prompt("mcq", f"[1-{len(options)}]"),
            choices=[str(i) for i in range(1, len(options) + 1)]
        )
        picked = options[int(choice) - 1] if options else ""

        if picked.strip().lower() == correct.strip().lower():
            console.print(cortex_result_panel(True, correct))
            return (True, picked)

        console.print(cortex_result_panel(False, correct, note.get("source_fact_basis")))
        return (False, picked)

    def _ask_parsons(self, note: dict) -> tuple[bool, str]:
        # Use pre-parsed steps if available
        steps = note.get("steps") or _split_parsons_steps(note.get("back", ""))
        if not steps:
            console.print(Panel(
                "[yellow]No steps found; treating as flashcard[/yellow]",
                border_style=Style(color=CORTEX_THEME["warning"])
            ))
            return self._ask_flashcard(note)

        scrambled = steps.copy()
        random.shuffle(scrambled)

        # ASI-styled step display
        step_content = Text()
        for i, s in enumerate(scrambled):
            step_content.append(f"  [{i+1}] ", style=STYLES["cortex_warning"])
            step_content.append(f"{s}\n", style=Style(color=CORTEX_THEME["white"]))

        step_panel = Panel(
            step_content,
            title="[bold yellow][*] SEQUENCE BLOCKS[/bold yellow]",
            border_style=Style(color=CORTEX_THEME["warning"]),
            box=box.HEAVY,
            padding=(1, 2),
        )
        console.print(step_panel)

        # ASI-style prompt
        seq = Prompt.ask(
            get_asi_prompt("parsons", "(e.g., 3 1 2 4)"),
            default=" ".join(str(i + 1) for i in range(len(scrambled))),
        )
        try:
            indices = [int(x) - 1 for x in seq.replace(",", " ").split()]
        except ValueError:
            indices = list(range(len(scrambled)))

        ordered = [scrambled[i] for i in indices if 0 <= i < len(scrambled)]

        if ordered == steps:
            console.print(cortex_result_panel(True, " → ".join(steps)))
            return (True, seq)

        # Visual diff with ASI styling
        diff = Table(box=box.MINIMAL_HEAVY_HEAD, border_style=Style(color=CORTEX_THEME["error"]))
        diff.add_column("YOUR SEQUENCE", overflow="fold", style=Style(color=CORTEX_THEME["white"]))
        diff.add_column("CORRECT", overflow="fold", style=Style(color=CORTEX_THEME["accent"]))
        max_len = max(len(ordered), len(steps))
        for i in range(max_len):
            user_val = ordered[i] if i < len(ordered) else ""
            correct_val = steps[i] if i < len(steps) else ""
            user_style = STYLES["cortex_success"] if user_val == correct_val else STYLES["cortex_error"]
            diff.add_row(Text(user_val, style=user_style), Text(correct_val, style=STYLES["cortex_accent"]))

        console.print(Panel(
            diff,
            title="[bold red][*] SEQUENCE ERROR[/bold red]",
            border_style=Style(color=CORTEX_THEME["error"]),
            box=box.HEAVY,
            subtitle=f"[dim]Source: {note.get('source_fact_basis', 'N/A')}[/dim]" if note.get("source_fact_basis") else None,
        ))
        return (False, seq)

    def _ask_numeric(self, note: dict) -> tuple[bool, str]:
        # ASI-style prompt
        user_input = Prompt.ask(get_asi_prompt("numeric"))
        user_val = _normalize_numeric(user_input)

        # Use pre-parsed numeric answer if available
        correct_val = note.get("numeric_answer")
        if correct_val is None:
            correct_val = _normalize_numeric(note.get("back", ""))
        elif isinstance(correct_val, str):
            correct_val = _normalize_numeric(correct_val)

        # Check with tolerance using type-aware comparison
        tolerance = note.get("numeric_tolerance", 0)
        is_correct = _compare_numeric_answers(user_val, correct_val, tolerance)

        if is_correct:
            console.print(cortex_result_panel(True, str(note.get("back", ""))))
            return (True, user_input)

        # Show solution steps with ASI styling
        steps = note.get("numeric_steps") or note.get("back", "").split("\n")
        steps_content = Text()
        for i, step in enumerate(steps, 1):
            steps_content.append(f"  [{i}] ", style=STYLES["cortex_secondary"])
            steps_content.append(f"{step}\n", style=Style(color=CORTEX_THEME["white"]))

        steps_panel = Panel(
            steps_content,
            title="[bold yellow][*] SOLUTION VECTOR[/bold yellow]",
            border_style=Style(color=CORTEX_THEME["warning"]),
            box=box.HEAVY,
            subtitle=f"[dim]Source: {note.get('source_fact_basis', 'N/A')}[/dim]" if note.get("source_fact_basis") else None,
        )

        error_text = Text()
        error_text.append("[*] INCORRECT VALUE\n\n", style=STYLES["cortex_error"])
        error_text.append("Your input: ", style=STYLES["cortex_dim"])
        error_text.append(f"{user_input}\n", style=STYLES["cortex_error"])
        error_text.append("Expected: ", style=STYLES["cortex_dim"])
        error_text.append(f"{note.get('back', '')}", style=STYLES["cortex_success"])

        console.print(Panel(
            error_text,
            border_style=Style(color=CORTEX_THEME["error"]),
            box=box.HEAVY,
        ))
        console.print(steps_panel)
        return (False, user_input)

    def _ask_true_false(self, note: dict) -> tuple[bool, str]:
        """Handle True/False questions."""
        # ASI-style prompt
        response = Prompt.ask(
            get_asi_prompt("flashcard", "[T/F]"),
            choices=["t", "f", "true", "false"],
            default="t",
        ).lower()

        user_answer = "True" if response in ("t", "true") else "False"

        # Parse expected answer from back
        back = note.get("back", "").strip().lower()
        if back.startswith("true"):
            correct_answer = "True"
        elif back.startswith("false"):
            correct_answer = "False"
        elif back in ("t", "true", "yes", "correct"):
            correct_answer = "True"
        elif back in ("f", "false", "no", "incorrect"):
            correct_answer = "False"
        else:
            correct_answer = "True"  # Default

        is_correct = user_answer == correct_answer

        if is_correct:
            console.print(cortex_result_panel(True, correct_answer))
        else:
            # Include explanation if available
            explanation = note.get("explanation", "")
            console.print(cortex_result_panel(False, correct_answer, explanation))

        return (is_correct, user_answer)

    def _ask_matching(self, note: dict) -> tuple[bool, str]:
        """Handle Matching questions - pair terms with definitions."""
        pairs = note.get("pairs", [])
        if not pairs:
            console.print("[yellow]No matching pairs available[/yellow]")
            return (True, "skipped")

        # Display terms and definitions separately
        terms = [p.get("term", "") for p in pairs]
        definitions = [p.get("definition", "") for p in pairs]

        # Shuffle definitions for the challenge
        shuffled_defs = definitions.copy()
        random.shuffle(shuffled_defs)

        # Create numbered lists
        console.print("\n[bold cyan]TERMS:[/bold cyan]")
        for i, term in enumerate(terms, 1):
            console.print(f"  [{i}] {term}")

        console.print("\n[bold cyan]DEFINITIONS:[/bold cyan]")
        for i, defn in enumerate(shuffled_defs, 1):
            console.print(f"  ({chr(64+i)}) {defn}")

        # Get user matches
        console.print("\n[dim]Match each term to its definition (e.g., 1A 2B 3C)[/dim]")
        user_input = Prompt.ask(
            get_asi_prompt("matching"),
            default=""
        ).upper().strip()

        # Parse user input
        user_matches = {}
        for match in user_input.split():
            if len(match) >= 2 and match[0].isdigit():
                term_idx = int(match[0]) - 1
                def_idx = ord(match[-1]) - ord('A')
                if 0 <= term_idx < len(terms) and 0 <= def_idx < len(shuffled_defs):
                    user_matches[term_idx] = def_idx

        # Check correctness
        correct_count = 0
        for i, term in enumerate(terms):
            correct_def = definitions[i]
            shuffled_idx = shuffled_defs.index(correct_def)
            if user_matches.get(i) == shuffled_idx:
                correct_count += 1

        is_correct = correct_count == len(terms)
        score_text = f"{correct_count}/{len(terms)} correct"

        if is_correct:
            console.print(cortex_result_panel(True, score_text))
        else:
            # Show correct matches
            correct_answer = "\n".join(
                f"{i+1}. {terms[i]} -> {definitions[i]}"
                for i in range(len(terms))
            )
            console.print(cortex_result_panel(False, correct_answer))

        return (is_correct, user_input)


def _parse_module_list(raw: Optional[str], default: Iterable[int]) -> list[int]:
    if not raw:
        return list(default)
    return [int(part.strip()) for part in raw.split(",") if part.strip().isdigit()]


@cortex_app.command("start")
def cortex_start(
    mode: str = typer.Option(
        "adaptive",
        help="Session mode: adaptive or war",
        case_sensitive=False,
    ),
    modules: Optional[str] = typer.Option(
        None,
        help="Comma-separated modules (adaptive default: 1-17, war default: 11-17)",
    ),
    limit: int = typer.Option(20, help="Notes to pull into the session"),
    interactive: bool = typer.Option(
        False,
        "--interactive", "-i",
        help="Prompt for module and type selection",
    ),
):
    """Adaptive or war-mode session."""
    war_mode = mode.lower() == "war"

    # Interactive selection
    if interactive and not modules:
        console.print("\n[bold cyan]CORTEX SESSION CONFIGURATION[/bold cyan]\n")

        # Module selection
        console.print("[dim]Available modules: 1-17[/dim]")
        console.print("  [cyan]1-10[/cyan]: Fundamentals (OSI, TCP/IP, Addressing)")
        console.print("  [cyan]11-17[/cyan]: Advanced (Routing, Switching, Security)")
        console.print()

        modules_input = Prompt.ask(
            "[cyan]>_ SELECT MODULES[/cyan]",
            default="1-17" if not war_mode else "11-17",
        )

        # Parse range notation (e.g., "1-5" or "1,3,5" or "1-5,10-12")
        module_list = []
        for part in modules_input.split(","):
            part = part.strip()
            if "-" in part:
                try:
                    start, end = part.split("-")
                    module_list.extend(range(int(start), int(end) + 1))
                except ValueError:
                    pass
            elif part.isdigit():
                module_list.append(int(part))

        if not module_list:
            module_list = list(range(11, 18) if war_mode else range(1, 18))

        console.print(f"[dim]Selected modules: {sorted(set(module_list))}[/dim]\n")
    else:
        default_modules = range(11, 18) if war_mode else range(1, 18)
        module_list = _parse_module_list(modules, default=default_modules)

    session = CortexSession(modules=module_list, limit=limit, war_mode=war_mode)
    session.run()


@cortex_app.command("war")
def cortex_war(
    limit: int = typer.Option(25, help="Notes to pull into the cram deck"),
):
    """Alias for war mode."""
    module_list = list(range(11, 18))
    session = CortexSession(modules=module_list, limit=limit, war_mode=True)
    session.run()


# =============================================================================
# GOOGLE CALENDAR COMMANDS
# =============================================================================

@cortex_app.command("schedule")
def cortex_schedule(
    time_str: str = typer.Option(
        ...,
        "--time", "-t",
        help="When to schedule (e.g., 'tomorrow 9am', '2025-12-06 14:00')",
    ),
    duration: int = typer.Option(
        60,
        "--duration", "-d",
        help="Session duration in minutes",
    ),
    modules: Optional[str] = typer.Option(
        None,
        "--modules", "-m",
        help="Comma-separated modules (default: 11-17)",
    ),
    cram: bool = typer.Option(
        False,
        "--cram",
        help="Use cram mode modules (11-17)",
    ),
):
    """
    Schedule a study session on Google Calendar.

    Examples:
        nls cortex schedule --time "tomorrow 9am" --duration 60
        nls cortex schedule -t "2025-12-06 14:00" -d 90 --modules 11,12,13
        nls cortex schedule -t "saturday 10am" --cram
    """
    # Parse the time string
    try:
        start_time = date_parser.parse(time_str, fuzzy=True)
        # If time is in the past today, assume tomorrow
        if start_time < datetime.now():
            start_time += timedelta(days=1)
    except Exception as e:
        console.print(Panel(
            f"[bold red]Could not parse time:[/bold red] {time_str}\n\n"
            "Try formats like:\n"
            "  - 'tomorrow 9am'\n"
            "  - 'saturday 14:00'\n"
            "  - '2025-12-06 10:00'",
            border_style=Style(color=CORTEX_THEME["error"]),
            box=box.HEAVY,
        ))
        raise typer.Exit(code=1)

    # Determine modules
    if cram:
        module_list = list(range(11, 18))
    elif modules:
        module_list = _parse_module_list(modules, default=range(11, 18))
    else:
        module_list = list(range(11, 18))

    # Initialize calendar
    calendar = CortexCalendar()

    if not calendar.is_available:
        console.print(Panel(
            "[bold red]Google Calendar libraries not installed.[/bold red]\n\n"
            "Run: pip install google-auth google-auth-oauthlib google-api-python-client",
            border_style=Style(color=CORTEX_THEME["error"]),
            box=box.HEAVY,
        ))
        raise typer.Exit(code=1)

    if not calendar.has_credentials:
        console.print(calendar.get_setup_instructions())
        raise typer.Exit(code=1)

    # Authenticate
    console.print(Panel(
        "[cyan]Connecting to Google Calendar...[/cyan]",
        border_style=Style(color=CORTEX_THEME["primary"]),
    ))

    if not calendar.authenticate():
        console.print(Panel(
            "[bold red]Authentication failed.[/bold red]\n\n"
            "Check that credentials.json is valid and try again.",
            border_style=Style(color=CORTEX_THEME["error"]),
            box=box.HEAVY,
        ))
        raise typer.Exit(code=1)

    # Book the session
    event_id = calendar.book_study_session(
        start_time=start_time,
        duration_minutes=duration,
        modules=module_list,
        title="Cortex War Room",
    )

    if event_id:
        modules_str = ", ".join(str(m) for m in module_list)
        end_time = start_time + timedelta(minutes=duration)

        result_text = Text()
        result_text.append("[*] SESSION SCHEDULED [*]\n\n", style=STYLES["cortex_primary"])
        result_text.append("Start: ", style=STYLES["cortex_dim"])
        result_text.append(f"{start_time.strftime('%A, %B %d at %I:%M %p')}\n", style=STYLES["cortex_accent"])
        result_text.append("Duration: ", style=STYLES["cortex_dim"])
        result_text.append(f"{duration} minutes\n", style=STYLES["cortex_accent"])
        result_text.append("Modules: ", style=STYLES["cortex_dim"])
        result_text.append(f"{modules_str}\n\n", style=STYLES["cortex_accent"])
        result_text.append("Command to start:\n", style=STYLES["cortex_dim"])
        result_text.append(f"  nls cortex start --war --modules {modules_str}", style=STYLES["cortex_success"])

        console.print(Panel(
            Align.center(result_text),
            border_style=Style(color=CORTEX_THEME["success"]),
            box=box.DOUBLE,
            padding=(1, 2),
        ))
    else:
        console.print(Panel(
            "[bold red]Failed to create calendar event.[/bold red]",
            border_style=Style(color=CORTEX_THEME["error"]),
            box=box.HEAVY,
        ))
        raise typer.Exit(code=1)


@cortex_app.command("agenda")
def cortex_agenda(
    days: int = typer.Option(7, "--days", "-d", help="Days to look ahead"),
):
    """
    Show upcoming scheduled Cortex sessions.

    Examples:
        nls cortex agenda
        nls cortex agenda --days 14
    """
    calendar = CortexCalendar()

    if not calendar.is_available:
        console.print(Panel(
            "[bold yellow]Google Calendar not configured.[/bold yellow]\n\n"
            "Run: nls cortex schedule --help",
            border_style=Style(color=CORTEX_THEME["warning"]),
        ))
        return

    if not calendar.has_credentials:
        console.print(calendar.get_setup_instructions())
        return

    if not calendar.authenticate():
        console.print(Panel(
            "[bold red]Authentication failed.[/bold red]",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        return

    sessions = calendar.get_upcoming_sessions(days=days)

    if not sessions:
        console.print(Panel(
            f"[dim]No Cortex sessions scheduled in the next {days} days.[/dim]\n\n"
            "Schedule one with:\n"
            "  nls cortex schedule --time 'tomorrow 9am' --duration 60",
            title="[bold cyan][*] CORTEX AGENDA[/bold cyan]",
            border_style=Style(color=CORTEX_THEME["secondary"]),
            box=box.HEAVY,
        ))
        return

    # Build agenda table
    table = Table(
        title=f"[bold cyan][*] CORTEX SESSIONS (Next {days} days)[/bold cyan]",
        box=box.HEAVY,
        border_style=Style(color=CORTEX_THEME["primary"]),
    )
    table.add_column("DATE", style=Style(color=CORTEX_THEME["accent"]))
    table.add_column("TIME", style=Style(color=CORTEX_THEME["white"]))
    table.add_column("DURATION", justify="right", style=Style(color=CORTEX_THEME["secondary"]))
    table.add_column("TITLE", style=Style(color=CORTEX_THEME["warning"]))

    for session in sessions:
        start = session.get("start")
        end = session.get("end")
        title = session.get("title", "Cortex Session")

        if start:
            try:
                start_dt = date_parser.parse(start)
                end_dt = date_parser.parse(end) if end else start_dt + timedelta(hours=1)
                duration = int((end_dt - start_dt).total_seconds() / 60)

                table.add_row(
                    start_dt.strftime("%a %b %d"),
                    start_dt.strftime("%I:%M %p"),
                    f"{duration} min",
                    title.replace("[*] ", ""),
                )
            except Exception:
                table.add_row("?", "?", "?", title)

    console.print(table)


# =============================================================================
# PROGRESS & STATS COMMANDS
# =============================================================================

def _format_progress_bar(score: float, width: int = 10) -> str:
    """Format a progress bar (ASCII-safe for Windows console)."""
    filled = int(score / 100 * width)
    empty = width - filled
    return "#" * filled + "-" * empty


@cortex_app.command("stats")
def cortex_stats():
    """
    Show comprehensive study statistics with ASI styling.

    Displays:
    - Section progress (total, completed, completion rate)
    - Atom mastery breakdown (mastered, learning, struggling, new)
    - Overall mastery score and total reviews
    - Session history (if available)
    """
    study_service = StudyService()

    try:
        stats = study_service.get_study_stats()
    except Exception as e:
        console.print(Panel(
            f"[bold red]Error loading stats:[/bold red] {e}",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        return

    # Header
    header = Text()
    header.append("[*] CORTEX TELEMETRY [*]", style=STYLES["cortex_primary"])

    console.print(Panel(
        Align.center(header),
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.DOUBLE,
    ))

    # Section Progress Table
    s = stats["sections"]
    section_table = Table(
        title="[bold cyan]SECTION PROGRESS[/bold cyan]",
        box=box.HEAVY,
        border_style=Style(color=CORTEX_THEME["secondary"]),
        show_header=False,
    )
    section_table.add_column("Metric", style=Style(color=CORTEX_THEME["dim"]))
    section_table.add_column("Value", justify="right", style=Style(color=CORTEX_THEME["white"]))

    section_table.add_row("Total Sections", str(s["total"]))
    section_table.add_row("Completed", f"[green]{s['completed']}[/green]")
    section_table.add_row("Completion Rate", f"[cyan]{s['completion_rate']}%[/cyan]")

    console.print(section_table)

    # Atom Mastery Table
    a = stats["atoms"]
    atom_table = Table(
        title="[bold cyan]ATOM MASTERY[/bold cyan]",
        box=box.HEAVY,
        border_style=Style(color=CORTEX_THEME["secondary"]),
        show_header=False,
    )
    atom_table.add_column("Status", style=Style(color=CORTEX_THEME["dim"]))
    atom_table.add_column("Count", justify="right")

    atom_table.add_row("Total Atoms", str(a["total"]))
    atom_table.add_row("[green]Mastered[/green]", f"[green]{a['mastered']}[/green]")
    atom_table.add_row("[yellow]Learning[/yellow]", f"[yellow]{a['learning']}[/yellow]")
    atom_table.add_row("[red]Struggling[/red]", f"[red]{a['struggling']}[/red]")
    atom_table.add_row("[dim]New[/dim]", f"[dim]{a['new']}[/dim]")

    console.print(atom_table)

    # Overall Mastery
    mastery = stats["mastery"]["average"]
    bar = _format_progress_bar(mastery, 20)
    mastery_color = CORTEX_THEME["success"] if mastery >= 80 else CORTEX_THEME["warning"] if mastery >= 60 else CORTEX_THEME["error"]

    mastery_text = Text()
    mastery_text.append("OVERALL MASTERY: ", style=STYLES["cortex_dim"])
    mastery_text.append(f"{bar} ", style=Style(color=mastery_color))
    mastery_text.append(f"{mastery:.1f}%", style=Style(color=mastery_color, bold=True))
    mastery_text.append(f"\n\nTotal Reviews: ", style=STYLES["cortex_dim"])
    mastery_text.append(f"{stats['mastery']['total_reviews']}", style=Style(color=CORTEX_THEME["accent"]))

    console.print(Panel(
        Align.center(mastery_text),
        border_style=Style(color=mastery_color),
        box=box.HEAVY,
    ))


@cortex_app.command("today")
def cortex_today():
    """
    Show today's study session summary.

    Displays:
    - Due reviews count
    - New atoms available
    - Remediation needs
    - Current module/section progress
    - Study streak
    """
    study_service = StudyService()

    try:
        summary = study_service.get_daily_summary()
    except Exception as e:
        console.print(Panel(
            f"[bold red]Error loading summary:[/bold red] {e}",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        return

    # Build content
    content = Text()
    content.append("[*] DAILY BRIEFING [*]\n\n", style=STYLES["cortex_primary"])

    content.append(f"DATE: ", style=STYLES["cortex_dim"])
    content.append(f"{summary.date.strftime('%B %d, %Y')}\n\n", style=Style(color=CORTEX_THEME["accent"]))

    # Due Reviews
    content.append("DUE REVIEWS: ", style=Style(color=CORTEX_THEME["warning"]))
    content.append(f"{summary.due_reviews} cards", style=Style(color=CORTEX_THEME["white"], bold=True))
    if summary.due_reviews > 0:
        content.append(f" (~{summary.due_reviews // 2} min)\n", style=STYLES["cortex_dim"])
    else:
        content.append(" - All caught up!\n", style=STYLES["cortex_success"])

    # New Content
    content.append("NEW CONTENT: ", style=Style(color=CORTEX_THEME["success"]))
    content.append(f"{summary.new_atoms_available} atoms available\n", style=Style(color=CORTEX_THEME["white"], bold=True))

    # Remediation
    if summary.remediation_sections > 0:
        content.append("REMEDIATION: ", style=Style(color=CORTEX_THEME["error"]))
        content.append(f"{summary.remediation_atoms} cards ", style=Style(color=CORTEX_THEME["white"], bold=True))
        content.append(f"from {summary.remediation_sections} sections\n", style=STYLES["cortex_dim"])
    else:
        content.append("REMEDIATION: ", style=Style(color=CORTEX_THEME["success"]))
        content.append("None needed\n", style=STYLES["cortex_success"])

    content.append("\n")

    # Current Progress
    content.append("CURRENT: ", style=STYLES["cortex_dim"])
    content.append(f"Module {summary.current_module} - Section {summary.current_section}\n", style=Style(color=CORTEX_THEME["accent"]))

    # Mastery Bar
    bar = _format_progress_bar(summary.overall_mastery, 15)
    mastery_color = CORTEX_THEME["success"] if summary.overall_mastery >= 80 else CORTEX_THEME["warning"]
    content.append("MASTERY: ", style=STYLES["cortex_dim"])
    content.append(f"{bar} {summary.overall_mastery:.0f}%\n", style=Style(color=mastery_color))

    # Streak
    if summary.streak_days > 0:
        content.append("\n")
        content.append(f"[FIRE] STREAK: {summary.streak_days} days", style=Style(color=CORTEX_THEME["warning"], bold=True))

    # Estimated Time
    content.append(f"\n\nESTIMATED SESSION: ", style=STYLES["cortex_dim"])
    content.append(f"{summary.estimated_minutes} minutes", style=Style(color=CORTEX_THEME["accent"]))

    console.print(Panel(
        content,
        title="[bold cyan][*] CORTEX[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.HEAVY,
        padding=(1, 2),
    ))


@cortex_app.command("path")
def cortex_path():
    """
    Show full CCNA learning path with progress.

    Displays all 17 modules with:
    - Mastery percentage and progress bar
    - Section completion counts
    - Atom breakdown (mastered/learning/struggling/new)
    - Remediation warnings
    """
    study_service = StudyService()

    try:
        modules = study_service.get_module_summaries()
    except Exception as e:
        console.print(Panel(
            f"[bold red]Error loading path:[/bold red] {e}",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        return

    if not modules:
        console.print(Panel(
            "[yellow]No module data found.[/yellow]",
            border_style=Style(color=CORTEX_THEME["warning"]),
        ))
        return

    # Header
    console.print(Panel(
        Align.center(Text("[*] CCNA LEARNING PATH [*]", style=STYLES["cortex_primary"])),
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.DOUBLE,
    ))

    for mod in modules:
        # Determine status
        if mod.sections_needing_remediation > 0:
            status_icon = "[red][*] REMEDIATION[/red]"
            border_color = CORTEX_THEME["error"]
        elif mod.avg_mastery >= 90:
            status_icon = "[green][*] MASTERED[/green]"
            border_color = CORTEX_THEME["success"]
        elif mod.avg_mastery >= 70:
            status_icon = "[yellow][*] LEARNING[/yellow]"
            border_color = CORTEX_THEME["warning"]
        else:
            status_icon = "[dim][*] NEW[/dim]"
            border_color = CORTEX_THEME["dim"]

        bar = _format_progress_bar(mod.avg_mastery, 15)

        content = Text()
        content.append(f"{bar} ", style=Style(color=border_color))
        content.append(f"{mod.avg_mastery:.0f}%  ", style=Style(color=border_color, bold=True))
        content.append(f"({mod.sections_completed}/{mod.total_sections} sections)\n", style=STYLES["cortex_dim"])

        if mod.atoms_total > 0:
            content.append(f"[green]{mod.atoms_mastered}[/green] mastered | ", style="")
            content.append(f"[yellow]{mod.atoms_learning}[/yellow] learning | ", style="")
            content.append(f"[red]{mod.atoms_struggling}[/red] struggling | ", style="")
            content.append(f"[dim]{mod.atoms_new}[/dim] new", style="")

        console.print(Panel(
            content,
            title=f"[bold cyan]Module {mod.module_number}:[/bold cyan] {mod.title}  {status_icon}",
            border_style=Style(color=border_color),
            box=box.ROUNDED,
            padding=(0, 1),
        ))


@cortex_app.command("remediation")
def cortex_remediation():
    """
    Show sections needing remediation.

    Lists all sections with low mastery scores that need
    focused review, sorted by priority.
    """
    study_service = StudyService()

    try:
        sections = study_service.get_remediation_sections()
    except Exception as e:
        console.print(Panel(
            f"[bold red]Error loading remediation:[/bold red] {e}",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        return

    if not sections:
        console.print(Panel(
            Align.center(Text("[*] ALL CLEAR [*]\n\nNo sections need remediation!\nGreat job keeping up with your studies.", style=STYLES["cortex_success"])),
            border_style=Style(color=CORTEX_THEME["success"]),
            box=box.DOUBLE,
        ))
        return

    # Header
    header = Text()
    header.append(f"[*] REMEDIATION QUEUE: {len(sections)} sections [*]", style=STYLES["cortex_error"])

    console.print(Panel(
        Align.center(header),
        border_style=Style(color=CORTEX_THEME["error"]),
        box=box.DOUBLE,
    ))

    # Build table
    table = Table(
        box=box.HEAVY,
        border_style=Style(color=CORTEX_THEME["error"]),
    )
    table.add_column("SECTION", style=Style(color=CORTEX_THEME["accent"]))
    table.add_column("TITLE", max_width=40)
    table.add_column("MASTERY", justify="right")
    table.add_column("REASON", style=Style(color=CORTEX_THEME["warning"]))

    for section in sections[:15]:
        bar = _format_progress_bar(section.mastery_score, 8)
        table.add_row(
            section.section_id,
            section.title[:38] + "..." if len(section.title) > 38 else section.title,
            f"{bar} {section.mastery_score:.0f}%",
            section.remediation_reason or "combined",
        )

    console.print(table)

    if len(sections) > 15:
        console.print(f"\n[dim]... and {len(sections) - 15} more sections[/dim]")

    # Suggest action
    console.print(Panel(
        f"Run [cyan]nls cortex start --mode war[/cyan] to focus on weak areas",
        border_style=Style(color=CORTEX_THEME["secondary"]),
    ))


@cortex_app.command("module")
def cortex_module(
    module_num: int = typer.Argument(..., help="Module number (1-17)"),
    expand: bool = typer.Option(False, "--expand", "-e", help="Expand with prerequisite graph"),
):
    """
    Show detailed progress for a specific module.

    Examples:
        nls cortex module 11
        nls cortex module 11 --expand
    """
    if module_num < 1 or module_num > 17:
        console.print(Panel(
            "[bold red]Module must be between 1 and 17[/bold red]",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        return

    study_service = StudyService()

    try:
        sections = study_service.get_section_details(module_num)
    except Exception as e:
        console.print(Panel(
            f"[bold red]Error loading module:[/bold red] {e}",
            border_style=Style(color=CORTEX_THEME["error"]),
        ))
        return

    if not sections:
        console.print(Panel(
            f"[yellow]No sections found for Module {module_num}[/yellow]",
            border_style=Style(color=CORTEX_THEME["warning"]),
        ))
        return

    module_titles = {
        1: "Networking Today", 2: "Basic Switch and End Device Configuration",
        3: "Protocols and Models", 4: "Physical Layer", 5: "Number Systems",
        6: "Data Link Layer", 7: "Ethernet Switching", 8: "Network Layer",
        9: "Address Resolution", 10: "Basic Router Configuration",
        11: "IPv4 Addressing", 12: "IPv6 Addressing", 13: "ICMP",
        14: "Transport Layer", 15: "Application Layer",
        16: "Network Security Fundamentals", 17: "Build a Small Network",
    }

    title = module_titles.get(module_num, f"Module {module_num}")

    # Header
    console.print(Panel(
        Align.center(Text(f"[*] MODULE {module_num}: {title} [*]", style=STYLES["cortex_primary"])),
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.DOUBLE,
    ))

    # Show sections
    for section in sections:
        bar = _format_progress_bar(section.mastery_score, 10)

        if section.is_mastered:
            status = "[green][*] MASTERED[/green]"
            border_color = CORTEX_THEME["success"]
        elif section.needs_remediation:
            status = "[red][*] REMEDIATION[/red]"
            border_color = CORTEX_THEME["error"]
        else:
            status = ""
            border_color = CORTEX_THEME["secondary"]

        content = Text()
        content.append(f"{bar} {section.mastery_score:.0f}%\n", style=Style(color=border_color))

        if section.atoms_total > 0:
            content.append(f"[green]{section.atoms_mastered}[/green]/", style="")
            content.append(f"[yellow]{section.atoms_learning}[/yellow]/", style="")
            content.append(f"[red]{section.atoms_struggling}[/red]/", style="")
            content.append(f"[dim]{section.atoms_new}[/dim] atoms", style="")

        if section.needs_remediation and section.remediation_reason:
            content.append(f"\n[red]Reason: {section.remediation_reason}[/red]", style="")

        console.print(Panel(
            content,
            title=f"[cyan]{section.section_id}[/cyan] {section.title}  {status}",
            border_style=Style(color=border_color),
            box=box.ROUNDED,
            padding=(0, 1),
        ))

    # Show expansion if requested
    if expand:
        console.print(Panel(
            "[dim]Prerequisite expansion coming soon...[/dim]",
            border_style=Style(color=CORTEX_THEME["dim"]),
        ))


# =============================================================================
# CORTEX 2.0: NEUROMORPHIC COMMANDS
# =============================================================================

@cortex_app.command("persona")
def cortex_persona():
    """
    Show your learner persona profile.

    Displays the dynamic cognitive profile including:
    - Processing speed classification
    - Knowledge type strengths/weaknesses
    - Mechanism effectiveness
    - Chronotype and peak hours
    - Learning velocity and acceleration
    """
    from src.adaptive.persona_service import PersonaService

    service = PersonaService()
    persona = service.get_persona()

    # Build content
    content = Text()
    content.append("[*] LEARNER PERSONA [*]\n\n", style=STYLES["cortex_primary"])

    # Processing Speed
    content.append("PROCESSING: ", style=STYLES["cortex_dim"])
    speed_display = persona.processing_speed.value.replace("_", " ").title()
    content.append(f"{speed_display}\n", style=Style(color=CORTEX_THEME["accent"], bold=True))

    # Chronotype
    content.append("CHRONOTYPE: ", style=STYLES["cortex_dim"])
    chrono_display = persona.chronotype.value.replace("_", " ").title()
    content.append(f"{chrono_display} ", style=Style(color=CORTEX_THEME["white"]))
    content.append(f"(peak: {persona.peak_performance_hour}:00)\n\n", style=STYLES["cortex_dim"])

    # Knowledge Strengths
    content.append("KNOWLEDGE TYPE STRENGTHS:\n", style=Style(color=CORTEX_THEME["secondary"]))
    for ktype in ["factual", "conceptual", "procedural", "strategic"]:
        score = getattr(persona, f"strength_{ktype}")
        bar = _format_progress_bar(score * 100, 10)
        color = CORTEX_THEME["success"] if score > 0.7 else CORTEX_THEME["warning"] if score > 0.4 else CORTEX_THEME["error"]
        content.append(f"  {ktype.capitalize():12s} ", style=STYLES["cortex_dim"])
        content.append(f"{bar} {score:.0%}\n", style=Style(color=color))

    content.append("\n")

    # Mechanism Effectiveness
    content.append("MECHANISM EFFECTIVENESS:\n", style=Style(color=CORTEX_THEME["secondary"]))
    for mech in ["retrieval", "discrimination", "elaboration"]:
        score = getattr(persona, f"effectiveness_{mech}")
        bar = _format_progress_bar(score * 100, 10)
        color = CORTEX_THEME["success"] if score > 0.7 else CORTEX_THEME["warning"] if score > 0.4 else CORTEX_THEME["error"]
        content.append(f"  {mech.capitalize():12s} ", style=STYLES["cortex_dim"])
        content.append(f"{bar} {score:.0%}\n", style=Style(color=color))

    content.append("\n")

    # Calibration
    content.append("CALIBRATION: ", style=STYLES["cortex_dim"])
    if persona.calibration_score > 0.65:
        content.append("Overconfident ", style=Style(color=CORTEX_THEME["warning"]))
        content.append("(needs more challenge)\n", style=STYLES["cortex_dim"])
    elif persona.calibration_score < 0.35:
        content.append("Underconfident ", style=Style(color=CORTEX_THEME["accent"]))
        content.append("(needs encouragement)\n", style=STYLES["cortex_dim"])
    else:
        content.append("Well-calibrated\n", style=Style(color=CORTEX_THEME["success"]))

    # Velocity
    content.append("\nLEARNING VELOCITY: ", style=STYLES["cortex_dim"])
    content.append(f"{persona.current_velocity:.1f} atoms/hour ", style=Style(color=CORTEX_THEME["accent"], bold=True))
    trend_color = CORTEX_THEME["success"] if persona.velocity_trend == "improving" else CORTEX_THEME["warning"]
    content.append(f"({persona.velocity_trend})\n", style=Style(color=trend_color))

    # Stats
    content.append(f"\nTOTAL STUDY: ", style=STYLES["cortex_dim"])
    content.append(f"{persona.total_study_hours:.1f} hours  ", style=Style(color=CORTEX_THEME["white"]))
    content.append(f"STREAK: {persona.current_streak_days} days", style=Style(color=CORTEX_THEME["warning"]))

    console.print(Panel(
        content,
        title="[bold cyan][*] CORTEX PERSONA[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.HEAVY,
        padding=(1, 2),
    ))


@cortex_app.command("diagnose")
def cortex_diagnose(
    atom_id: str = typer.Argument(None, help="Atom ID to diagnose (optional)"),
):
    """
    Run cognitive diagnosis on recent performance.

    Analyzes your recent interactions to identify:
    - Cognitive patterns (encoding, retrieval, discrimination errors)
    - Struggle patterns requiring remediation
    - Cognitive load levels
    - Recommended actions
    """
    from src.adaptive.neuro_model import (
        detect_struggle_pattern,
        compute_cognitive_load,
        CognitiveState,
        FailMode,
    )
    from src.adaptive.cognitive_model import diagnose_error

    study_service = StudyService()

    # Get recent history (mock - would come from study_service)
    # For now, show the diagnostic framework
    content = Text()
    content.append("[*] COGNITIVE DIAGNOSIS [*]\n\n", style=STYLES["cortex_primary"])

    content.append("FAIL MODE DETECTION:\n", style=Style(color=CORTEX_THEME["secondary"]))
    fail_modes = [
        ("ENCODING", "Hippocampus", "Memory never formed - needs elaboration"),
        ("RETRIEVAL", "CA3/CA1", "Memory exists but weak pathway - needs practice"),
        ("DISCRIMINATION", "Dentate Gyrus", "Confusing similar items - needs contrast training"),
        ("INTEGRATION", "P-FIT Network", "Facts don't connect - needs worked examples"),
        ("EXECUTIVE", "Prefrontal Cortex", "Impulsive/careless - needs slow down"),
        ("FATIGUE", "Global", "Cognitive exhaustion - needs rest"),
    ]

    for mode, region, remedy in fail_modes:
        content.append(f"  {mode:14s} ", style=Style(color=CORTEX_THEME["accent"]))
        content.append(f"({region:16s}) ", style=STYLES["cortex_dim"])
        content.append(f"{remedy}\n", style=Style(color=CORTEX_THEME["white"]))

    content.append("\n")
    content.append("Run a study session to collect diagnostic data.\n", style=STYLES["cortex_dim"])
    content.append("Diagnosis happens automatically during learning.", style=STYLES["cortex_dim"])

    console.print(Panel(
        content,
        title="[bold cyan][*] NEUROMORPHIC DIAGNOSIS[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["secondary"]),
        box=box.HEAVY,
        padding=(1, 2),
    ))


@cortex_app.command("plm")
def cortex_plm(
    category: str = typer.Argument(None, help="Category to train on"),
    duration: int = typer.Option(5, "--duration", "-d", help="Training duration in minutes"),
):
    """
    Start a Perceptual Learning Module (PLM) drill.

    PLM trains rapid pattern recognition (<1000ms response times):
    - Classification: "Is this X or Y?"
    - Discrimination: "What type is this?"
    - Builds automatic recognition, not conscious recall

    Examples:
        nls cortex plm "chain rule"
        nls cortex plm --duration 10
    """
    from src.adaptive.perceptual_learning import PLMEngine, PLM_TARGET_MS

    content = Text()
    content.append("[*] PERCEPTUAL LEARNING MODULE [*]\n\n", style=STYLES["cortex_primary"])

    content.append("GOAL: ", style=STYLES["cortex_dim"])
    content.append(f"Response time < {PLM_TARGET_MS}ms with 90%+ accuracy\n\n", style=Style(color=CORTEX_THEME["accent"]))

    content.append("This mode trains AUTOMATIC pattern recognition:\n", style=Style(color=CORTEX_THEME["white"]))
    content.append("- Visual cortex processing, not frontal deliberation\n", style=STYLES["cortex_dim"])
    content.append("- High volume, rapid presentation\n", style=STYLES["cortex_dim"])
    content.append("- Interleaved confusable pairs\n", style=STYLES["cortex_dim"])

    if category:
        content.append(f"\nCategory: {category}\n", style=Style(color=CORTEX_THEME["accent"]))

    content.append(f"\nDuration: {duration} minutes\n", style=STYLES["cortex_dim"])
    content.append("\n[PLM session implementation coming soon]", style=Style(color=CORTEX_THEME["warning"]))

    console.print(Panel(
        content,
        title="[bold cyan][*] PLM DRILL[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.HEAVY,
        padding=(1, 2),
    ))


@cortex_app.command("tutor")
def cortex_tutor(
    topic: str = typer.Argument(None, help="Topic to discuss"),
):
    """
    Start a Socratic tutoring session with AI.

    Uses Gemini AI for personalized tutoring:
    - Guides you to answers, doesn't give them
    - Adapts to your learner persona
    - Scaffolding that fades over time

    Examples:
        nls cortex tutor "limits"
        nls cortex tutor "why does integration by parts work"
    """
    from src.integrations.vertex_tutor import VertexTutor, get_quick_hint
    from src.adaptive.neuro_model import FailMode

    content = Text()
    content.append("[*] SOCRATIC TUTOR [*]\n\n", style=STYLES["cortex_primary"])

    content.append("The AI tutor uses your persona to personalize explanations.\n\n", style=Style(color=CORTEX_THEME["white"]))

    content.append("TUTORING MODES:\n", style=Style(color=CORTEX_THEME["secondary"]))
    content.append("  SOCRATIC     - Guides with questions\n", style=STYLES["cortex_dim"])
    content.append("  ELABORATIVE  - Explains differently\n", style=STYLES["cortex_dim"])
    content.append("  CONTRASTIVE  - Compares similar concepts\n", style=STYLES["cortex_dim"])
    content.append("  PROCEDURAL   - Step-by-step walkthrough\n", style=STYLES["cortex_dim"])

    if topic:
        content.append(f"\nTopic: {topic}\n", style=Style(color=CORTEX_THEME["accent"]))

    content.append("\n[AI tutor integration coming soon]", style=Style(color=CORTEX_THEME["warning"]))
    content.append("\nRequires: GOOGLE_API_KEY environment variable", style=STYLES["cortex_dim"])

    console.print(Panel(
        content,
        title="[bold cyan][*] AI TUTOR[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.HEAVY,
        padding=(1, 2),
    ))


@cortex_app.command("smart-schedule")
def cortex_smart_schedule(
    days: int = typer.Option(7, "--days", "-d", help="Days to schedule"),
    hours: int = typer.Option(1, "--hours", "-h", help="Study hours per day"),
):
    """
    Generate an optimal study schedule based on your persona.

    Uses your chronotype and peak hours to:
    - Block optimal cognitive windows
    - Avoid low-energy periods
    - Balance deep work and review
    - Integrate with Google Calendar

    Examples:
        nls cortex smart-schedule --days 7 --hours 2
    """
    from src.adaptive.persona_service import PersonaService
    from src.integrations.google_calendar import CortexCalendar, StudyBlockType

    service = PersonaService()
    persona = service.get_persona()
    calendar = CortexCalendar()

    content = Text()
    content.append("[*] SMART SCHEDULING [*]\n\n", style=STYLES["cortex_primary"])

    content.append("PERSONA-BASED OPTIMIZATION:\n", style=Style(color=CORTEX_THEME["secondary"]))
    content.append(f"  Chronotype: {persona.chronotype.value.replace('_', ' ').title()}\n", style=STYLES["cortex_dim"])
    content.append(f"  Peak Hour: {persona.peak_performance_hour}:00\n", style=STYLES["cortex_dim"])
    content.append(f"  Low Energy: {persona.low_energy_hours}\n\n", style=STYLES["cortex_dim"])

    content.append("RECOMMENDED SCHEDULE:\n", style=Style(color=CORTEX_THEME["secondary"]))

    # Generate recommendations
    peak = persona.peak_performance_hour
    for day in range(min(days, 3)):  # Show first 3 days
        day_name = ["Today", "Tomorrow", "Day 3"][day]
        content.append(f"\n{day_name}:\n", style=Style(color=CORTEX_THEME["accent"]))
        content.append(f"  {peak}:00-{peak+1}:00  ", style=Style(color=CORTEX_THEME["white"]))
        content.append("DEEP WORK (new material)\n", style=Style(color=CORTEX_THEME["success"]))
        if hours > 1:
            review_hour = peak + 4 if peak + 4 < 22 else peak - 3
            content.append(f"  {review_hour}:00-{review_hour+1}:00  ", style=Style(color=CORTEX_THEME["white"]))
            content.append("REVIEW (spaced repetition)\n", style=Style(color=CORTEX_THEME["warning"]))

    content.append("\n")

    if calendar.is_available and calendar.has_credentials:
        content.append("Google Calendar: ", style=STYLES["cortex_dim"])
        content.append("Connected\n", style=Style(color=CORTEX_THEME["success"]))
        content.append("Run with --book to add events to calendar", style=STYLES["cortex_dim"])
    else:
        content.append("Google Calendar: ", style=STYLES["cortex_dim"])
        content.append("Not configured\n", style=Style(color=CORTEX_THEME["warning"]))
        content.append("Run: nls cortex schedule --help for setup", style=STYLES["cortex_dim"])

    console.print(Panel(
        content,
        title="[bold cyan][*] SMART SCHEDULE[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.HEAVY,
        padding=(1, 2),
    ))


@cortex_app.command("force-z")
def cortex_force_z():
    """
    Check for prerequisite gaps (Force Z analysis).

    Analyzes your knowledge graph to find:
    - Concepts you're trying to learn (X)
    - Prerequisites you're missing (Z)
    - Backtracking recommendations

    The "Force Z" algorithm ensures foundational knowledge
    is solid before building on it.
    """
    from src.adaptive.scheduler_rl import should_force_z, PREREQUISITE_THRESHOLD

    content = Text()
    content.append("[*] FORCE Z ANALYSIS [*]\n\n", style=STYLES["cortex_primary"])

    content.append("ALGORITHM:\n", style=Style(color=CORTEX_THEME["secondary"]))
    content.append("If trying to learn X but prerequisite Z has\n", style=STYLES["cortex_dim"])
    content.append(f"mastery < {PREREQUISITE_THRESHOLD:.0%}, FORCE BACKTRACK to Z.\n\n", style=STYLES["cortex_dim"])

    content.append("WHY THIS MATTERS:\n", style=Style(color=CORTEX_THEME["secondary"]))
    content.append("Building on weak foundations leads to:\n", style=Style(color=CORTEX_THEME["white"]))
    content.append("  - Integration errors (P-FIT failure)\n", style=STYLES["cortex_dim"])
    content.append("  - Increased cognitive load\n", style=STYLES["cortex_dim"])
    content.append("  - Frustration and abandonment\n\n", style=STYLES["cortex_dim"])

    content.append("During sessions, Force Z activates automatically.\n", style=Style(color=CORTEX_THEME["accent"]))
    content.append("The scheduler will backtrack when needed.", style=STYLES["cortex_dim"])

    console.print(Panel(
        content,
        title="[bold cyan][*] FORCE Z[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.HEAVY,
        padding=(1, 2),
    ))


@cortex_app.command("struggle")
def cortex_struggle(
    modules: Optional[str] = typer.Option(
        None,
        "--modules", "-m",
        help="Comma-separated modules you struggle with (e.g., 11,12,14)",
    ),
    show: bool = typer.Option(
        False,
        "--show", "-s",
        help="Show current struggle schema",
    ),
    reset: bool = typer.Option(
        False,
        "--reset",
        help="Reset all struggle data",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive", "-i",
        help="Interactive mode for entering struggles",
    ),
):
    """
    Set or view CCNA modules and submodules you struggle with.

    The struggle schema helps the adaptive scheduler prioritize
    remediation and customize the learning path.

    Examples:
        nls cortex struggle --show
        nls cortex struggle --modules 11,12,14
        nls cortex struggle --interactive
        nls cortex struggle --reset
    """
    import json
    from pathlib import Path

    # Store struggle data in user's config directory
    struggle_file = Path.home() / ".cortex" / "struggle_schema.json"
    struggle_file.parent.mkdir(parents=True, exist_ok=True)

    # Load existing schema
    struggle_schema: dict[int, float] = {}
    if struggle_file.exists():
        try:
            with open(struggle_file, "r") as f:
                data = json.load(f)
                struggle_schema = {int(k): float(v) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError):
            pass

    # Reset mode
    if reset:
        if struggle_file.exists():
            struggle_file.unlink()
        console.print(Panel(
            "[green]Struggle schema reset successfully.[/green]",
            border_style=Style(color=CORTEX_THEME["success"]),
        ))
        return

    # Show mode
    if show or (not modules and not interactive and not reset):
        if not struggle_schema:
            console.print(Panel(
                "[dim]No struggle data recorded.[/dim]\n\n"
                "Use [cyan]--interactive[/cyan] to set your struggle areas\n"
                "or [cyan]--modules 11,12,14[/cyan] to specify directly.",
                title="[bold cyan][*] STRUGGLE SCHEMA[/bold cyan]",
                border_style=Style(color=CORTEX_THEME["secondary"]),
                box=box.HEAVY,
            ))
            return

        # Display heatmap
        console.print(create_struggle_heatmap(struggle_schema))

        # Show summary
        high_struggle = [m for m, s in struggle_schema.items() if s >= 0.7]
        med_struggle = [m for m, s in struggle_schema.items() if 0.4 <= s < 0.7]

        if high_struggle:
            console.print(f"\n[red]HIGH priority:[/red] Modules {', '.join(map(str, sorted(high_struggle)))}")
        if med_struggle:
            console.print(f"[yellow]MEDIUM priority:[/yellow] Modules {', '.join(map(str, sorted(med_struggle)))}")

        console.print(f"\n[dim]Run [cyan]cortex start --war --modules {','.join(map(str, sorted(high_struggle or med_struggle)))}[/cyan] to focus on weak areas[/dim]")
        return

    # Interactive mode
    if interactive:
        console.print(Panel(
            "[bold cyan][*] STRUGGLE SCHEMA CONFIGURATION [*][/bold cyan]\n\n"
            "Rate your difficulty with each CCNA module.\n"
            "0 = No problem, 1 = Major struggle",
            border_style=Style(color=CORTEX_THEME["primary"]),
            box=box.HEAVY,
        ))

        module_names = {
            1: "Networking Today", 2: "Basic Switch/End Device Config",
            3: "Protocols and Models", 4: "Physical Layer", 5: "Number Systems",
            6: "Data Link Layer", 7: "Ethernet Switching", 8: "Network Layer",
            9: "Address Resolution", 10: "Basic Router Configuration",
            11: "IPv4 Addressing", 12: "IPv6 Addressing", 13: "ICMP",
            14: "Transport Layer", 15: "Application Layer",
            16: "Network Security", 17: "Build a Small Network",
        }

        for mod in range(1, 18):
            current = struggle_schema.get(mod, 0.0)
            name = module_names.get(mod, f"Module {mod}")

            console.print(f"\n[cyan]M{mod:02d}[/cyan]: {name}")
            console.print(f"[dim]Current: {current:.0%}[/dim]")

            choice = Prompt.ask(
                "Difficulty [0-10]",
                choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "s"],
                default=str(int(current * 10)),
            )

            if choice.lower() == "s":
                continue  # Skip this module

            struggle_schema[mod] = int(choice) / 10.0

    # Modules flag mode
    elif modules:
        # Parse modules - can be "11,12,14" or "11-14" or mixed
        module_list = []
        for part in modules.split(","):
            part = part.strip()
            if "-" in part:
                try:
                    start, end = part.split("-")
                    module_list.extend(range(int(start), int(end) + 1))
                except ValueError:
                    pass
            elif part.isdigit():
                module_list.append(int(part))

        # Ask for intensity if not specified
        intensity = Prompt.ask(
            "Struggle intensity for these modules",
            choices=["low", "medium", "high"],
            default="high",
        )

        intensity_map = {"low": 0.3, "medium": 0.6, "high": 0.9}
        intensity_value = intensity_map.get(intensity.lower(), 0.6)

        for mod in module_list:
            if 1 <= mod <= 17:
                struggle_schema[mod] = intensity_value

    # Save updated schema
    with open(struggle_file, "w") as f:
        json.dump({str(k): v for k, v in struggle_schema.items()}, f, indent=2)

    # Show confirmation
    console.print(Panel(
        "[green]Struggle schema updated successfully![/green]",
        border_style=Style(color=CORTEX_THEME["success"]),
    ))

    # Show updated heatmap
    console.print(create_struggle_heatmap(struggle_schema))


@cortex_app.command("neurolink")
def cortex_neurolink():
    """
    Display current neuro-link cognitive status.

    Shows a real-time snapshot of your cognitive state:
    - Encoding strength (memory formation)
    - Integration capacity (working memory)
    - Focus index (attention)
    - Fatigue level (exhaustion)

    These metrics are updated during study sessions.
    """
    from src.adaptive.persona_service import PersonaService

    service = PersonaService()
    persona = service.get_persona()

    # Calculate mock cognitive state from persona
    # In a real session, these would come from NCDE
    encoding = max(0.4, min(1.0, persona.strength_factual * 1.2))
    integration = max(0.4, min(1.0, persona.strength_procedural * 1.2))
    focus = max(0.5, min(1.0, 1.0 - (0.3 if persona.current_streak_days == 0 else 0.0)))
    fatigue = 0.1  # Baseline when not in session

    console.print(create_neurolink_panel(
        encoding=encoding,
        integration=integration,
        focus=focus,
        fatigue=fatigue,
        diagnosis="",
        strategy="",
    ))

    # Additional context
    content = Text()
    content.append("\n[*] COGNITIVE CONTEXT [*]\n\n", style=STYLES["cortex_primary"])

    content.append("ENCODING ", style=Style(color=CORTEX_THEME["accent"]))
    content.append("(Hippocampus): ", style=STYLES["cortex_dim"])
    content.append("How well new facts are being stored\n", style=Style(color=CORTEX_THEME["white"]))

    content.append("INTEGRATION ", style=Style(color=CORTEX_THEME["accent"]))
    content.append("(P-FIT Network): ", style=STYLES["cortex_dim"])
    content.append("Working memory for complex problems\n", style=Style(color=CORTEX_THEME["white"]))

    content.append("FOCUS ", style=Style(color=CORTEX_THEME["accent"]))
    content.append("(Prefrontal Cortex): ", style=STYLES["cortex_dim"])
    content.append("Attention and engagement level\n", style=Style(color=CORTEX_THEME["white"]))

    content.append("FATIGUE ", style=Style(color=CORTEX_THEME["accent"]))
    content.append("(Global): ", style=STYLES["cortex_dim"])
    content.append("Cognitive exhaustion requiring rest\n", style=Style(color=CORTEX_THEME["white"]))

    content.append("\n[dim]Start a study session to see real-time metrics.[/dim]", style="")

    console.print(Panel(
        content,
        border_style=Style(color=CORTEX_THEME["secondary"]),
        box=box.ROUNDED,
        padding=(0, 1),
    ))


def main() -> None:
    cortex_app()


if __name__ == "__main__":
    main()
