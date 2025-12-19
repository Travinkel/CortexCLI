"""
Smoke Tests for CLI Commands.

These tests verify that CLI commands run without errors and produce output.
They don't validate correctness deeply - just that commands work.

Usage:
    pytest tests/smoke/test_cli_commands.py -v
    pytest tests/smoke/test_cli_commands.py -v -m smoke
"""

import subprocess
import sys
from pathlib import Path

import pytest

# Mark all tests in this module as smoke tests
pytestmark = pytest.mark.smoke

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


def run_cli_command(command: str, timeout: int = 30) -> tuple[int, str, str]:
    """
    Run a CLI command and return exit code, stdout, stderr.

    Args:
        command: The command to run (after 'python -m src.cli.cortex')
        timeout: Maximum time to wait

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    full_command = f"{sys.executable} -m src.cli.cortex {command}"

    result = subprocess.run(
        full_command,
        shell=True,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    return result.returncode, result.stdout, result.stderr


class TestCLIHelp:
    """Test that help commands work."""

    def test_main_help(self):
        """Main help should display without errors."""
        code, stdout, stderr = run_cli_command("--help")

        assert code == 0, f"Help failed: {stderr}"
        assert "CORTEX" in stdout or "cortex" in stdout.lower()
        assert "Commands" in stdout

    def test_stats_help(self):
        """Stats command help should work."""
        code, stdout, stderr = run_cli_command("stats --help")

        assert code == 0, f"Stats help failed: {stderr}"

    def test_start_help(self):
        """Start command help should work."""
        code, stdout, stderr = run_cli_command("start --help")

        assert code == 0, f"Start help failed: {stderr}"


class TestCLIStats:
    """Test stats command."""

    def test_stats_runs(self):
        """Stats command should complete without error."""
        code, stdout, stderr = run_cli_command("stats")

        assert code == 0, f"Stats failed with: {stderr}"
        assert "TELEMETRY" in stdout or "Mastery" in stdout.lower() or "Atoms" in stdout

    def test_stats_shows_atoms(self):
        """Stats should show atom count."""
        code, stdout, stderr = run_cli_command("stats")

        assert code == 0
        assert "Atoms" in stdout or "atoms" in stdout.lower()

    def test_stats_shows_sections(self):
        """Stats should show section info."""
        code, stdout, stderr = run_cli_command("stats")

        assert code == 0
        assert "Section" in stdout or "section" in stdout.lower()


class TestCLIPath:
    """Test path command."""

    def test_path_runs(self):
        """Path command should complete."""
        code, stdout, stderr = run_cli_command("path")

        # May fail if no path defined, but shouldn't crash
        assert code in [0, 1], f"Path crashed: {stderr}"

    def test_path_shows_modules(self):
        """Path should show module information."""
        code, stdout, stderr = run_cli_command("path")

        if code == 0:
            assert "Module" in stdout or "module" in stdout.lower()


class TestCLIToday:
    """Test today command."""

    def test_today_runs(self):
        """Today command should complete."""
        code, stdout, stderr = run_cli_command("today")

        # May show "no sessions" but shouldn't crash
        assert code in [0, 1], f"Today crashed: {stderr}"


class TestCLIModule:
    """Test module command."""

    def test_module_1(self):
        """Module 1 details should show."""
        code, stdout, stderr = run_cli_command("module 1")

        assert code in [0, 1], f"Module 1 crashed: {stderr}"

    def test_module_invalid(self):
        """Invalid module number should handle gracefully."""
        code, stdout, stderr = run_cli_command("module 999")

        # Should fail gracefully, not crash
        assert code in [0, 1, 2], "Module 999 crashed unexpectedly"


class TestCLIRemediation:
    """Test remediation command."""

    def test_remediation_runs(self):
        """Remediation command should complete."""
        code, stdout, stderr = run_cli_command("remediation")

        assert code in [0, 1], f"Remediation crashed: {stderr}"


class TestCLIPersona:
    """Test persona command."""

    def test_persona_runs(self):
        """Persona command should complete."""
        code, stdout, stderr = run_cli_command("persona")

        assert code in [0, 1], f"Persona crashed: {stderr}"


class TestCLIDiagnose:
    """Test diagnose command."""

    def test_diagnose_runs(self):
        """Diagnose command should complete."""
        code, stdout, stderr = run_cli_command("diagnose")

        assert code in [0, 1], f"Diagnose crashed: {stderr}"


class TestCLIForceZ:
    """Test force-z command."""

    def test_forcez_runs(self):
        """Force-Z command should complete."""
        code, stdout, stderr = run_cli_command("force-z")

        assert code in [0, 1], f"Force-Z crashed: {stderr}"


class TestCLISchedule:
    """Test schedule-related commands."""

    def test_agenda_runs(self):
        """Agenda command should complete."""
        code, stdout, stderr = run_cli_command("agenda")

        # May fail without Google Calendar configured
        assert code in [0, 1, 2], f"Agenda crashed: {stderr}"

    def test_smart_schedule_runs(self):
        """Smart-schedule command should complete."""
        code, stdout, stderr = run_cli_command("smart-schedule --help")

        assert code == 0, f"Smart-schedule help failed: {stderr}"


class TestCLIOutputFormat:
    """Test that CLI output is properly formatted."""

    def test_stats_uses_tables(self):
        """Stats should use formatted tables."""
        code, stdout, stderr = run_cli_command("stats")

        if code == 0:
            # Rich tables use box characters or separators
            assert "|" in stdout or "─" in stdout or "+" in stdout, (
                "Stats output should use table formatting"
            )

    def test_no_python_exceptions(self):
        """Commands should not print Python exceptions."""
        commands = ["stats", "path", "today", "persona"]

        for cmd in commands:
            code, stdout, stderr = run_cli_command(cmd)

            # Should not have traceback in stdout
            assert "Traceback" not in stdout, f"Exception in {cmd} stdout"

            # stderr may have logs but not crashes
            if "Traceback" in stderr:
                # Check if it's a real crash or just a warning
                assert code == 0, f"Crash in {cmd}: {stderr}"


class TestCLIPerformance:
    """Test CLI performance."""

    def test_stats_fast(self):
        """Stats should complete quickly."""
        import time

        start = time.time()

        code, stdout, stderr = run_cli_command("stats", timeout=10)

        elapsed = time.time() - start

        assert elapsed < 5, f"Stats took {elapsed:.1f}s, expected < 5s"

    def test_help_fast(self):
        """Help should complete very quickly."""
        import time

        start = time.time()

        code, stdout, stderr = run_cli_command("--help", timeout=5)

        elapsed = time.time() - start

        assert elapsed < 2, f"Help took {elapsed:.1f}s, expected < 2s"
