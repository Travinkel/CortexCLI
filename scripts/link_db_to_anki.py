#!/usr/bin/env python
"""
Link PostgreSQL learning_atoms to existing Anki notes by matching front text.

This allows us to:
1. Preserve review history from Anki
2. Enable bidirectional sync
3. Track which atoms are already in Anki
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.db.database import engine
from src.anki.anki_client import AnkiClient
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def link_atoms_to_anki():
    """Link DB atoms to Anki notes by matching front text."""

    console.print("\n[bold cyan]Linking DB Atoms to Anki Notes[/bold cyan]")
    console.print("=" * 50)

    # Create client with CCNA deck
    client = AnkiClient(deck_name="CCNA")

    # Verify connection
    try:
        version = client.get_version()
        console.print(f"[green]AnkiConnect v{version} connected[/green]")
    except Exception as e:
        console.print(f"[red]AnkiConnect not available: {e}[/red]")
        return

    # Get atoms without anki_note_id
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, front, atom_type
            FROM learning_atoms
            WHERE anki_note_id IS NULL
            AND atom_type IN ('flashcard', 'cloze')
            LIMIT 1000
        """)).fetchall()

    console.print(f"\nAtoms to link: {len(rows)}")

    linked = 0
    not_found = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Linking... (0/{len(rows)})", total=len(rows))

        for i, row in enumerate(rows):
            note_id = client.find_note_by_front(row.front)

            if note_id:
                # Update DB with the Anki note ID
                with engine.connect() as conn:
                    conn.execute(
                        text("UPDATE learning_atoms SET anki_note_id = :note_id WHERE id = :id"),
                        {"note_id": str(note_id), "id": str(row.id)}
                    )
                    conn.commit()
                linked += 1
            else:
                not_found += 1

            progress.update(task, description=f"Linking... ({i+1}/{len(rows)}, linked={linked})")
            progress.advance(task)

    console.print(f"\n[green]Linked: {linked} atoms[/green]")
    console.print(f"[yellow]Not found in Anki: {not_found} atoms[/yellow]")


if __name__ == "__main__":
    link_atoms_to_anki()
