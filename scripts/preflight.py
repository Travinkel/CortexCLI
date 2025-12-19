"""
Pre-Flight System Check for Cortex V1.

Runs a comprehensive check sequence before daily study:
1. Database Connection Check
2. Data Integrity Audit (audit_db.py)
3. Simulation Stress Test (1000 cards, no exceptions)
4. Pedagogy Logic Tests (test_pedagogy.py)
5. Math Integrity Tests (test_numeric_comparison.py)

Returns SYSTEM READY or SYSTEM NOT READY.
"""

import os
import subprocess
import sys
from pathlib import Path

# Fix Windows encoding for Unicode output
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.panel import Panel

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import get_settings
from sqlalchemy import create_engine, text

console = Console(force_terminal=True)


def check_db_connection() -> bool:
    """Check if the database connection is valid."""
    console.print("[bold blue]1. Checking Database Connection...[/bold blue]")
    try:
        settings = get_settings()
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM learning_atoms"))
            count = result.scalar()
        console.print(f"[bold green]   ✅ Database connected. {count} atoms found.[/bold green]")
        return True
    except Exception as e:
        console.print(f"[bold red]   ❌ Database connection failed: {e}[/bold red]")
        return False


def run_audit_script() -> bool:
    """Run the data integrity audit script."""
    console.print("\n[bold blue]2. Running Data Integrity Audit...[/bold blue]")
    script_path = Path(__file__).parent / "qa" / "audit_db.py"

    if not script_path.exists():
        console.print(f"[bold red]   ❌ Audit script not found: {script_path}[/bold red]")
        return False

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120  # 2 minute timeout
    )

    # Print audit output (indented)
    for line in result.stdout.strip().split("\n"):
        console.print(f"   {line}")

    if result.returncode == 0:
        console.print("[bold green]   ✅ Data integrity audit passed.[/bold green]")
        return True
    else:
        console.print("[bold red]   ❌ Data integrity audit failed.[/bold red]")
        if result.stderr:
            console.print(f"   Error: {result.stderr}")
        return False


def run_simulation_test() -> bool:
    """Run 1000-card tutor stress test."""
    console.print("\n[bold blue]3. Running Simulation Stress Test (1000 cards)...[/bold blue]")
    script_path = PROJECT_ROOT / "tests" / "simulation" / "sim_study.py"

    if not script_path.exists():
        console.print(f"[bold red]   ❌ Simulation script not found: {script_path}[/bold red]")
        return False

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=300  # 5 minute timeout
    )

    # Print key lines from output
    output_lines = result.stdout.strip().split("\n")
    for line in output_lines:
        if any(marker in line for marker in ["✅", "❌", "PASSED", "FAILED", "PERSONA", "RESULTS"]):
            console.print(f"   {line}")

    if result.returncode == 0:
        console.print("[bold green]   ✅ Simulation stress test passed.[/bold green]")
        return True
    else:
        console.print("[bold red]   ❌ Simulation stress test failed.[/bold red]")
        if result.stderr:
            console.print(f"   Error: {result.stderr}")
        return False


def run_unit_tests(test_path: str, test_name: str) -> bool:
    """Run specific unit tests using pytest."""
    console.print(f"\n[bold blue]{test_name}...[/bold blue]")
    full_test_path = PROJECT_ROOT / test_path

    if not full_test_path.exists():
        console.print(f"[bold red]   ❌ Test file not found: {full_test_path}[/bold red]")
        return False

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(full_test_path), "-v", "--tb=short"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120  # 2 minute timeout
    )

    # Count passed/failed tests
    passed = result.stdout.count(" PASSED")
    failed = result.stdout.count(" FAILED")

    if result.returncode == 0:
        console.print(f"[bold green]   ✅ {test_name} passed ({passed} tests).[/bold green]")
        return True
    else:
        console.print(f"[bold red]   ❌ {test_name} failed ({failed} failures).[/bold red]")
        # Show failure details
        for line in result.stdout.split("\n"):
            if "FAILED" in line or "AssertionError" in line:
                console.print(f"   {line}")
        return False


def main() -> int:
    """Run all pre-flight checks."""
    console.print(Panel.fit(
        "[bold cyan]🚀 CORTEX V1 PRE-FLIGHT CHECKS[/bold cyan]",
        border_style="cyan"
    ))
    console.print("")

    # Define check sequence
    checks = [
        ("DB Connection", check_db_connection),
        ("Data Integrity", run_audit_script),
        ("Simulation Stress", run_simulation_test),
        ("Pedagogy Logic", lambda: run_unit_tests("tests/unit/test_pedagogy.py", "4. Pedagogy Logic Tests")),
        ("Math Integrity", lambda: run_unit_tests("tests/unit/test_numeric_comparison.py", "5. Math Integrity Tests")),
    ]

    results = {}

    for check_name, check_fn in checks:
        try:
            results[check_name] = check_fn()
        except subprocess.TimeoutExpired:
            console.print(f"[bold red]   ❌ {check_name} timed out.[/bold red]")
            results[check_name] = False
        except Exception as e:
            console.print(f"[bold red]   ❌ {check_name} error: {e}[/bold red]")
            results[check_name] = False

        # Stop on first failure (fail-fast)
        if not results[check_name]:
            break

    # Summary
    console.print("\n" + "=" * 50)
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    if all(results.values()) and len(results) == len(checks):
        console.print(Panel.fit(
            "[bold green]✅ SYSTEM READY[/bold green]\n"
            f"All {total} checks passed. Ready for study!",
            border_style="green"
        ))
        return 0
    else:
        failed_checks = [k for k, v in results.items() if not v]
        console.print(Panel.fit(
            "[bold red]❌ SYSTEM NOT READY[/bold red]\n"
            f"Passed: {passed}/{total}\n"
            f"Failed: {', '.join(failed_checks)}",
            border_style="red"
        ))
        return 1


if __name__ == "__main__":
    sys.exit(main())
