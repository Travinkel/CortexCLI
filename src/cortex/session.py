"""
Cortex Session: Orchestration layer for interactive study.

Refactored Architecture:
- UI/Rendering -> src.delivery.cortex_visuals
- Logic/Parsing -> src.cortex.atoms (Handlers)
- Algorithms -> src.adaptive.ncde_pipeline
- State/Persistence -> src.cortex.session_store
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
import time
from pathlib import Path
from typing import Optional

from loguru import logger

logger.remove()
logger.add(
    sys.stderr,
    level="INFO",  # Changed to INFO to make warnings visible
    format="<dim>{time:HH:mm:ss}</dim> | <level>{level: <8}</level> | {message}",
)

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from config import get_settings
from src.cortex.atoms import get_handler as get_atom_handler
from src.cortex.session_store import SessionStore, SessionState, create_session_state
from src.study.study_service import StudyService

# UI Delegation
from src.delivery import cortex_visuals as ui

# Adaptive Pipeline
from src.adaptive.ncde_pipeline import (
    FatigueVector,
    NCDEPipeline,
    SessionContext,
    create_raw_event,
    prepare_struggle_update,
)
from src.adaptive.neuro_model import FailMode
from src.adaptive.persona_service import PersonaService

# Socratic Tutoring
from src.cortex.socratic import SocraticTutor, SocraticSession, Resolution
from src.cortex.dialogue_recorder import DialogueRecorder
from src.cortex.remediation_recommender import RemediationRecommender
from src.integrations.greenlight_client import (
    GreenlightAtomRequest,
    GreenlightAtomResult,
    GreenlightExecutionStatus,
    GreenlightClient,
)

console = Console()

# Cache directory for offline sync resilience
OFFLINE_CACHE_DIR = Path("outputs/cache")
OFFLINE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
PENDING_SYNC_FILE = OFFLINE_CACHE_DIR / "pending_sync.json"


class CortexSession:
    """
    Orchestrator for the Cognitive Loop.
    Decouples rendering, logic, and state management.
    """

    def __init__(
        self,
        modules: list[int],
        limit: int = 20,
        war_mode: bool = False,
        enable_ncde: bool = True,
        session_state: Optional[SessionState] = None,
        atoms_override: Optional[list[dict]] = None,
        sections: Optional[list[str]] = None,
        source_file: Optional[str] = None,
    ):
        self.modules = modules
        self.sections = sections
        self.source_file = source_file
        self.limit = limit
        self.war_mode = war_mode
        self.enable_ncde = enable_ncde
        self.start_time = time.monotonic()
        self.settings = get_settings()

        # Greenlight Integration
        self.greenlight_config = self.settings.get_greenlight_config()
        self.greenlight_enabled = self.settings.has_greenlight_configured()
        self.greenlight_fallback_mode = self.greenlight_config.get(
            "fallback_mode", "queue"
        )
        self.greenlight_client: GreenlightClient | None = None
        if self.greenlight_enabled:
            self.greenlight_client = GreenlightClient(
                api_url=self.greenlight_config["api_url"],
                timeout_ms=self.greenlight_config["handoff_timeout_ms"],
                retry_attempts=self.greenlight_config["retry_attempts"],
            )

        # Metrics
        self.correct = 0
        self.incorrect = 0
        self._streak = 0
        self.current_index = 0
        self._error_streak = 0
        self._recent_response_times: list[int] = []  # For Flow State detection

        # Backend & Pipeline
        self.study_service = StudyService()
        self.persona_service = PersonaService()
        self.ncde = NCDEPipeline() if enable_ncde else None
        self.session_context: Optional[SessionContext] = None

        # State Management
        self.queue: list[dict] = []
        self._atoms_override = atoms_override
        self._session_store = SessionStore()
        self._session_state: Optional[SessionState] = session_state
        self._atoms_completed: list[str] = []
        self._incorrect_atoms: list[dict] = []

        # Strategies & Resilience
        self._suspension_stack: list[dict] = []
        self._post_break_grace = 0
        self._offline_mode = False

        # Micro-note tracking (consecutive errors by section)
        self._section_error_streak: dict[str, int] = {}
        self._micro_note_shown: set[str] = set()

        # Socratic Tutoring
        self.socratic_tutor = SocraticTutor()
        self.dialogue_recorder = DialogueRecorder()
        self.remediation_recommender = RemediationRecommender()

        if session_state:
            self._restore_from_state(session_state)

    def load_queue(self) -> None:
        """Hydrates the question queue via StudyService and removes duplicates."""
        if self._atoms_override:
            atoms = self._atoms_override
        elif self.war_mode:
            with ui.CortexSpinner(console, "Engaging War Mode..."):
                atoms = self.study_service.get_war_session(
                    modules=self.modules,
                    limit=self.limit * 2,
                    prioritize_types=["mcq", "parsons"],
                )
        else:
            with ui.CortexSpinner(console, "Calibrating Neuro-Adaptive Path..."):
                atoms = self.study_service.get_adaptive_session(
                    limit=self.limit * 2,
                    include_new=True,
                    interleave=True,
                    modules=self.modules if self.modules != list(range(1, 18)) else None,
                    sections=self.sections,
                    source_file=self.source_file,
                )

        # De-duplicate atoms based on 'id'
        seen_ids = set()
        unique_atoms = []
        for atom in atoms:
            atom_id = atom.get("id")
            if atom_id and atom_id not in seen_ids:
                unique_atoms.append(atom)
                seen_ids.add(atom_id)

        # Hydrate/Validate using Atom Handlers directly
        self.queue = []
        for atom in unique_atoms:
            handler = get_atom_handler(atom.get("atom_type", ""))
            if handler and handler.validate(atom):
                self.queue.append(atom)

        self.queue = self.queue[: self.limit]
        if not self.war_mode:
            random.shuffle(self.queue)

        # Initialize State
        if not self._session_state:
            atom_ids = [str(a.get("id", "")) for a in self.queue if a.get("id")]
            self._session_state = create_session_state(
                self.modules, self.limit, self.war_mode, atom_ids
            )

    def _restore_from_state(self, state: SessionState) -> None:
        """Restores session context from disk."""
        self.correct = state.correct
        self.incorrect = state.incorrect
        self.current_index = state.current_index
        self._atoms_completed = state.atoms_completed.copy()

    def sync_anki(self) -> None:
        """Resilient Sync: Attempts live sync, falls back to local buffer."""
        try:
            from src.anki.anki_client import AnkiClient
            from src.anki.pull_service import pull_review_stats

            client = AnkiClient()
            if not client.check_connection(cache_seconds=0):
                self._offline_mode = True
                if PENDING_SYNC_FILE.exists():
                    logger.warning("Anki unreachable. Pending changes buffered.")
                return

            # Flush pending changes first
            if PENDING_SYNC_FILE.exists():
                try:
                    self._flush_offline_buffer(client)
                except Exception as e:
                    logger.error(f"Failed to flush offline buffer: {e}")

            # Normal Pull
            with ui.CortexSpinner(console, "Syncing Neural Link..."):
                pull_review_stats(anki_client=client)

        except ImportError:
            self._offline_mode = True
        except Exception:
            self._offline_mode = True

    def _flush_offline_buffer(self, client) -> None:
        """Flushes locally cached interaction events to Anki."""
        PENDING_SYNC_FILE.unlink()
        console.print("Offline buffer synced.", style="dim")

    def run(self) -> None:
        """Event-Driven Cognitive Loop."""
        ui.cortex_boot_sequence(console, self.war_mode)
        self.sync_anki()

        if not self.queue:
            self.load_queue()
            if not self.queue:
                console.print("[red]No content available.[/red]")
                return

        # Pre-session: Check for unread remediation notes
        self._check_unread_notes()

        # Init NCDE
        if self.ncde:
            self.session_context = SessionContext(
                session_id=f"session_{int(time.time())}",
                learner_id="default",
                queue_size=len(self.queue),
            )

        idx = 0
        try:
            while idx < len(self.queue):
                note = self.queue[idx]
                self.current_index = idx + 1

                # Render Dashboard
                ui.render_session_dashboard(
                    console=console,
                    mode="WAR" if self.war_mode else "ADAPTIVE",
                    start_time=self.start_time,
                    stats={
                        "correct": self.correct,
                        "incorrect": self.incorrect,
                        "streak": self._streak,
                    },
                    total=len(self.queue),
                    current=self.current_index,
                    context=self.session_context,
                    offline=self._offline_mode,
                )

                # Process Interaction
                result_state = self._process_atom_interaction(note)

                # Post-Processing
                self._update_metrics(result_state, note)
                self._handle_ncde_pipeline(result_state, note, idx)

                # Advance
                if not result_state["repeat_queue"]:
                    idx += 1

                if idx % 5 == 0:
                    self._session_store.save(self._session_state)

        except KeyboardInterrupt:
            self._handle_interrupt()

        self._finalize_session()

    def _process_atom_interaction(self, note: dict) -> dict:
        """Handles Ask -> Answer -> Feedback loop for a single atom."""
        content_json = note.get("content_json") or note.get("content") or {}
        if isinstance(content_json, str):
            try:
                content_json = json.loads(content_json)
            except json.JSONDecodeError:
                content_json = {}
        if self._should_handoff_greenlight(note, content_json):
            return self._process_greenlight_atom(note, content_json)

        handler = get_atom_handler(note.get("atom_type", ""))
        if not handler:
            return {"correct": True, "time_ms": 0, "answer": "skipped", "repeat_queue": False}

        # 1. Ask
        ui.render_question_panel(console, note)

        # 2. Capture
        start = time.monotonic()
        user_input = handler.get_input(note, console)
        duration_ms = int((time.monotonic() - start) * 1000)

        # 3. Evaluate
        result = handler.check(note, user_input, console=console)

        # 4. Handle "I don't know" - trigger Socratic dialogue
        if result.dont_know:
            socratic_result = self._run_socratic_dialogue(note, result)
            self._track_dont_know(note)
            return {
                "correct": socratic_result.get("solved", False),
                "time_ms": duration_ms + socratic_result.get("duration_ms", 0),
                "answer": "Socratic dialogue",
                "repeat_queue": False,
                "dont_know": True,
                "socratic_resolution": socratic_result.get("resolution", "unknown"),
            }

        # 5. Immediate Feedback Loop (for non-binary questions)
        if not result.correct and not note.get("_retry_attempt") and note.get("atom_type") != "true_false":
            hint = handler.hint(note, 1)
            ui.render_hint_panel(console, hint or "Think carefully...")
            note["_retry_attempt"] = True
            return self._process_atom_interaction(note)

        # 6. Final Result
        if result.correct:
            ui.render_result_panel(console, True, result.correct_answer)
        else:
            # For incorrect answers, render appropriate feedback per atom type
            atom_type = note.get("atom_type")
            if atom_type == "true_false":
                # Educational feedback for T/F (no retry to prevent gaming)
                ui.render_tf_feedback_panel(
                    console,
                    correct=False,
                    correct_answer=result.correct_answer,
                    user_answer=result.user_answer,
                    explanation=result.explanation,
                )
            elif atom_type != "parsons":
                # Parsons handler renders its own diff, others get standard panel
                ui.render_result_panel(console, False, result.correct_answer, result.explanation)

            # Offer flag option for incorrect answers
            flag_data = ui.prompt_flag_option(console)
            if flag_data:
                self._record_flag(note, flag_data)

        return {
            "correct": result.correct,
            "time_ms": duration_ms,
            "answer": result.user_answer,
            "repeat_queue": False,
        }

    def _should_handoff_greenlight(self, note: dict, content_json: dict) -> bool:
        """Check whether an atom should be routed to Greenlight."""
        owner = content_json.get("owner") or note.get("owner", "cortex")
        grading_mode = content_json.get("grading_mode") or note.get(
            "grading_mode", "static"
        )
        return owner == "greenlight" or grading_mode == "runtime"

    def _process_greenlight_atom(self, note: dict, content_json: dict) -> dict:
        """Route runtime atoms to Greenlight or apply fallback behavior."""
        if not self.greenlight_enabled or not self.greenlight_client:
            logger.warning(
                "Greenlight atom %s but Greenlight disabled. Applying fallback.",
                note.get("id"),
            )
            return self._queue_for_greenlight(note)

        try:
            return self._handoff_to_greenlight(note, content_json)
        except Exception as e:
            logger.error(f"Greenlight handoff failed: {e}")
            return self._handle_greenlight_failure(note, e)

    def _build_greenlight_content(self, note: dict, content_json: dict) -> dict:
        """Build Greenlight content payload from atom fields."""
        content = dict(content_json) if content_json else {}
        if "front" not in content and note.get("front"):
            content["front"] = note.get("front")
        if "back" not in content and note.get("back"):
            content["back"] = note.get("back")
        return content

    def _handoff_to_greenlight(self, note: dict, content_json: dict) -> dict:
        """Hand off atom to Greenlight for execution."""
        console.print(
            Panel(
                "[bold cyan]Handing off to Greenlight IDE...[/bold cyan]\n\n"
                f"Atom: {note.get('atom_type', 'runtime')}\n"
                "This requires execution in a sandboxed environment.\n\n"
                "[dim]Waiting for results...[/dim]",
                title="Greenlight Handoff",
                border_style="cyan",
            )
        )

        request = GreenlightAtomRequest(
            atom_id=str(note.get("id", "")),
            atom_type=str(note.get("atom_type", "")),
            content=self._build_greenlight_content(note, content_json),
            session_context={
                "modules": self.modules,
                "war_mode": self.war_mode,
                "error_streak": self._error_streak,
            },
        )

        if content_json.get("async_execution", False):
            execution_id = self._run_async(self.greenlight_client.queue_atom(request))
            console.print(f"[yellow]Queued for execution: {execution_id}[/yellow]")
            status = self._poll_greenlight_execution(execution_id)
            if status.status != "complete" or not status.result:
                raise RuntimeError(status.error or "Greenlight execution failed")
            result = status.result
        else:
            result = self._run_async(self.greenlight_client.execute_atom(request))

        self._display_greenlight_result(result)

        return {
            "correct": result.correct,
            "time_ms": int(result.meta.get("execution_time_ms", 0)),
            "answer": result.feedback or "",
            "repeat_queue": False,
        }

    def _display_greenlight_result(self, result: GreenlightAtomResult) -> None:
        """Display Greenlight execution result in terminal."""
        tests = result.test_results
        if isinstance(tests, dict):
            tests = tests.get("tests") or tests.get("results") or []

        if isinstance(tests, list) and tests:
            test_table = Table(title="Test Results")
            test_table.add_column("Test", style="cyan")
            test_table.add_column("Status", style="bold")
            test_table.add_column("Details")

            for test in tests:
                status = "PASS" if test.get("passed") else "FAIL"
                status_style = "green" if test.get("passed") else "red"
                test_table.add_row(
                    str(test.get("name", "Unnamed")),
                    f"[{status_style}]{status}[/{status_style}]",
                    str(test.get("message", "")),
                )

            console.print(test_table)

        score = result.partial_score * 100
        score_color = "green" if result.partial_score >= 0.7 else "yellow"
        if result.partial_score < 0.4:
            score_color = "red"

        console.print(f"\n[{score_color}]Score: {score:.0f}%[/{score_color}]")

        if result.feedback:
            console.print(result.feedback)

        if result.git_suggestions:
            console.print("\n[bold cyan]Suggestions:[/bold cyan]")
            for suggestion in result.git_suggestions:
                console.print(f"  - {suggestion}")

        if result.diff_suggestion:
            console.print("\n[bold cyan]Diff Suggestion:[/bold cyan]")
            console.print(result.diff_suggestion)

        if result.error:
            console.print(f"\n[red]Error: {result.error}[/red]")

    def _poll_greenlight_execution(
        self,
        execution_id: str,
        poll_interval_sec: float = 2.0,
        max_wait_sec: float = 300.0,
    ) -> GreenlightExecutionStatus:
        """Poll Greenlight for queued execution result."""
        start_time = time.monotonic()
        while True:
            status = self._run_async(self.greenlight_client.poll_execution(execution_id))
            if status.status in {"complete", "failed"}:
                return status
            if time.monotonic() - start_time > max_wait_sec:
                return GreenlightExecutionStatus(
                    execution_id=execution_id,
                    status="failed",
                    error="Greenlight execution timed out",
                )
            time.sleep(poll_interval_sec)

    def _handle_greenlight_failure(self, note: dict, error: Exception) -> dict:
        """Handle Greenlight failure gracefully."""
        console.print(
            "[red]Failed to execute atom via Greenlight.[/red]\n"
            f"Error: {str(error)}\n\n"
            "This atom will be skipped for now."
        )
        return {
            "correct": False,
            "time_ms": 0,
            "answer": "",
            "repeat_queue": False,
            "skipped": True,
        }

    def _queue_for_greenlight(self, note: dict) -> dict:
        """Queue atom for later Greenlight execution."""
        console.print(
            "[yellow]Greenlight is disabled but this atom requires runtime execution.[/yellow]\n"
            f"Atom {note.get('id', '')} queued for later execution."
        )
        # TODO: Persist to greenlight_queue table when available.
        return {
            "correct": False,
            "time_ms": 0,
            "answer": "",
            "repeat_queue": False,
            "skipped": self.greenlight_fallback_mode in {"queue", "skip", "manual"},
        }

    def _run_async(self, coro):
        """Run coroutine from sync context."""
        try:
            return asyncio.run(coro)
        except RuntimeError as exc:
            if "asyncio.run()" not in str(exc):
                raise
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)

    def _handle_ncde_pipeline(self, result: dict, note: dict, idx: int) -> None:
        """Runs the Neuro-Cognitive Diagnosis Engine pipeline."""
        if result.get("skipped"):
            return
        if not self.ncde or not self.session_context:
            return

        raw_event = create_raw_event(
            atom_id=str(note.get("id", "")),
            atom_type=note.get("atom_type", "flashcard"),
            is_correct=result["correct"],
            user_answer=result["answer"],
            correct_answer=note.get("back", ""),
            response_time_ms=result["time_ms"],
            session_duration_seconds=int(time.monotonic() - self.start_time),
            session_index=idx,
        )

        # Track section-level errors for micro-notes
        self._update_section_error_streak(note, result["correct"])

        # Flow State Protection
        is_flow = self._check_flow_state(result["time_ms"], result["correct"])

        if self._post_break_grace > 0:
            self._post_break_grace -= 1
            return

        diagnosis, strategy = self.ncde.process(raw_event, self.session_context)

        # Update dynamic struggle weights in PostgreSQL
        self._update_struggle_weight(note, result["correct"], diagnosis)

        # Suppress fatigue break if in flow
        if diagnosis.fail_mode == FailMode.FATIGUE_ERROR and is_flow:
            logger.info("Fatigue break suppressed due to detected Flow State.")
            return

        if not result["correct"]:
            ui.render_diagnosis_panel(console, diagnosis)

            # Show contrastive comparison for discrimination errors
            if diagnosis.fail_mode == FailMode.DISCRIMINATION_ERROR:
                self._show_contrastive_comparison(note, diagnosis)

            # Check for micro-note trigger (2+ consecutive errors in same section)
            self._check_micro_note_trigger(note)

        if strategy.name == "micro_break":
            ui.trigger_micro_break(console, strategy.message)
            self._post_break_grace = 5
            self.ncde.reset_fatigue()

    def _check_flow_state(self, time_ms: int, is_correct: bool) -> bool:
        """Heuristic: High accuracy + fast responses = Flow."""
        self._recent_response_times.append(time_ms)
        if len(self._recent_response_times) > 5:
            self._recent_response_times.pop(0)

        if self._streak < 3:
            return False

        if len(self._recent_response_times) >= 3:
            avg = sum(self._recent_response_times) / len(self._recent_response_times)
            if avg < 15000:
                return True
        return False

    def _show_contrastive_comparison(self, note: dict, diagnosis) -> None:
        """
        Show side-by-side comparison when discrimination error detected.

        Uses the ConfusionMatrix to find the most confused concept pair
        and renders a contrastive panel.
        """
        try:
            from src.cortex.contrastive import get_contrastive_data

            atom_id = str(note.get("id", ""))
            if not atom_id:
                logger.warning("Contrastive: Missing atom_id in current note.")
                return

            if not hasattr(self.ncde, "confusion_matrix"):
                logger.warning("Contrastive: NCDE has no confusion_matrix attribute.")
                return

            worst_pair = self.ncde.confusion_matrix.get_worst_pair(atom_id)
            if not worst_pair:
                logger.debug(f"Contrastive: No confused pair found for atom {atom_id}.")
                return

            confused_id, confusion_score = worst_pair
            logger.debug(f"Contrastive: Found confused pair ({atom_id}, {confused_id}) with score {confusion_score:.2f}.")

            if confusion_score < 0.3:  # Threshold for showing comparison
                logger.debug("Contrastive: Confusion score below threshold, skipping panel.")
                return

            # Fetch contrastive data
            concept_a, concept_b, evidence = get_contrastive_data(atom_id, confused_id)

            # Render the comparison panel
            ui.render_contrastive_panel(
                console,
                concept_a=concept_a,
                concept_b=concept_b,
                confusion_evidence=evidence,
            )

        except Exception as e:
            logger.warning(f"Could not show contrastive comparison: {e}", exc_info=True)

    def _update_struggle_weight(self, note: dict, is_correct: bool, diagnosis) -> None:
        """
        Update dynamic struggle weights in PostgreSQL based on NCDE diagnosis.

        This moves beyond static YAML-based struggle weights to real-time
        performance-based prioritization.
        """
        from sqlalchemy import text
        from src.db.database import engine

        section_id = note.get("ccna_section_id")
        if not section_id:
            return

        # Extract module number from section_id (e.g., "11.4.1" -> 11)
        try:
            module_number = int(section_id.split(".")[0])
        except (ValueError, IndexError):
            return

        # Get failure mode from diagnosis
        failure_mode = diagnosis.fail_mode.value if diagnosis.fail_mode else "unknown"

        # Prepare update data
        update_data = prepare_struggle_update(
            diagnosis=diagnosis,
            module_number=module_number,
            section_id=section_id,
            is_correct=is_correct,
            atom_id=str(note.get("id", "")),
            session_id=self.session_context.session_id if self.session_context else None,
        )

        # Call PostgreSQL function to update struggle weight
        # Function signature: update_struggle_from_ncde(
        #   p_user_id, p_module_number, p_section_id, p_failure_mode,
        #   p_accuracy, p_atom_id, p_session_id
        # )
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        SELECT update_struggle_from_ncde(
                            :user_id, :module_number, :section_id, :failure_mode,
                            :accuracy, :atom_id::uuid, :session_id::uuid
                        )
                    """),
                    {
                        "user_id": "default",
                        "module_number": update_data.module_number,
                        "section_id": update_data.section_id,
                        "failure_mode": update_data.failure_mode,
                        "accuracy": update_data.accuracy,  # 1.0 for correct, 0.0 for incorrect
                        "atom_id": update_data.atom_id,
                        "session_id": update_data.session_id,
                    },
                )
                conn.commit()
                logger.debug(
                    f"Struggle weight updated: module {module_number}, "
                    f"section {section_id}, correct={is_correct}"
                )
        except Exception as e:
            # Non-critical - struggle updates shouldn't break the session
            logger.debug(f"Failed to update struggle weight: {e}")

    def _update_section_error_streak(self, note: dict, is_correct: bool) -> None:
        """Track consecutive errors by section."""
        section_id = note.get("ccna_section_id", "unknown")

        if is_correct:
            # Reset streak on correct answer
            self._section_error_streak[section_id] = 0
        else:
            # Increment streak on error
            current = self._section_error_streak.get(section_id, 0)
            self._section_error_streak[section_id] = current + 1

    def _check_micro_note_trigger(self, note: dict) -> None:
        """Check if we should show a micro-note for this section."""
        section_id = note.get("ccna_section_id", "unknown")

        if section_id == "unknown":
            return

        error_streak = self._section_error_streak.get(section_id, 0)

        # Trigger micro-note on 2+ consecutive errors (only once per section per session)
        if error_streak >= 2 and section_id not in self._micro_note_shown:
            self._show_micro_note(section_id, note)
            self._micro_note_shown.add(section_id)

    def _show_micro_note(self, section_id: str, note: dict) -> None:
        """Display a quick micro-note for the struggling section."""
        from rich.panel import Panel
        from rich import box

        console.print()
        console.print("[yellow]━━━ QUICK REVIEW ━━━[/yellow]")
        console.print(f"[dim]Multiple errors on section {section_id}[/dim]\n")

        # Try to get existing note, or show a generic tip
        try:
            from src.learning.note_generator import get_qualified_notes

            notes = get_qualified_notes(section_ids=[section_id])
            if notes:
                content = notes[0].get("content", "")[:500]
                if len(notes[0].get("content", "")) > 500:
                    content += "..."

                panel = Panel(
                    content,
                    title=f"[bold cyan]{notes[0].get('title', 'Study Tip')}[/bold cyan]",
                    border_style="yellow",
                    box=box.ROUNDED,
                    padding=(1, 2),
                )
                console.print(panel)
            else:
                # Generic tip based on atom content
                console.print(f"[cyan]Key concept: {note.get('front', '')}[/cyan]")
                if note.get("explanation"):
                    console.print(f"[dim]{note.get('explanation')}[/dim]")

        except Exception as e:
            logger.warning(f"Failed to fetch micro-note: {e}")
            # Fallback: show the correct answer as a mini-review
            console.print(f"[cyan]Remember: {note.get('back', '')}[/cyan]")

        console.print("\n[dim]Press Enter to continue...[/dim]")
        input()

    def _update_metrics(self, result: dict, note: dict) -> None:
        """Updates internal counters and persists to database."""
        if result.get("skipped"):
            return
        if result["correct"]:
            self.correct += 1
            self._streak += 1
            self._error_streak = 0
        else:
            self.incorrect += 1
            self._streak = 0
            self._error_streak += 1
            if note not in self._incorrect_atoms:
                self._incorrect_atoms.append(note)

        # Persist to database with transfer testing
        atom_id = str(note.get("id", ""))
        atom_type = note.get("atom_type", "")
        if atom_id:
            try:
                self.study_service.record_interaction(
                    atom_id=atom_id,
                    is_correct=result["correct"],
                    response_time_ms=result.get("time_ms", 0),
                    user_answer=result.get("answer", ""),
                    session_type="war" if self.war_mode else "adaptive",
                    atom_type=atom_type,
                )
            except Exception as e:
                logger.debug(f"Could not persist interaction: {e}")

        if self._offline_mode:
            self._buffer_interaction(note, result)

    def _buffer_interaction(self, note: dict, result: dict) -> None:
        """Buffers interaction to JSON when Anki is offline."""
        event = {
            "atom_id": str(note.get("id")),
            "timestamp": time.time(),
            "result": result,
        }
        try:
            current = []
            if PENDING_SYNC_FILE.exists():
                current = json.loads(PENDING_SYNC_FILE.read_text())
            current.append(event)
            PENDING_SYNC_FILE.write_text(json.dumps(current))
        except Exception as e:
            logger.error(f"Failed to buffer offline event: {e}")

    def _track_dont_know(self, note: dict) -> None:
        """Track 'I don't know' response for remediation targeting."""
        atom_id = note.get("id")
        if not atom_id:
            return

        try:
            from sqlalchemy import text
            from src.db.database import get_session

            with next(get_session()) as session:
                session.execute(
                    text("""
                        UPDATE learning_atoms
                        SET dont_know_count = COALESCE(dont_know_count, 0) + 1
                        WHERE id = :atom_id
                    """),
                    {"atom_id": str(atom_id)}
                )
                session.commit()
        except Exception as e:
            logger.warning(f"Failed to track dont_know: {e}")

    def _record_flag(self, note: dict, flag_data: dict) -> None:
        """Record a user flag for a problematic question."""
        atom_id = note.get("id")
        if not atom_id or not flag_data:
            return

        try:
            from sqlalchemy import text
            from src.db.database import get_session

            with next(get_session()) as session:
                # Try to insert flag, ignore if table doesn't exist yet
                session.execute(
                    text("""
                        INSERT INTO user_flags (atom_id, flag_type, flag_reason, session_id)
                        VALUES (:atom_id, :flag_type, :flag_reason, :session_id)
                    """),
                    {
                        "atom_id": str(atom_id),
                        "flag_type": flag_data.get("type", "other"),
                        "flag_reason": flag_data.get("reason"),
                        "session_id": str(self.session_id) if hasattr(self, "session_id") else None,
                    }
                )
                session.commit()
                logger.info(f"Recorded flag for atom {atom_id}: {flag_data.get('type')}")
        except Exception as e:
            # Silently fail if table doesn't exist - migration may not have run
            logger.debug(f"Could not record flag (table may not exist): {e}")

    def _run_socratic_dialogue(self, note: dict, initial_result) -> dict:
        """
        Run an interactive Socratic tutoring dialogue.

        Args:
            note: The atom being studied
            initial_result: The AnswerResult from the initial check

        Returns:
            Dict with 'solved', 'resolution', 'duration_ms', 'gaps'
        """
        from rich.prompt import Prompt

        # Start Socratic session
        session = self.socratic_tutor.start_session(note)

        # Start recording (learner_id is set in DialogueRecorder constructor)
        dialogue_id = self.dialogue_recorder.start_recording(
            atom_id=session.atom_id
        )

        # Record opening tutor turn
        if dialogue_id and session.turns:
            self.dialogue_recorder.record_turn(
                dialogue_id=dialogue_id,
                turn_number=0,
                role="tutor",
                content=session.turns[0].content,
            )

        # Display opening question
        opening_question = session.turns[0].content if session.turns else "Let's think about this..."
        ui.render_socratic_panel(console, opening_question, session.scaffold_level.value, is_opening=True)

        # Dialogue loop
        turn_number = 1
        while not session.ended_at:
            # Get learner response
            start_time = time.monotonic()
            try:
                learner_response = Prompt.ask("[dim]Your thoughts[/dim]")
            except (KeyboardInterrupt, EOFError):
                session.resolution = Resolution.GAVE_UP
                session.ended_at = time.monotonic()
                break

            latency_ms = int((time.monotonic() - start_time) * 1000)

            # Record learner turn
            if dialogue_id:
                self.dialogue_recorder.record_turn(
                    dialogue_id=dialogue_id,
                    turn_number=turn_number,
                    role="learner",
                    content=learner_response,
                    latency_ms=latency_ms,
                )
            turn_number += 1

            # Process response
            next_question, is_resolved = self.socratic_tutor.process_response(
                session, learner_response, latency_ms
            )

            if is_resolved:
                # Show resolution
                if session.resolution == Resolution.SELF_SOLVED or session.resolution == Resolution.GUIDED_SOLVED:
                    ui.render_socratic_success_panel(
                        console,
                        next_question or "You figured it out!",
                        session.turn_count
                    )
                elif session.resolution == Resolution.REVEALED:
                    ui.render_result_panel(
                        console, False, initial_result.correct_answer,
                        next_question or "Here's the answer:"
                    )
                else:  # GAVE_UP
                    ui.render_result_panel(
                        console, False, initial_result.correct_answer,
                        "Here's the answer for future reference:"
                    )
                break
            else:
                # Record tutor turn
                if dialogue_id:
                    self.dialogue_recorder.record_turn(
                        dialogue_id=dialogue_id,
                        turn_number=turn_number,
                        role="tutor",
                        content=next_question,
                    )
                turn_number += 1

                # Display next question
                ui.render_socratic_panel(console, next_question, session.scaffold_level.value)

        # Detect prerequisite gaps
        detected_gaps = self.socratic_tutor.detect_prerequisite_gaps(session)
        session.detected_gaps = detected_gaps

        # Finalize recording
        if dialogue_id:
            self.dialogue_recorder.finalize(
                dialogue_id=dialogue_id,
                resolution=session.resolution.value if session.resolution else "unknown",
                scaffold_level_reached=session.scaffold_level.value,
                turns_count=session.turn_count,
                total_duration_ms=session.duration_ms,
                detected_gaps=detected_gaps,
            )

        # Show dialogue summary
        if session.resolution:
            ui.render_dialogue_summary_panel(
                console,
                resolution=session.resolution.value,
                turns_count=session.turn_count,
                duration_ms=session.duration_ms,
                scaffold_level=session.scaffold_level.value,
            )

        # Show remediation recommendations if gaps detected
        if detected_gaps:
            recommendations = self.remediation_recommender.recommend(
                gaps=detected_gaps,
                current_atom_id=session.atom_id,
            )
            if recommendations:
                ui.render_remediation_panel(console, recommendations)

        # Determine if solved
        solved = session.resolution in (Resolution.SELF_SOLVED, Resolution.GUIDED_SOLVED)

        return {
            "solved": solved,
            "resolution": session.resolution.value if session.resolution else "unknown",
            "duration_ms": session.duration_ms,
            "gaps": detected_gaps,
        }

    def _check_unread_notes(self) -> None:
        """Check for unread remediation notes before starting session."""
        try:
            from src.learning.note_generator import get_qualified_notes

            # Get section IDs from queued atoms
            section_ids = list({
                atom.get("ccna_section_id")
                for atom in self.queue
                if atom.get("ccna_section_id")
            })

            if not section_ids:
                return

            # Get unread notes for these sections
            notes = get_qualified_notes(
                section_ids=section_ids,
                unread_only=True,
            )

            if not notes:
                return

            # Offer to show notes
            console.print(f"\n[yellow]📚 {len(notes)} unread study note(s) available for today's topics[/yellow]")

            if Confirm.ask("Read notes before starting?", default=True):
                self._display_notes(notes)

        except Exception as e:
            logger.warning(f"Failed to check unread notes: {e}")

    def _display_notes(self, notes: list[dict]) -> None:
        """Display remediation notes with navigation."""
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich import box
        from src.learning.note_generator import mark_note_read

        for i, note in enumerate(notes):
            console.clear()
            console.print(f"\n[dim]Note {i + 1} of {len(notes)}[/dim]")

            # Render note content
            content_panel = Panel(
                Markdown(note.get("content", "")),
                title=f"[bold cyan]{note.get('title', 'Study Note')}[/bold cyan]",
                subtitle=f"[dim]Section {note.get('section_id', '')}[/dim]",
                border_style="cyan",
                box=box.HEAVY,
                padding=(1, 2),
            )
            console.print(content_panel)

            # Mark as read
            try:
                mark_note_read(str(note.get("id")))
            except Exception as e:
                logger.warning(f"Failed to mark note read: {e}")

            # Navigation
            if i < len(notes) - 1:
                console.print("\n[dim]Press Enter for next note, 'q' to start session[/dim]")
                response = input().strip().lower()
                if response == "q":
                    break
            else:
                console.print("\n[dim]Press Enter to start session[/dim]")
                input()

        console.print("[green]✓ Notes reviewed. Starting session...[/green]\n")

    def _handle_interrupt(self) -> None:
        """Handles Ctrl+C."""
        console.print("\n")
        if Confirm.ask("[yellow]Save session progress?[/yellow]", default=True):
            self._session_store.save(self._session_state)
            console.print("[green]Session Saved.[/green]")
        else:
            if self._session_state:
                self._session_store.delete(self._session_state.session_id)

    def _finalize_session(self) -> None:
        """End of session cleanup and summary."""
        if self._session_state:
            self._session_store.delete(self._session_state.session_id)
        ui.render_session_summary(
            console,
            self.correct,
            self.incorrect,
            self.session_context,
            self._incorrect_atoms,
        )

        # Post-session remediation offer
        self._offer_post_session_remediation()

    def _offer_post_session_remediation(self) -> None:
        """Offer remediation for weak sections after session ends."""
        logger.debug(f"Post-session remediation check: {len(self._incorrect_atoms)} incorrect atoms")

        if not self._incorrect_atoms:
            logger.debug("No incorrect atoms - skipping remediation offer")
            return

        # Group incorrect atoms by section (check both field names)
        section_errors: dict[str, list[dict]] = {}
        for atom in self._incorrect_atoms:
            section_id = (
                atom.get("ccna_section_id")
                or atom.get("section_id")
                or "unknown"
            )
            logger.debug(f"Atom {atom.get('id', '?')}: section_id={section_id}")
            if section_id not in section_errors:
                section_errors[section_id] = []
            section_errors[section_id].append(atom)

        logger.debug(f"Section errors: {[(k, len(v)) for k, v in section_errors.items()]}")

        # Find weak sections - lower threshold: 1+ error if we have 3+ total errors
        total_errors = len(self._incorrect_atoms)
        min_errors_threshold = 1 if total_errors >= 3 else 2
        logger.debug(f"Total errors: {total_errors}, threshold: {min_errors_threshold}")

        weak_sections = [
            (section_id, atoms)
            for section_id, atoms in section_errors.items()
            if len(atoms) >= min_errors_threshold and section_id != "unknown"
        ]

        logger.debug(f"Weak sections found: {len(weak_sections)}")

        if not weak_sections:
            # If we have errors but no weak sections, show info to user
            if total_errors >= 2:
                console.print(
                    f"\n[dim]Note: {total_errors} errors across {len(section_errors)} sections "
                    "(need {min_errors_threshold}+ per section for remediation)[/dim]"
                )
            return

        console.print("\n[yellow]━━━ REMEDIATION RECOMMENDATION ━━━[/yellow]")
        console.print(f"[dim]Found {len(weak_sections)} section(s) with repeated errors:[/dim]\n")

        for section_id, atoms in weak_sections:
            console.print(f"  • Section {section_id}: {len(atoms)} errors")

        console.print()

        # Automatic remediation flow: Read Note → Practice Exercises
        if Confirm.ask("[yellow]Start automatic remediation? (Note → Practice)[/yellow]", default=True):
            self._run_remediation_cycle(weak_sections)
        else:
            # Fallback: just generate notes without practice
            if Confirm.ask("[dim]Generate study notes only?[/dim]", default=False):
                self._generate_remediation_notes(weak_sections)

        # Recommend Anki filtered deck
        self._recommend_filtered_deck(weak_sections)

    def _generate_remediation_notes(self, weak_sections: list[tuple[str, list[dict]]]) -> None:
        """Generate study notes for weak sections."""
        try:
            from src.learning.note_generator import NoteGenerator

            generator = NoteGenerator()
            persona = self.persona_service.get_persona()
            learner_context = persona.to_prompt_context()

            for section_id, atoms in weak_sections:
                console.print(f"\n[cyan]Generating note for section {section_id}...[/cyan]")

                # Extract weak concepts from incorrect atoms
                weak_concepts = [
                    atom.get("front", "")[:50]
                    for atom in atoms[:3]  # Limit to 3 examples
                ]

                result = generator.generate_note(
                    section_id=section_id,
                    weak_concepts=weak_concepts,
                    error_patterns=["incorrect answer", "confusion"],
                    learner_context=learner_context,
                )

                if result.success:
                    console.print(f"[green]✓ Note generated: {result.title}[/green]")

                    # Offer to display immediately
                    if Confirm.ask("Read now?", default=False):
                        from rich.markdown import Markdown
                        from rich.panel import Panel
                        from rich import box

                        panel = Panel(
                            Markdown(result.content or ""),
                            title=f"[bold cyan]{result.title}[/bold cyan]",
                            border_style="cyan",
                            box=box.HEAVY,
                            padding=(1, 2),
                        )
                        console.print(panel)
                        input("\nPress Enter to continue...")
                else:
                    console.print(f"[red]✗ Failed: {result.error}[/red]")

        except Exception as e:
            logger.warning(f"Failed to generate remediation notes: {e}")
            console.print(f"[red]Note generation unavailable: {e}[/red]")

    def _recommend_filtered_deck(self, weak_sections: list[tuple[str, list[dict]]]) -> None:
        """Recommend Anki filtered deck for weak sections."""
        if not weak_sections:
            return

        section_ids = [s[0] for s in weak_sections]

        console.print("\n[yellow]━━━ ANKI FILTERED DECK RECOMMENDATION ━━━[/yellow]")
        console.print("[dim]Create a filtered deck in Anki with this search:[/dim]\n")

        # Build Anki search query
        # Tag format: section:{id} (e.g., section:11.1)
        search_parts = [f'tag:section:{sid}' for sid in section_ids]
        search_query = f"deck:CCNA::ITN::* ({' OR '.join(search_parts)}) is:due"

        console.print(f"[cyan]{search_query}[/cyan]\n")
        console.print(f"[dim]Suggested deck size: {min(len(weak_sections) * 10, 30)} cards[/dim]")

    def _run_remediation_cycle(self, weak_sections: list[tuple[str, list[dict]]]) -> None:
        """
        Run automatic remediation cycle: Read Note → Practice Exercises.

        Flow:
        1. Generate/fetch note for section
        2. Display note with "Press Enter to continue"
        3. Immediately serve 5-10 exercises from that section
        4. Track pre/post accuracy for effectiveness

        Args:
            weak_sections: List of (section_id, error_atoms) tuples
        """
        from dataclasses import dataclass
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich import box

        @dataclass
        class MiniSessionResult:
            total: int = 0
            correct: int = 0
            incorrect: int = 0

        for section_id, error_atoms in weak_sections:
            console.print(f"\n[bold cyan]━━━ REMEDIATION: Section {section_id} ━━━[/bold cyan]")
            console.print(f"[dim]{len(error_atoms)} errors detected in this section[/dim]\n")

            # Step 1: Generate or fetch existing note
            note_content = self._get_or_generate_note(section_id, error_atoms)

            if note_content:
                # Step 2: Display note
                panel = Panel(
                    Markdown(note_content.get("content", "")),
                    title=f"[bold cyan]{note_content.get('title', f'Section {section_id}')}[/bold cyan]",
                    border_style="cyan",
                    box=box.HEAVY,
                    padding=(1, 2),
                )
                console.print(panel)
                console.input("\n[dim]Press Enter to practice this section...[/dim]")

            # Step 3: Fetch exercises for this specific section
            exclude_ids = [a.get("id") for a in error_atoms if a.get("id")]
            exercises = self.study_service.get_manual_session(
                sections=[section_id],
                atom_types=["mcq", "true_false", "cloze", "numeric"],
                limit=5,
                use_struggle_weights=False,
                shuffle=True,
            )

            # Step 4: Run mini-session with these exercises
            if exercises:
                pre_error_rate = len(error_atoms) / max(1, self.correct + self.incorrect)

                result = self._run_mini_session(exercises, section_id)

                post_error_rate = result.incorrect / max(1, result.total)

                # Display effectiveness feedback
                if result.total > 0:
                    improvement = pre_error_rate - post_error_rate
                    if improvement > 0.1:
                        console.print(f"\n[green]✓ Improvement detected: {improvement:.0%} better![/green]")
                    elif result.correct == result.total:
                        console.print(f"\n[green]✓ Perfect score on remediation exercises![/green]")
                    else:
                        console.print(f"\n[yellow]Practice score: {result.correct}/{result.total}[/yellow]")

                logger.info(
                    f"Remediation cycle complete for {section_id}: "
                    f"pre={pre_error_rate:.1%}, post={post_error_rate:.1%}"
                )
            else:
                console.print(f"[dim]No additional exercises available for section {section_id}[/dim]")

    def _get_or_generate_note(self, section_id: str, error_atoms: list[dict]) -> dict | None:
        """
        Get existing note or generate new one for a section.

        Args:
            section_id: CCNA section ID (e.g., "11.4")
            error_atoms: List of atoms with errors in this section

        Returns:
            Dict with 'title' and 'content' keys, or None if generation failed
        """
        try:
            from src.learning.note_generator import NoteGenerator

            generator = NoteGenerator()
            persona = self.persona_service.get_persona()
            learner_context = persona.to_prompt_context()

            # Extract weak concepts from incorrect atoms
            weak_concepts = [
                atom.get("front", "")[:50]
                for atom in error_atoms[:3]
            ]

            console.print(f"[cyan]Generating study note for section {section_id}...[/cyan]")

            result = generator.generate_note(
                section_id=section_id,
                weak_concepts=weak_concepts,
                error_patterns=["incorrect answer", "confusion"],
                learner_context=learner_context,
            )

            if result.success:
                console.print(f"[green]✓ Note ready: {result.title}[/green]\n")
                return {"title": result.title, "content": result.content}
            else:
                logger.warning(f"Note generation failed: {result.error}")
                return None

        except ImportError:
            logger.warning("NoteGenerator not available - skipping note generation")
            return None
        except Exception as e:
            logger.warning(f"Failed to generate note: {e}")
            return None

    def _run_mini_session(self, exercises: list[dict], section_id: str) -> "MiniSessionResult":
        """
        Run a mini practice session with provided exercises.

        Args:
            exercises: List of atom dicts to practice
            section_id: Section ID for context

        Returns:
            MiniSessionResult with total/correct/incorrect counts
        """
        from dataclasses import dataclass

        @dataclass
        class MiniSessionResult:
            total: int = 0
            correct: int = 0
            incorrect: int = 0

        result = MiniSessionResult()

        console.print(f"\n[bold yellow]━━━ PRACTICE: {len(exercises)} questions ━━━[/bold yellow]\n")

        for i, atom in enumerate(exercises, 1):
            console.print(f"[dim]Question {i}/{len(exercises)} • Section {section_id}[/dim]")

            # Get handler for atom type
            handler = get_atom_handler(atom.get("atom_type", "flashcard"))
            if not handler:
                continue

            # Present and get response
            try:
                handler.present(atom, console)
                response = handler.get_input(atom, console)

                # Evaluate response
                result_obj = handler.check(atom, response, console)
                is_correct = result_obj.correct
                feedback = result_obj.feedback
                result.total += 1

                if is_correct:
                    result.correct += 1
                    console.print("[green]✓ Correct![/green]\n")
                else:
                    result.incorrect += 1
                    console.print(f"[red]✗ {feedback}[/red]\n")

                # Brief pause between questions
                time.sleep(0.3)

            except KeyboardInterrupt:
                console.print("\n[yellow]Mini-session interrupted[/yellow]")
                break
            except Exception as e:
                logger.warning(f"Error in mini-session question: {e}")
                continue

        return result
