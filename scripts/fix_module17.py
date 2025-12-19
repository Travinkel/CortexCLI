#!/usr/bin/env python3
"""
Fix Module 17 Data - Add missing sections and re-link atoms.

This script:
1. Adds Module 17 sections to ccna_sections table
2. Re-links M17 atoms to correct ccna_section_id
3. Moves M17 cards to correct deck in Anki (non-destructive)

Usage:
    python scripts/fix_module17.py --dry-run     # Preview changes
    python scripts/fix_module17.py               # Apply changes
"""

from __future__ import annotations

import argparse
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from rich.console import Console
from rich.table import Table
from sqlalchemy import text

from src.anki.anki_client import AnkiClient
from src.anki.config import get_module_deck_name
from src.db.database import session_scope

console = Console()

# Module 17 section titles from CCNA ITN curriculum
# Build a Small Network
M17_SECTIONS = {
    "17.1": ("Device Management", 2, None),
    "17.2": ("Small Network Topologies", 2, None),
    "17.2.1": ("Common Network Topologies", 3, "17.2"),
    "17.2.2": ("Small Network Device Selection", 3, "17.2"),
    "17.2.3": ("IP Addressing", 3, "17.2"),
    "17.2.4": ("Redundancy in Small Networks", 3, "17.2"),
    "17.2.5": ("Traffic Management", 3, "17.2"),
    "17.3": ("Small Network Applications and Protocols", 2, None),
    "17.3.1": ("Common Applications", 3, "17.3"),
    "17.3.2": ("Common Protocols", 3, "17.3"),
    "17.3.3": ("Voice and Video Applications", 3, "17.3"),
    "17.4": ("Scale to Larger Networks", 2, None),
    "17.4.1": ("Small Network Growth", 3, "17.4"),
    "17.4.2": ("Protocol Analysis", 3, "17.4"),
    "17.4.3": ("Employee Network Usage", 3, "17.4"),
    "17.5": ("Verify Connectivity", 2, None),
    "17.5.1": ("Verify Connectivity with Ping", 3, "17.5"),
    "17.5.2": ("Extended Ping", 3, "17.5"),
    "17.5.3": ("Verify Connectivity with Traceroute", 3, "17.5"),
    "17.5.4": ("Extended Traceroute", 3, "17.5"),
    "17.6": ("Host and IOS Commands", 2, None),
    "17.6.1": ("IP Configuration on Windows", 3, "17.6"),
    "17.6.2": ("IP Configuration on Linux", 3, "17.6"),
    "17.6.3": ("IP Configuration on macOS", 3, "17.6"),
    "17.6.4": ("The arp Command", 3, "17.6"),
    "17.7": ("Troubleshooting Methodologies", 2, None),
    "17.7.1": ("Basic Troubleshooting Approaches", 3, "17.7"),
    "17.7.2": ("Resolve or Escalate", 3, "17.7"),
    "17.7.3": ("The debug Command", 3, "17.7"),
    "17.7.4": ("The terminal monitor Command", 3, "17.7"),
    "17.8": ("Troubleshooting Scenarios", 2, None),
    "17.8.1": ("Duplex and Speed Mismatch", 3, "17.8"),
    "17.8.2": ("IP Addressing Issues", 3, "17.8"),
    "17.8.3": ("Default Gateway Issues", 3, "17.8"),
    "17.8.4": ("DNS Issues", 3, "17.8"),
}


def add_m17_sections(dry_run: bool = False) -> int:
    """Add Module 17 sections to ccna_sections table."""
    console.print("\n[bold]Step 1: Adding Module 17 sections[/bold]")

    with session_scope() as session:
        # Check existing M17 sections
        result = session.execute(text(
            "SELECT COUNT(*) FROM ccna_sections WHERE module_number = 17"
        ))
        existing = result.scalar()

        if existing > 0:
            console.print(f"[yellow]Found {existing} existing M17 sections - skipping[/yellow]")
            return 0

        if dry_run:
            console.print(f"[yellow]DRY RUN: Would add {len(M17_SECTIONS)} M17 sections[/yellow]")
            return len(M17_SECTIONS)

        # Insert sections
        count = 0
        for section_id, (title, level, parent) in M17_SECTIONS.items():
            session.execute(text("""
                INSERT INTO ccna_sections (id, module_number, section_id, title, level, parent_section_id, created_at, updated_at)
                VALUES (:id, 17, :section_id, :title, :level, :parent, NOW(), NOW())
                ON CONFLICT (section_id) DO NOTHING
            """), {
                "id": str(uuid.uuid4()),
                "section_id": section_id,
                "title": title,
                "level": level,
                "parent": parent,
            })
            count += 1

        session.commit()
        console.print(f"[green]Added {count} Module 17 sections[/green]")
        return count


def relink_m17_atoms(dry_run: bool = False) -> int:
    """Re-link M17 atoms to correct ccna_section_id."""
    console.print("\n[bold]Step 2: Re-linking M17 atoms to correct sections[/bold]")

    with session_scope() as session:
        # Get all M17 atoms
        result = session.execute(text("""
            SELECT id, card_id, ccna_section_id
            FROM learning_atoms
            WHERE card_id LIKE 'NET-M17%'
        """))
        atoms = result.fetchall()

        if not atoms:
            console.print("[yellow]No M17 atoms found[/yellow]")
            return 0

        # Get M17 sections for lookup
        sections_result = session.execute(text("""
            SELECT section_id FROM ccna_sections WHERE module_number = 17
        """))
        valid_sections = {row[0] for row in sections_result}

        if not valid_sections:
            console.print("[red]No M17 sections found - run Step 1 first[/red]")
            return 0

        updates = []
        for atom_id, card_id, current_section in atoms:
            # Extract section from card_id: NET-M17-S2-4-1-FC-005 -> 17.2.4.1
            # Or NET-M17-S1-FC-006 -> 17.1
            match = re.search(r'NET-M17-S(\d+(?:-\d+)*)', card_id)
            if not match:
                continue

            section_parts = match.group(1).split('-')
            # Convert S2-4-1 to 17.2.4.1, then find closest match
            # Try progressively shorter section IDs
            for i in range(len(section_parts), 0, -1):
                candidate = "17." + ".".join(section_parts[:i])
                if candidate in valid_sections:
                    if current_section != candidate:
                        updates.append((atom_id, card_id, current_section, candidate))
                    break

        if not updates:
            console.print("[green]All M17 atoms already correctly linked[/green]")
            return 0

        if dry_run:
            console.print(f"[yellow]DRY RUN: Would update {len(updates)} atoms[/yellow]")
            for atom_id, card_id, old, new in updates[:5]:
                console.print(f"  {card_id}: {old} -> {new}")
            if len(updates) > 5:
                console.print(f"  ... and {len(updates) - 5} more")
            return len(updates)

        # Apply updates
        for atom_id, card_id, old_section, new_section in updates:
            session.execute(text("""
                UPDATE learning_atoms
                SET ccna_section_id = :new_section, updated_at = NOW()
                WHERE id = :atom_id
            """), {"atom_id": atom_id, "new_section": new_section})

        session.commit()
        console.print(f"[green]Updated {len(updates)} M17 atoms[/green]")
        return len(updates)


def move_m17_cards_in_anki(dry_run: bool = False) -> int:
    """Move M17 cards to correct deck in Anki (non-destructive)."""
    console.print("\n[bold]Step 3: Moving M17 cards to correct deck in Anki[/bold]")

    client = AnkiClient()

    if not dry_run and not client.check_connection():
        console.print("[red]Cannot connect to Anki - skipping[/red]")
        return 0

    m17_deck = get_module_deck_name(17)  # CCNA::ITN::M17 Build a Small Network

    with session_scope() as session:
        # Get M17 atoms with anki_note_id
        result = session.execute(text("""
            SELECT la.card_id, la.anki_note_id
            FROM learning_atoms la
            WHERE la.card_id LIKE 'NET-M17%'
              AND la.anki_note_id IS NOT NULL
        """))
        atoms = result.fetchall()

        if not atoms:
            console.print("[yellow]No M17 cards with Anki IDs found[/yellow]")
            return 0

        # Check which cards are in wrong deck
        cards_to_move = []
        for card_id, note_id in atoms:
            if dry_run:
                cards_to_move.append((card_id, note_id))
                continue

            # Get current deck
            try:
                notes_info = client._invoke("notesInfo", {"notes": [note_id]})
                if notes_info and notes_info[0].get("cards"):
                    card_ids = notes_info[0]["cards"]
                    cards_info = client._invoke("cardsInfo", {"cards": card_ids})
                    if cards_info:
                        current_deck = cards_info[0].get("deckName", "")
                        if not current_deck.startswith("CCNA::ITN::M17"):
                            cards_to_move.append((card_id, card_ids[0], current_deck))
            except Exception as e:
                logger.debug("Error checking card {}: {}", card_id, e)

        if not cards_to_move:
            console.print("[green]All M17 cards already in correct deck[/green]")
            return 0

        if dry_run:
            console.print(f"[yellow]DRY RUN: Would move up to {len(cards_to_move)} cards to {m17_deck}[/yellow]")
            return len(cards_to_move)

        # Ensure M17 deck exists
        try:
            client._invoke("createDeck", {"deck": m17_deck})
        except Exception:
            pass

        # Move cards
        moved = 0
        for concept_id, card_id, old_deck in cards_to_move:
            try:
                client._invoke("changeDeck", {"cards": [card_id], "deck": m17_deck})
                moved += 1
                logger.debug("Moved {} from {} to {}", concept_id, old_deck, m17_deck)
            except Exception as e:
                logger.error("Failed to move {}: {}", concept_id, e)

        console.print(f"[green]Moved {moved} cards to {m17_deck}[/green]")

        # Update anki_deck in database
        session.execute(text("""
            UPDATE learning_atoms
            SET anki_deck = :deck
            WHERE card_id LIKE 'NET-M17%'
              AND anki_note_id IS NOT NULL
        """), {"deck": m17_deck})
        session.commit()

        return moved


def main() -> int:
    parser = argparse.ArgumentParser(description="Fix Module 17 data")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    args = parser.parse_args()

    console.print("\n[bold]Module 17 Fix Script[/bold]")
    console.print(f"  Dry run: {args.dry_run}")

    # Summary table
    table = Table(title="Fix Summary")
    table.add_column("Step", style="cyan")
    table.add_column("Action", style="white")
    table.add_column("Count", justify="right", style="green")

    # Step 1: Add sections
    sections_count = add_m17_sections(dry_run=args.dry_run)
    table.add_row("1", "Add M17 sections", str(sections_count))

    # Step 2: Re-link atoms
    relink_count = relink_m17_atoms(dry_run=args.dry_run)
    table.add_row("2", "Re-link atoms", str(relink_count))

    # Step 3: Move Anki cards
    move_count = move_m17_cards_in_anki(dry_run=args.dry_run)
    table.add_row("3", "Move Anki cards", str(move_count))

    console.print()
    console.print(table)

    if args.dry_run:
        console.print("\n[yellow]DRY RUN - No changes made[/yellow]")
    else:
        console.print("\n[green]Module 17 fix complete![/green]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
