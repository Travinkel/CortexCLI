"""
User Flag Review Tool.

Admin interface to review and resolve user-reported issues with learning atoms.
Displays atoms flagged by users, grouped by count, and allows:
- Viewing flag details
- Fixing the issue
- Quarantining broken atoms
- Dismissing false reports

Usage:
    python scripts/qa/review_flags.py              # Review all unresolved flags
    python scripts/qa/review_flags.py --min 2     # Only show atoms with 2+ flags
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from sqlalchemy import text

from src.db.database import get_session

console = Console()


def get_flagged_atoms(min_flags: int = 1) -> list[dict]:
    """Get atoms with unresolved flags, sorted by flag count."""
    with next(get_session()) as session:
        result = session.execute(text("""
            SELECT
                la.id,
                la.card_id,
                la.atom_type,
                la.front,
                la.back,
                COUNT(uf.id) as flag_count,
                ARRAY_AGG(DISTINCT uf.flag_type) as flag_types,
                ARRAY_AGG(uf.flag_reason) FILTER (WHERE uf.flag_reason IS NOT NULL) as reasons
            FROM learning_atoms la
            JOIN user_flags uf ON la.id = uf.atom_id
            WHERE uf.resolved_at IS NULL
            GROUP BY la.id, la.card_id, la.atom_type, la.front, la.back
            HAVING COUNT(uf.id) >= :min_flags
            ORDER BY COUNT(uf.id) DESC
        """), {"min_flags": min_flags})

        return [
            {
                "id": str(row[0]),
                "card_id": row[1],
                "atom_type": row[2],
                "front": row[3][:100] if row[3] else "",
                "back": row[4][:200] if row[4] else "",
                "flag_count": row[5],
                "flag_types": row[6],
                "reasons": [r for r in (row[7] or []) if r],
            }
            for row in result.fetchall()
        ]


def resolve_flags(atom_id: str, resolution: str, notes: str = "") -> int:
    """Mark all flags for an atom as resolved."""
    with next(get_session()) as session:
        result = session.execute(text("""
            UPDATE user_flags
            SET resolved_at = NOW(),
                resolution_notes = :notes
            WHERE atom_id = :atom_id AND resolved_at IS NULL
            RETURNING id
        """), {"atom_id": atom_id, "notes": f"{resolution}: {notes}" if notes else resolution})
        count = len(result.fetchall())
        session.commit()
        return count


def quarantine_atom(atom_id: str, reason: str) -> bool:
    """Move atom to quarantine and resolve its flags."""
    with next(get_session()) as session:
        # Get atom data
        atom = session.execute(text("""
            SELECT id, card_id, atom_type, front, back, media_type, media_code
            FROM learning_atoms WHERE id = :id
        """), {"id": atom_id}).fetchone()

        if not atom:
            return False

        # Insert into quarantine
        session.execute(text("""
            INSERT INTO quarantine_atoms
            (original_id, card_id, atom_type, front, back, media_type, media_code, quarantine_reason)
            VALUES (:id, :card_id, :atom_type, :front, :back, :media_type, :media_code, :reason)
            ON CONFLICT DO NOTHING
        """), {
            "id": atom_id,
            "card_id": atom[1],
            "atom_type": atom[2],
            "front": atom[3],
            "back": atom[4],
            "media_type": atom[5],
            "media_code": atom[6],
            "reason": reason,
        })

        # Delete from learning_atoms
        session.execute(text("DELETE FROM learning_atoms WHERE id = :id"), {"id": atom_id})

        # Resolve flags
        session.execute(text("""
            UPDATE user_flags
            SET resolved_at = NOW(), resolution_notes = 'Quarantined: ' || :reason
            WHERE atom_id = :atom_id
        """), {"atom_id": atom_id, "reason": reason})

        session.commit()
        return True


def display_atom(atom: dict) -> None:
    """Display detailed atom info."""
    console.print(Panel(
        f"[bold]Front:[/bold]\n{atom['front']}\n\n"
        f"[bold]Back:[/bold]\n{atom['back']}\n\n"
        f"[bold]Type:[/bold] {atom['atom_type']}  |  "
        f"[bold]Card ID:[/bold] {atom['card_id'] or 'N/A'}",
        title=f"[bold red]Atom {atom['id'][:8]}... ({atom['flag_count']} flags)[/bold red]",
        border_style="red",
    ))

    # Show flag types and reasons
    console.print(f"[yellow]Flag Types:[/yellow] {', '.join(atom['flag_types'])}")
    if atom['reasons']:
        console.print("[yellow]User Reasons:[/yellow]")
        for reason in atom['reasons'][:5]:
            console.print(f"  - {reason}")


def review_flags(min_flags: int = 1) -> None:
    """Interactive flag review interface."""
    console.print("\n[bold cyan]USER FLAG REVIEW[/bold cyan]\n")

    atoms = get_flagged_atoms(min_flags)

    if not atoms:
        console.print("[green]No flagged atoms found![/green]")
        return

    # Summary table
    table = Table(title=f"Flagged Atoms ({len(atoms)} total)")
    table.add_column("#", width=3)
    table.add_column("Flags", width=5)
    table.add_column("Type", width=10)
    table.add_column("Flag Types", width=20)
    table.add_column("Front Preview", max_width=50)

    for i, atom in enumerate(atoms[:20], 1):
        table.add_row(
            str(i),
            str(atom['flag_count']),
            atom['atom_type'],
            ', '.join(atom['flag_types']),
            atom['front'][:50] + "..." if len(atom['front']) > 50 else atom['front'],
        )

    console.print(table)

    if len(atoms) > 20:
        console.print(f"[dim]... and {len(atoms) - 20} more[/dim]")

    # Action loop
    while True:
        console.print("\n[bold]Actions:[/bold]")
        console.print("  [cyan]#[/cyan] - Review specific atom (enter number)")
        console.print("  [cyan]q[/cyan] - Quit")

        choice = Prompt.ask(">", default="q").strip().lower()

        if choice == "q":
            break

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(atoms):
                review_single_atom(atoms[idx])
        except ValueError:
            console.print("[red]Invalid choice[/red]")


def review_single_atom(atom: dict) -> None:
    """Review and take action on a single atom."""
    display_atom(atom)

    console.print("\n[bold]Actions:[/bold]")
    console.print("  [cyan]f[/cyan] - Fix (edit in DB manually, then dismiss flags)")
    console.print("  [cyan]q[/cyan] - Quarantine (remove from study pool)")
    console.print("  [cyan]d[/cyan] - Dismiss (false reports, no issue)")
    console.print("  [cyan]s[/cyan] - Skip (come back later)")

    action = Prompt.ask(">", choices=["f", "q", "d", "s"], default="s")

    if action == "f":
        notes = Prompt.ask("Fix notes (what was corrected)")
        count = resolve_flags(atom['id'], "fixed", notes)
        console.print(f"[green]Resolved {count} flags as FIXED[/green]")

    elif action == "q":
        reason = Prompt.ask("Quarantine reason")
        if quarantine_atom(atom['id'], reason):
            console.print(f"[green]Atom quarantined[/green]")
        else:
            console.print("[red]Quarantine failed[/red]")

    elif action == "d":
        notes = Prompt.ask("Dismissal reason", default="False report")
        count = resolve_flags(atom['id'], "dismissed", notes)
        console.print(f"[green]Dismissed {count} flags[/green]")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Review user-flagged atoms")
    parser.add_argument("--min", type=int, default=1, help="Minimum flags to show (default: 1)")

    args = parser.parse_args()
    review_flags(min_flags=args.min)


if __name__ == "__main__":
    main()
