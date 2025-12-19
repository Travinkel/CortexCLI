#!/usr/bin/env python3
"""
Fresh Anki Sync - Delete and re-upload all atoms with correct structure.

This script:
1. Deletes all existing cortex cards from Anki
2. Batch uploads all quality atoms with correct note types
3. Creates filtered decks for efficient study

Usage:
    python scripts/anki/anki_fresh_sync.py
    python scripts/anki/anki_fresh_sync.py --dry-run
    python scripts/anki/anki_fresh_sync.py --skip-delete
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger
from rich.console import Console
from rich.table import Table

from src.anki.anki_client import AnkiClient
from src.anki.config import (
    BASE_DECK,
    CCNA_ITN_MODULE_NAMES,
    CURRICULUM_ID,
    SOURCE_TAG,
    get_module_deck_name,
)
from src.anki.push_service import push_clean_atoms
from src.db.database import get_session

console = Console()


def delete_cortex_cards(client: AnkiClient, dry_run: bool = False) -> int:
    """Delete all cards with cortex tag."""
    if dry_run:
        # Count cards that would be deleted
        note_ids = client._invoke("findNotes", {"query": f"tag:{SOURCE_TAG}"})
        console.print(f"[yellow]DRY RUN: Would delete {len(note_ids or [])} notes with tag '{SOURCE_TAG}'[/yellow]")
        return len(note_ids or [])

    try:
        note_ids = client._invoke("findNotes", {"query": f"tag:{SOURCE_TAG}"})
        if not note_ids:
            console.print("[green]No existing cortex cards found[/green]")
            return 0

        client._invoke("deleteNotes", {"notes": note_ids})
        console.print(f"[green]Deleted {len(note_ids)} cortex cards[/green]")
        return len(note_ids)
    except Exception as exc:
        console.print(f"[red]Failed to delete cards: {exc}[/red]")
        return 0


def clear_anki_sync_state(dry_run: bool = False) -> int:
    """Clear anki_note_id and anki_synced_at from database for fresh sync."""
    if dry_run:
        console.print("[yellow]DRY RUN: Would clear Anki sync state from database[/yellow]")
        return 0

    session = next(get_session())
    try:
        from sqlalchemy import text
        result = session.execute(
            text("UPDATE learning_atoms SET anki_note_id = NULL, anki_synced_at = NULL WHERE anki_note_id IS NOT NULL")
        )
        session.commit()
        console.print(f"[green]Cleared Anki sync state for {result.rowcount} atoms[/green]")
        return result.rowcount
    except Exception as exc:
        console.print(f"[red]Failed to clear sync state: {exc}[/red]")
        session.rollback()
        return 0


def create_module_decks(client: AnkiClient, dry_run: bool = False) -> None:
    """Create all module subdecks."""
    if dry_run:
        console.print("[yellow]DRY RUN: Would create module decks[/yellow]")
        return

    for module_num in CCNA_ITN_MODULE_NAMES:
        deck_name = get_module_deck_name(module_num)
        try:
            client._invoke("createDeck", {"deck": deck_name})
            logger.debug("Created deck: {}", deck_name)
        except Exception:
            pass  # Deck might exist


def create_filtered_decks(client: AnkiClient, dry_run: bool = False) -> None:
    """Create filtered decks for efficient study."""
    # Struggle sections - areas needing extra focus
    struggle_query = (
        f'deck:{BASE_DECK}::* ('
        'tag:section:2.1.4 OR tag:section:2.1.5 OR tag:section:2.2.1 OR tag:section:2.2.2 OR '
        'tag:section:2.2.4 OR tag:section:2.3.1 OR tag:section:2.3.2 OR tag:section:2.3.3 OR '
        'tag:section:2.3.5 OR tag:section:2.4.2 OR tag:section:2.4.3 OR tag:section:2.4.5 OR '
        'tag:section:2.6.2 OR tag:section:2.7.1 OR tag:section:2.7.4 OR tag:section:2.8.1 OR '
        'tag:section:2.8.2 OR tag:section:3.1.2 OR tag:section:3.1.3 OR tag:section:3.2.* OR '
        'tag:section:3.3.* OR tag:section:4.1.* OR tag:section:4.2.1 OR tag:section:4.2.2 OR '
        'tag:section:4.2.3 OR tag:section:4.3.* OR tag:section:5.1.1 OR tag:section:5.1.2 OR '
        'tag:section:5.1.4 OR tag:section:5.1.5 OR tag:section:5.2.1 OR tag:section:5.2.2 OR '
        'tag:section:5.2.3 OR tag:section:5.3.1 OR tag:section:5.3.2 OR tag:section:5.3.3 OR '
        'tag:section:5.4.1 OR tag:section:5.4.2 OR tag:section:6.1.* OR tag:section:6.2.* OR '
        'tag:section:6.3.* OR tag:section:7.1.2 OR tag:section:7.1.3 OR tag:section:7.1.4 OR '
        'tag:section:7.2.1 OR tag:section:7.2.2 OR tag:section:7.2.3 OR tag:section:7.2.4 OR '
        'tag:section:7.2.5 OR tag:section:7.2.6 OR tag:section:8.1.* OR tag:section:8.2.* OR '
        'tag:section:8.3.* OR tag:section:9.1.* OR tag:section:9.2.* OR tag:section:9.3.* OR '
        'tag:section:10.1.* OR tag:section:10.2.* OR tag:section:10.3.* OR tag:section:10.4.* OR '
        'tag:section:11.1.* OR tag:section:11.2.* OR tag:section:11.3.* OR tag:section:11.4.* OR '
        'tag:section:11.5.* OR tag:section:11.6.* OR tag:section:11.7.* OR tag:section:11.8.* OR '
        'tag:section:12.1.* OR tag:section:12.2.* OR tag:section:12.3.* OR tag:section:12.4.* OR '
        'tag:section:12.5.* OR tag:section:12.6.* OR tag:section:13.1.* OR tag:section:13.2.* OR '
        'tag:section:14.* OR tag:section:15.* OR tag:section:16.* OR tag:section:17.*'
        ') -is:suspended'
    )

    filtered_decks = [
        # Priority: Struggle sections
        ("Study::Struggle Sections", struggle_query),
        ("Study::Struggle Due", f'{struggle_query} is:due'),
        # By module - study one module at a time
        *[
            (f"Study::ITN M{m:02d}", f'"deck:{BASE_DECK}::M{m:02d}*" is:due')
            for m in CCNA_ITN_MODULE_NAMES
        ],
        # By type
        ("Study::All Due Flashcards", f'"deck:{BASE_DECK}*" tag:type:flashcard is:due'),
        ("Study::All Due Cloze", f'"deck:{BASE_DECK}*" tag:type:cloze is:due'),
        # All due
        ("Study::All Due", f'"deck:{BASE_DECK}*" is:due'),
        # New cards only
        ("Study::New Cards", f'"deck:{BASE_DECK}*" is:new'),
        # Weak cards (low ease)
        ("Study::Weak Cards", f'"deck:{BASE_DECK}*" prop:ease<2.0'),
    ]

    if dry_run:
        console.print("[yellow]DRY RUN: Would create filtered decks:[/yellow]")
        for name, query in filtered_decks:
            console.print(f"  - {name}: {query}")
        return

    console.print("\n[bold]Creating filtered decks...[/bold]")
    created = 0
    for name, query in filtered_decks:
        try:
            # AnkiConnect createFilteredDeck API
            # Note: Anki's filtered deck API is limited, we might need to use GUI
            client._invoke(
                "createFilteredDeck",
                {
                    "newDeckName": name,
                    "searchQuery": query,
                    "gatherCount": 100,
                    "reschedule": True,
                },
            )
            created += 1
            logger.debug("Created filtered deck: {}", name)
        except Exception as exc:
            # Filtered deck creation often fails via API, log but continue
            logger.warning("Could not create filtered deck '{}': {}", name, exc)

    if created > 0:
        console.print(f"[green]Created {created} filtered decks[/green]")
    else:
        console.print("[yellow]Filtered deck creation via API failed (Anki limitation)[/yellow]")
        console.print("[yellow]Create manually: Tools > Create Filtered Deck[/yellow]")
        console.print("\nSuggested queries:")
        for name, query in filtered_decks[:5]:  # Show first 5
            console.print(f"  {name}: {query}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fresh Anki sync with correct structure")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--skip-delete", action="store_true", help="Skip deletion step (RECOMMENDED)")
    parser.add_argument(
        "--force-delete",
        action="store_true",
        help="DANGER: Delete ALL cortex cards from Anki before sync. "
             "This loses all FSRS scheduling data (ease, interval, reviews). "
             "Only use for fresh start scenarios."
    )
    parser.add_argument("--min-quality", default="B", help="Minimum quality grade (A/B/C/D/F)")
    args = parser.parse_args()

    # Safety check: deletion requires explicit --force-delete flag
    if not args.skip_delete and not args.force_delete:
        console.print("[yellow]⚠️  SAFETY: Deletion is now opt-in to protect your FSRS data.[/yellow]")
        console.print("[yellow]   Use --force-delete to delete all cards (loses scheduling data)[/yellow]")
        console.print("[yellow]   Use --skip-delete to sync without deletion (RECOMMENDED)[/yellow]")
        console.print()
        args.skip_delete = True  # Default to safe mode

    console.print("\n[bold]Fresh Anki Sync[/bold]")
    console.print(f"  Base deck: {BASE_DECK}")
    console.print(f"  Curriculum: {CURRICULUM_ID}")
    console.print(f"  Min quality: {args.min_quality}")
    console.print(f"  Dry run: {args.dry_run}")
    console.print()

    # Initialize client
    client = AnkiClient()

    # Check connection
    if not args.dry_run and not client.check_connection():
        console.print("[red]Cannot connect to Anki. Ensure Anki is running with AnkiConnect.[/red]")
        return 1

    stats = {"deleted": 0, "created": 0, "updated": 0, "errors": []}

    # Step 1: Delete existing cortex cards (only with --force-delete)
    if args.force_delete and not args.skip_delete:
        console.print("\n[bold red]Step 1: DELETING existing cortex cards (--force-delete)[/bold red]")
        console.print("[red]⚠️  This will lose all FSRS scheduling data![/red]")
        stats["deleted"] = delete_cortex_cards(client, dry_run=args.dry_run)

        # Clear database sync state
        clear_anki_sync_state(dry_run=args.dry_run)
    else:
        console.print("\n[bold green]Step 1: Skipping deletion (safe mode)[/bold green]")

    # Step 2: Create deck structure
    console.print("\n[bold]Step 2: Creating deck structure...[/bold]")
    create_module_decks(client, dry_run=args.dry_run)

    # Step 3: Push atoms to Anki
    # Use incremental mode when not deleting (preserves existing cards)
    # Use full mode after deletion (creates all fresh)
    use_incremental = not args.force_delete or args.skip_delete
    mode_str = "incremental (safe)" if use_incremental else "full (after delete)"
    console.print(f"\n[bold]Step 3: Uploading atoms to Anki ({mode_str})...[/bold]")
    push_stats = push_clean_atoms(
        anki_client=client,
        min_quality=args.min_quality,
        dry_run=args.dry_run,
        incremental=use_incremental,
    )
    stats["created"] = push_stats.get("created", 0)
    stats["updated"] = push_stats.get("updated", 0)
    stats["errors"] = push_stats.get("errors", [])

    # Step 4: Create filtered decks
    console.print("\n[bold]Step 4: Creating filtered decks...[/bold]")
    create_filtered_decks(client, dry_run=args.dry_run)

    # Summary
    table = Table(title="Sync Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Cards deleted", str(stats["deleted"]))
    table.add_row("Cards created", str(stats["created"]))
    table.add_row("Cards updated", str(stats["updated"]))
    table.add_row("Errors", str(len(stats["errors"])))

    console.print()
    console.print(table)

    if stats["errors"]:
        console.print("\n[yellow]Errors:[/yellow]")
        for err in stats["errors"][:10]:  # Show first 10
            console.print(f"  - {err}")

    if args.dry_run:
        console.print("\n[yellow]DRY RUN - No changes made[/yellow]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
