#!/usr/bin/env python3
"""
Cortex CLI - Unified Learning Interface

A clean entry point that shows a main menu when launched without arguments,
allowing users to choose their learning activity.

Usage:
    python cortex.py           # Interactive menu
    python cortex.py study     # Start adaptive study session
    python cortex.py quiz      # Start quiz mode
    python cortex.py stats     # Show progress stats
    python cortex.py --help    # Show all commands
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

# Fix Windows encoding for Unicode
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import typer
from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.style import Style
from rich.table import Table
from rich.text import Text

# Theme colors
THEME = {
    "primary": "cyan",
    "secondary": "bright_blue",
    "accent": "yellow",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "dim": "bright_black",
    "white": "white",
}

console = Console()
app = typer.Typer(
    help="Cortex CLI - Your Learning Command Center",
    no_args_is_help=False,
    invoke_without_command=True,
)

# Struggle schema file location
STRUGGLE_FILE = Path.home() / ".cortex" / "struggle_schema.json"


def show_main_menu():
    """Display interactive main menu when no command is given."""
    console.clear()

    # Header
    header = Text()
    header.append("CORTEX", style=Style(color=THEME["primary"], bold=True))
    header.append(" - Neuro-Adaptive Learning Command Center", style=Style(color=THEME["dim"]))

    console.print(Panel(
        Align.center(header),
        border_style=Style(color=THEME["primary"]),
        box=box.DOUBLE,
        padding=(1, 2),
    ))

    # Menu options - organized by category
    menu = Table(
        show_header=False,
        box=box.SIMPLE,
        padding=(0, 2),
        expand=True,
    )
    menu.add_column("Key", style=Style(color=THEME["accent"], bold=True), width=6)
    menu.add_column("Action", style=Style(color=THEME["white"]), width=18)
    menu.add_column("Description", style=Style(color=THEME["dim"]))

    # Study section
    menu.add_row("[1]", "Study Session", "Adaptive learning with MCQ, T/F, Parsons")
    menu.add_row("[2]", "War Mode", "Aggressive cramming for weak areas")
    menu.add_row("[3]", "Flashcards", "Review flashcards and cloze deletions")
    menu.add_row("", "", "")

    # Cognitive section
    menu.add_row("[4]", "Neuro-Link", "View cognitive state (encoding/focus/fatigue)")
    menu.add_row("[5]", "Struggle Map", "Set modules/sections you struggle with")
    menu.add_row("[6]", "Persona", "View your learner profile")
    menu.add_row("", "", "")

    # Progress section
    menu.add_row("[7]", "Stats", "View progress and mastery")
    menu.add_row("[8]", "Today's Plan", "See what's due today")
    menu.add_row("[9]", "Learning Path", "Full CCNA module progress")
    menu.add_row("", "", "")

    # Tools section
    menu.add_row("[s]", "Sync", "Sync with Notion/Anki")
    menu.add_row("[g]", "Generate", "Generate new learning content")
    menu.add_row("[c]", "Schedule", "Smart calendar scheduling")
    menu.add_row("", "", "")
    menu.add_row("[q]", "Quit", "Exit Cortex")

    console.print(Panel(
        menu,
        title="[bold cyan]What would you like to do?[/bold cyan]",
        border_style=Style(color=THEME["secondary"]),
        box=box.ROUNDED,
        padding=(1, 1),
    ))

    # Quick stats footer with neuro-link preview
    try:
        from src.study.study_service import StudyService
        service = StudyService()
        stats = service.get_study_stats()

        footer = Text()
        footer.append("Due: ", style=Style(color=THEME["dim"]))
        footer.append(f"{stats['atoms']['total'] - stats['atoms']['mastered']} atoms",
                     style=Style(color=THEME["warning"]))
        footer.append("  |  Mastery: ", style=Style(color=THEME["dim"]))
        footer.append(f"{stats['mastery']['average']:.0f}%",
                     style=Style(color=THEME["success"] if stats['mastery']['average'] >= 70 else THEME["warning"]))

        # Show struggle count if any
        struggle_schema = load_struggle_schema()
        if struggle_schema:
            high_struggle = sum(1 for v in struggle_schema.values() if isinstance(v, (int, float)) and v >= 0.7)
            if high_struggle > 0:
                footer.append(f"  |  Struggles: ", style=Style(color=THEME["dim"]))
                footer.append(f"{high_struggle} areas", style=Style(color=THEME["error"]))

        console.print(Align.center(footer))
    except Exception:
        pass

    console.print()

    # Get user choice
    choice = Prompt.ask(
        "[cyan]>_[/cyan] Select option",
        choices=["1", "2", "3", "4", "5", "6", "7", "8", "9", "s", "g", "c", "q"],
        default="1",
    ).lower()

    return choice


def load_struggle_schema() -> dict:
    """Load struggle schema from file."""
    if STRUGGLE_FILE.exists():
        try:
            with open(STRUGGLE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            pass
    return {}


def save_struggle_schema(schema: dict) -> None:
    """Save struggle schema to file."""
    STRUGGLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STRUGGLE_FILE, "w") as f:
        json.dump(schema, f, indent=2)


def run_study_session(war_mode: bool = False):
    """Launch a study session."""
    from src.cli.cortex import CortexSession

    # Ask for configuration
    console.print()
    console.print("[bold cyan]SESSION CONFIGURATION[/bold cyan]\n")

    # Atom type selection
    console.print("[dim]Available types:[/dim]")
    console.print("  [1] MCQ - Multiple choice questions")
    console.print("  [2] True/False - Binary choice")
    console.print("  [3] Parsons - Order the steps")
    console.print("  [4] Mixed - All types (recommended)")
    console.print()

    type_choice = Prompt.ask(
        "[cyan]>_[/cyan] Select type",
        choices=["1", "2", "3", "4"],
        default="4",
    )

    type_map = {
        "1": ["mcq"],
        "2": ["true_false"],
        "3": ["parsons"],
        "4": ["mcq", "true_false", "parsons", "matching"],
    }
    selected_types = type_map.get(type_choice, ["mcq"])

    # Session length
    limit = Prompt.ask(
        "[cyan]>_[/cyan] Number of questions",
        default="20",
    )
    try:
        limit = int(limit)
    except ValueError:
        limit = 20

    console.print(f"\n[dim]Starting session: {limit} questions, types: {', '.join(selected_types)}[/dim]\n")

    # Launch session
    modules = list(range(11, 18) if war_mode else range(1, 18))
    session = CortexSession(modules=modules, limit=limit, war_mode=war_mode)
    session.run()


def run_flashcard_review():
    """Launch flashcard review mode."""
    console.print(Panel(
        "[yellow]Flashcard review sends cards to Anki.[/yellow]\n\n"
        "For in-app flashcard review, use:\n"
        "  [cyan]python -m src.cli.main anki review[/cyan]",
        title="[bold cyan]Flashcard Mode[/bold cyan]",
        border_style=Style(color=THEME["warning"]),
    ))

    # Could implement a simple flashcard viewer here
    Prompt.ask("\nPress Enter to return to menu", default="")


def show_stats():
    """Show study statistics."""
    from src.cli.cortex import cortex_stats
    cortex_stats()
    Prompt.ask("\nPress Enter to return to menu", default="")


def show_today():
    """Show today's study plan."""
    from src.cli.cortex import cortex_today
    cortex_today()
    Prompt.ask("\nPress Enter to return to menu", default="")


def run_sync():
    """Run sync operations."""
    console.print(Panel(
        "Sync Options:\n\n"
        "  [1] Notion -> PostgreSQL (pull content)\n"
        "  [2] PostgreSQL -> Anki (push to Anki)\n"
        "  [3] Anki -> PostgreSQL (pull stats)\n"
        "  [4] Full sync (all of the above)",
        title="[bold cyan]Sync[/bold cyan]",
        border_style=Style(color=THEME["secondary"]),
    ))

    choice = Prompt.ask(
        "[cyan]>_[/cyan] Select sync",
        choices=["1", "2", "3", "4", "q"],
        default="4",
    )

    if choice == "q":
        return

    console.print("\n[dim]Running sync...[/dim]")
    console.print("[yellow]Use: python -m src.cli.main sync --help for full options[/yellow]")
    Prompt.ask("\nPress Enter to return to menu", default="")


def run_generate():
    """Run content generation."""
    console.print(Panel(
        "Generation Options:\n\n"
        "  [1] Generate MCQ from concepts\n"
        "  [2] Generate cloze deletions\n"
        "  [3] Generate Parsons problems\n"
        "  [4] Batch generation (AI-powered)",
        title="[bold cyan]Generate Content[/bold cyan]",
        border_style=Style(color=THEME["secondary"]),
    ))

    console.print("\n[yellow]Use: python -m src.cli.main clean --help for generation[/yellow]")
    Prompt.ask("\nPress Enter to return to menu", default="")


def show_neurolink():
    """Show neuro-link cognitive status."""
    from src.cli.cortex import cortex_neurolink
    cortex_neurolink()
    Prompt.ask("\nPress Enter to return to menu", default="")


def show_persona():
    """Show learner persona."""
    from src.cli.cortex import cortex_persona
    cortex_persona()
    Prompt.ask("\nPress Enter to return to menu", default="")


def show_path():
    """Show learning path."""
    from src.cli.cortex import cortex_path
    cortex_path()
    Prompt.ask("\nPress Enter to return to menu", default="")


def run_schedule():
    """Run smart scheduling."""
    from src.cli.cortex import cortex_smart_schedule
    cortex_smart_schedule(days=7, hours=1)
    Prompt.ask("\nPress Enter to return to menu", default="")


def run_struggle_map():
    """Interactive struggle map configuration with submodule support."""
    console.clear()

    # CCNA curriculum structure with sections
    CCNA_CURRICULUM = {
        1: {
            "name": "Networking Today",
            "sections": {
                "1.1": "Networks Affect our Lives",
                "1.2": "Network Components",
                "1.3": "Network Representations and Topologies",
                "1.4": "Common Types of Networks",
                "1.5": "Internet Connections",
                "1.6": "Reliable Networks",
                "1.7": "Network Trends",
                "1.8": "Network Security",
            }
        },
        2: {
            "name": "Basic Switch and End Device Configuration",
            "sections": {
                "2.1": "Cisco IOS Access",
                "2.2": "IOS Navigation",
                "2.3": "The Command Structure",
                "2.4": "Basic Device Configuration",
                "2.5": "Save Configurations",
                "2.6": "Ports and Addresses",
                "2.7": "Configure IP Addressing",
                "2.8": "Verify Connectivity",
            }
        },
        3: {
            "name": "Protocols and Models",
            "sections": {
                "3.1": "The Rules",
                "3.2": "Protocols",
                "3.3": "Protocol Suites",
                "3.4": "Standards Organizations",
                "3.5": "Reference Models",
                "3.6": "Data Encapsulation",
                "3.7": "Data Access",
            }
        },
        4: {
            "name": "Physical Layer",
            "sections": {
                "4.1": "Purpose of the Physical Layer",
                "4.2": "Physical Layer Characteristics",
                "4.3": "Copper Cabling",
                "4.4": "UTP Cabling",
                "4.5": "Fiber-Optic Cabling",
                "4.6": "Wireless Media",
            }
        },
        5: {
            "name": "Number Systems",
            "sections": {
                "5.1": "Binary Number System",
                "5.2": "Hexadecimal Number System",
            }
        },
        6: {
            "name": "Data Link Layer",
            "sections": {
                "6.1": "Purpose of the Data Link Layer",
                "6.2": "Topologies",
                "6.3": "Data Link Frame",
            }
        },
        7: {
            "name": "Ethernet Switching",
            "sections": {
                "7.1": "Ethernet Frames",
                "7.2": "Ethernet MAC Address",
                "7.3": "The MAC Address Table",
                "7.4": "Switch Speeds and Forwarding Methods",
            }
        },
        8: {
            "name": "Network Layer",
            "sections": {
                "8.1": "Network Layer Characteristics",
                "8.2": "IPv4 Packet",
                "8.3": "IPv6 Packet",
                "8.4": "How a Host Routes",
                "8.5": "Router Routing Tables",
            }
        },
        9: {
            "name": "Address Resolution",
            "sections": {
                "9.1": "MAC and IP",
                "9.2": "ARP",
                "9.3": "IPv6 Neighbor Discovery",
            }
        },
        10: {
            "name": "Basic Router Configuration",
            "sections": {
                "10.1": "Configure Initial Router Settings",
                "10.2": "Configure Interfaces",
                "10.3": "Configure the Default Gateway",
            }
        },
        11: {
            "name": "IPv4 Addressing",
            "sections": {
                "11.1": "IPv4 Address Structure",
                "11.2": "IPv4 Unicast, Broadcast, and Multicast",
                "11.3": "Types of IPv4 Addresses",
                "11.4": "Network Segmentation",
                "11.5": "Subnet an IPv4 Network",
                "11.6": "Subnet a /16 and /8 Prefix",
                "11.7": "Subnet to Meet Requirements",
                "11.8": "VLSM",
                "11.9": "Structured Design",
            }
        },
        12: {
            "name": "IPv6 Addressing",
            "sections": {
                "12.1": "IPv4 Issues",
                "12.2": "IPv6 Address Representation",
                "12.3": "IPv6 Address Types",
                "12.4": "GUA and LLA Static Configuration",
                "12.5": "Dynamic Addressing for IPv6 GUAs",
                "12.6": "Dynamic Addressing for IPv6 LLAs",
                "12.7": "IPv6 Multicast Addresses",
                "12.8": "Subnet an IPv6 Network",
            }
        },
        13: {
            "name": "ICMP",
            "sections": {
                "13.1": "ICMP Messages",
                "13.2": "Ping and Traceroute Tests",
            }
        },
        14: {
            "name": "Transport Layer",
            "sections": {
                "14.1": "Transportation of Data",
                "14.2": "TCP Overview",
                "14.3": "UDP Overview",
                "14.4": "Port Numbers",
                "14.5": "TCP Communication Process",
                "14.6": "Reliability and Flow Control",
                "14.7": "UDP Communication",
            }
        },
        15: {
            "name": "Application Layer",
            "sections": {
                "15.1": "Application, Presentation, and Session",
                "15.2": "Peer-to-Peer",
                "15.3": "Web and Email Protocols",
                "15.4": "IP Addressing Services",
                "15.5": "File Sharing Services",
            }
        },
        16: {
            "name": "Network Security Fundamentals",
            "sections": {
                "16.1": "Security Threats and Vulnerabilities",
                "16.2": "Network Attacks",
                "16.3": "Network Attack Mitigations",
                "16.4": "Device Security",
            }
        },
        17: {
            "name": "Build a Small Network",
            "sections": {
                "17.1": "Devices in a Small Network",
                "17.2": "Small Network Applications and Protocols",
                "17.3": "Scale to Larger Networks",
                "17.4": "Verify Connectivity",
                "17.5": "Host and IOS Commands",
                "17.6": "Troubleshooting Methodologies",
                "17.7": "Troubleshooting Scenarios",
            }
        },
    }

    # Load existing schema
    schema = load_struggle_schema()

    console.print(Panel(
        "[bold cyan]STRUGGLE MAP CONFIGURATION[/bold cyan]\n\n"
        "Mark modules and sections you find difficult.\n"
        "This helps the adaptive scheduler prioritize remediation.",
        border_style=Style(color=THEME["primary"]),
        box=box.HEAVY,
    ))

    # Show current struggles summary
    if schema:
        high = [k for k, v in schema.items() if isinstance(v, (int, float)) and v >= 0.7]
        med = [k for k, v in schema.items() if isinstance(v, (int, float)) and 0.4 <= v < 0.7]
        if high:
            console.print(f"\n[red]HIGH struggle:[/red] {', '.join(sorted(high)[:10])}")
        if med:
            console.print(f"[yellow]MEDIUM struggle:[/yellow] {', '.join(sorted(med)[:10])}")

    console.print("\n[dim]Options:[/dim]")
    console.print("  [1] Set module struggle (entire module)")
    console.print("  [2] Set section struggle (specific section like 11.5)")
    console.print("  [3] View all struggles")
    console.print("  [4] Clear all struggles")
    console.print("  [q] Return to menu")

    choice = Prompt.ask("\n[cyan]>_[/cyan] Select", choices=["1", "2", "3", "4", "q"], default="1")

    if choice == "q":
        return

    if choice == "1":
        # Module-level struggle
        console.print("\n[cyan]Available Modules:[/cyan]")
        for mod_num, mod_data in CCNA_CURRICULUM.items():
            current = schema.get(str(mod_num), 0)
            indicator = "[red]!!![/red]" if current >= 0.7 else "[yellow]! [/yellow]" if current >= 0.4 else "[dim]  [/dim]"
            console.print(f"  {indicator} [{mod_num:2d}] {mod_data['name']}")

        modules_input = Prompt.ask(
            "\n[cyan]>_[/cyan] Enter module numbers (e.g., 11,12,14 or 11-14)",
            default=""
        )

        if modules_input:
            module_list = parse_range_input(modules_input, 1, 17)

            intensity = Prompt.ask(
                "Struggle intensity",
                choices=["low", "medium", "high", "clear"],
                default="high",
            )

            intensity_map = {"low": 0.3, "medium": 0.6, "high": 0.9, "clear": 0.0}
            value = intensity_map.get(intensity.lower(), 0.6)

            for mod in module_list:
                if value == 0:
                    schema.pop(str(mod), None)
                else:
                    schema[str(mod)] = value

            save_struggle_schema(schema)
            console.print(f"\n[green]Updated {len(module_list)} modules![/green]")

    elif choice == "2":
        # Section-level struggle
        console.print("\n[cyan]Enter section ID (e.g., 11.5 for VLSM, 12.8 for IPv6 Subnetting)[/cyan]")

        # Show section examples
        console.print("\n[dim]Popular sections:[/dim]")
        popular = ["11.5", "11.7", "11.8", "12.3", "12.8", "14.5", "14.6"]
        for sec_id in popular:
            mod_num = int(sec_id.split(".")[0])
            if mod_num in CCNA_CURRICULUM:
                sec_name = CCNA_CURRICULUM[mod_num]["sections"].get(sec_id, "Unknown")
                current = schema.get(sec_id, 0)
                indicator = "[red]!![/red]" if current >= 0.7 else "[yellow]![/yellow]" if current >= 0.4 else "  "
                console.print(f"  {indicator} [{sec_id}] {sec_name}")

        section_input = Prompt.ask(
            "\n[cyan]>_[/cyan] Enter section IDs (e.g., 11.5,11.7,12.8)",
            default=""
        )

        if section_input:
            sections = [s.strip() for s in section_input.split(",") if s.strip()]

            intensity = Prompt.ask(
                "Struggle intensity",
                choices=["low", "medium", "high", "clear"],
                default="high",
            )

            intensity_map = {"low": 0.3, "medium": 0.6, "high": 0.9, "clear": 0.0}
            value = intensity_map.get(intensity.lower(), 0.6)

            for sec in sections:
                if value == 0:
                    schema.pop(sec, None)
                else:
                    schema[sec] = value

            save_struggle_schema(schema)
            console.print(f"\n[green]Updated {len(sections)} sections![/green]")

    elif choice == "3":
        # View all struggles
        if not schema:
            console.print("\n[dim]No struggles recorded.[/dim]")
        else:
            console.print("\n[bold cyan]CURRENT STRUGGLE MAP[/bold cyan]\n")

            # Group by module
            by_module = {}
            for key, value in schema.items():
                if "." in key:
                    mod = key.split(".")[0]
                else:
                    mod = key
                if mod not in by_module:
                    by_module[mod] = []
                by_module[mod].append((key, value))

            for mod in sorted(by_module.keys(), key=lambda x: int(x) if x.isdigit() else 99):
                mod_int = int(mod) if mod.isdigit() else 0
                mod_name = CCNA_CURRICULUM.get(mod_int, {}).get("name", "Unknown")

                items = by_module[mod]
                for key, value in sorted(items):
                    bar = "#" * int(value * 10) + "-" * (10 - int(value * 10))
                    color = "red" if value >= 0.7 else "yellow" if value >= 0.4 else "dim"
                    if "." in key:
                        # Section
                        sec_name = CCNA_CURRICULUM.get(mod_int, {}).get("sections", {}).get(key, "")
                        console.print(f"  [{color}][{bar}][/{color}] {key}: {sec_name}")
                    else:
                        # Module
                        console.print(f"[{color}][{bar}][/{color}] Module {key}: {mod_name}")

    elif choice == "4":
        # Clear all
        if Confirm.ask("Clear all struggle data?", default=False):
            schema = {}
            save_struggle_schema(schema)
            console.print("\n[green]All struggles cleared![/green]")

    Prompt.ask("\nPress Enter to return to menu", default="")


def parse_range_input(input_str: str, min_val: int, max_val: int) -> list[int]:
    """Parse input like '11,12,14' or '11-14' or '11-14,16' into list of ints."""
    result = []
    for part in input_str.split(","):
        part = part.strip()
        if "-" in part:
            try:
                start, end = part.split("-")
                result.extend(range(int(start), int(end) + 1))
            except ValueError:
                pass
        elif part.isdigit():
            result.append(int(part))
    return [x for x in result if min_val <= x <= max_val]


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Cortex CLI - Your Learning Command Center

    Run without arguments to see the interactive menu.
    """
    if ctx.invoked_subcommand is None:
        # No command given - show interactive menu
        while True:
            choice = show_main_menu()

            # Study section
            if choice == "1":
                run_study_session(war_mode=False)
            elif choice == "2":
                run_study_session(war_mode=True)
            elif choice == "3":
                run_flashcard_review()

            # Cognitive section
            elif choice == "4":
                show_neurolink()
            elif choice == "5":
                run_struggle_map()
            elif choice == "6":
                show_persona()

            # Progress section
            elif choice == "7":
                show_stats()
            elif choice == "8":
                show_today()
            elif choice == "9":
                show_path()

            # Tools section
            elif choice == "s":
                run_sync()
            elif choice == "g":
                run_generate()
            elif choice == "c":
                run_schedule()

            elif choice == "q":
                console.print("\n[dim]Goodbye![/dim]\n")
                break


@app.command("study")
def cmd_study(
    war: bool = typer.Option(False, "--war", "-w", help="War mode (aggressive cramming)"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of questions"),
):
    """Start an adaptive study session."""
    from src.cli.cortex import CortexSession
    modules = list(range(11, 18) if war else range(1, 18))
    session = CortexSession(modules=modules, limit=limit, war_mode=war)
    session.run()


@app.command("stats")
def cmd_stats():
    """Show study statistics."""
    from src.cli.cortex import cortex_stats
    cortex_stats()


@app.command("today")
def cmd_today():
    """Show today's study plan."""
    from src.cli.cortex import cortex_today
    cortex_today()


@app.command("path")
def cmd_path():
    """Show full learning path with progress."""
    from src.cli.cortex import cortex_path
    cortex_path()


@app.command("neurolink")
def cmd_neurolink():
    """Show neuro-link cognitive status."""
    from src.cli.cortex import cortex_neurolink
    cortex_neurolink()


@app.command("persona")
def cmd_persona():
    """Show learner persona profile."""
    from src.cli.cortex import cortex_persona
    cortex_persona()


@app.command("struggle")
def cmd_struggle(
    modules: Optional[str] = typer.Option(None, "--modules", "-m", help="Modules to mark (e.g., 11,12,14)"),
    sections: Optional[str] = typer.Option(None, "--sections", "-s", help="Sections to mark (e.g., 11.5,12.8)"),
    intensity: str = typer.Option("high", "--intensity", "-i", help="low/medium/high/clear"),
    show: bool = typer.Option(False, "--show", help="Show current struggle map"),
    reset: bool = typer.Option(False, "--reset", help="Clear all struggles"),
):
    """
    Set CCNA modules/sections you struggle with.

    Examples:
        cortex struggle --show
        cortex struggle --modules 11,12,14 --intensity high
        cortex struggle --sections 11.5,11.8,12.8 --intensity high
        cortex struggle --reset
    """
    schema = load_struggle_schema()

    if reset:
        save_struggle_schema({})
        console.print("[green]Struggle schema cleared![/green]")
        return

    if show or (not modules and not sections):
        if not schema:
            console.print("[dim]No struggles recorded. Use --modules or --sections to add.[/dim]")
            return

        console.print("\n[bold cyan]STRUGGLE MAP[/bold cyan]\n")
        for key, value in sorted(schema.items()):
            bar = "#" * int(value * 10) + "-" * (10 - int(value * 10))
            color = "red" if value >= 0.7 else "yellow" if value >= 0.4 else "dim"
            console.print(f"[{color}][{bar}][/{color}] {key}")
        return

    intensity_map = {"low": 0.3, "medium": 0.6, "high": 0.9, "clear": 0.0}
    value = intensity_map.get(intensity.lower(), 0.6)

    updated = 0

    if modules:
        for mod in parse_range_input(modules, 1, 17):
            if value == 0:
                schema.pop(str(mod), None)
            else:
                schema[str(mod)] = value
            updated += 1

    if sections:
        for sec in sections.split(","):
            sec = sec.strip()
            if sec:
                if value == 0:
                    schema.pop(sec, None)
                else:
                    schema[sec] = value
                updated += 1

    save_struggle_schema(schema)
    console.print(f"[green]Updated {updated} items![/green]")


@app.command("schedule")
def cmd_schedule():
    """Show smart study schedule based on persona."""
    from src.cli.cortex import cortex_smart_schedule
    cortex_smart_schedule(days=7, hours=1)


if __name__ == "__main__":
    app()
