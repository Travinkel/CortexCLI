"""
Cortex ASI Visual Components.

"Digital Neocortex" aesthetic with cyan/electric blue color scheme.
Provides ASCII art, spinners, and themed UI components.
"""
from __future__ import annotations

import time
from typing import Optional

from rich import box
from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.style import Style
from rich.text import Text


# =============================================================================
# ASI COLOR THEME
# =============================================================================

CORTEX_THEME = {
    "primary": "#00FFFF",       # Cyan - main accent
    "secondary": "#0077BE",     # Electric Blue - secondary accent
    "accent": "#00D4FF",        # Bright Cyan - highlights
    "background": "#0a0a1a",    # Deep Navy - background
    "success": "#00FF88",       # Neon Green - correct answers
    "warning": "#FFD700",       # Gold - warnings/retries
    "error": "#FF3366",         # Hot Pink/Red - incorrect
    "dim": "#4a5568",           # Muted gray - secondary text
    "white": "#E0E0E0",         # Off-white - primary text
}

# Rich styles for easy use
STYLES = {
    "cortex_primary": Style(color=CORTEX_THEME["primary"], bold=True),
    "cortex_secondary": Style(color=CORTEX_THEME["secondary"]),
    "cortex_accent": Style(color=CORTEX_THEME["accent"], bold=True),
    "cortex_success": Style(color=CORTEX_THEME["success"], bold=True),
    "cortex_warning": Style(color=CORTEX_THEME["warning"], bold=True),
    "cortex_error": Style(color=CORTEX_THEME["error"], bold=True),
    "cortex_dim": Style(color=CORTEX_THEME["dim"]),
}


# =============================================================================
# ASCII ART - BRAIN ANIMATION FRAMES
# =============================================================================

BRAIN_FRAMES = [
    # Frame 1: Neural pulse outward
    """
           ----[CORTEX]----
          /                 \\
    o----*   .---.   .---.   *----o
         |  ( o o ) ( o o )  |
    o----*   '---'   '---'   *----o
          \\   \\       /   /
           \\   \\     /   /
    o-------*---\\   /---*-------o
                 \\_/
           [NEURAL LINK]
    """,
    # Frame 2: Pulse moving through circuits
    """
           ----[CORTEX]----
          /                 \\
    *----o   .---.   .---.   o----*
         |  ( * * ) ( o o )  |
    o----*   '---'   '---'   *----o
          \\   \\       /   /
           \\   \\     /   /
    *-------o---\\   /---o-------*
                 \\_/
           [NEURAL LINK]
    """,
    # Frame 3: Alternating pulse
    """
           ----[CORTEX]----
          /                 \\
    o----*   .---.   .---.   *----o
         |  ( o o ) ( * * )  |
    *----o   '---'   '---'   o----*
          \\   \\       /   /
           \\   \\     /   /
    o-------*---\\   /---*-------o
                 \\_/
           [NEURAL LINK]
    """,
    # Frame 4: Full activation
    """
           ----[CORTEX]----
          /                 \\
    *----*   .---.   .---.   *----*
         |  ( * * ) ( * * )  |
    *----*   '---'   '---'   *----*
          \\   \\       /   /
           \\   \\     /   /
    *-------*---\\   /---*-------*
                 \\_/
           [NEURAL LINK]
    """,
    # Frame 5: Brain with synapses firing
    """
                 ___
        .--.   .'   '.   .--.
    o--( ** )-'  ___  '-( ** )--o
        '--'   /     \\   '--'
    o----.    | BRAIN |    .----o
         '-.  |  o o  |  .-'
    o------'-.|  ___  |.-'------o
              '.     .'
           ----'---'----
    """,
    # Frame 6: Synapses pulsing
    """
                 ___
        .--.   .'   '.   .--.
    *--( oo )-'  ___  '-( oo )--*
        '--'   /     \\   '--'
    *----.    | BRAIN |    .----*
         '-.  |  * *  |  .-'
    *------'-.|  ___  |.-'------*
              '.     .'
           ----'---'----
    """,
]

CORTEX_LOGO = """
   ██████╗ ██████╗ ██████╗ ████████╗███████╗██╗  ██╗
  ██╔════╝██╔═══██╗██╔══██╗╚══██╔══╝██╔════╝╚██╗██╔╝
  ██║     ██║   ██║██████╔╝   ██║   █████╗   ╚███╔╝
  ██║     ██║   ██║██╔══██╗   ██║   ██╔══╝   ██╔██╗
  ╚██████╗╚██████╔╝██║  ██║   ██║   ███████╗██╔╝ ██╗
   ╚═════╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝
             NEURAL STUDY INTERFACE v1.0
"""


# =============================================================================
# BOOT SEQUENCE ANIMATION
# =============================================================================

def cortex_boot_sequence(console: Console, war_mode: bool = False) -> None:
    """
    Display a streamlined Cortex boot sequence.

    Optimized for quick startup while maintaining ASI aesthetic:
    - Brief brain animation (3 frames max)
    - Single status progression
    - Immediate transition to ready state

    Args:
        console: Rich Console instance
        war_mode: If True, shows WAR MODE styling
    """
    console.clear()

    mode_text = "W A R   M O D E" if war_mode else "A D A P T I V E"
    mode_color = CORTEX_THEME["error"] if war_mode else CORTEX_THEME["primary"]

    # Compact boot messages (reduced from 6 to 3)
    boot_messages = [
        "Initializing neural pathways...",
        "Loading knowledge graph...",
        f"Engaging {mode_text}...",
    ]

    with Live(console=console, refresh_per_second=4) as live:
        for i, msg in enumerate(boot_messages):
            frame_idx = i % len(BRAIN_FRAMES)
            brain = Text(BRAIN_FRAMES[frame_idx])
            brain.stylize(Style(color=CORTEX_THEME["primary"]))

            status_text = Text()
            status_text.append("STATUS: ", style=STYLES["cortex_dim"])
            status_text.append(msg, style=STYLES["cortex_accent"])

            content = Text()
            content.append_text(brain)
            content.append("\n")
            content.append_text(status_text)

            panel = Panel(
                Align.center(content),
                title="[bold cyan]◉ CORTEX ENGINE[/bold cyan]",
                border_style=Style(color=mode_color),
                box=box.HEAVY,
                padding=(0, 2),
            )

            live.update(panel)
            time.sleep(0.3)

    # Ready state - brief acknowledgment
    console.print()
    ready_text = Text()
    ready_text.append("◉ ", style=STYLES["cortex_primary"])
    ready_text.append("CORTEX ONLINE", style=Style(color=CORTEX_THEME["success"], bold=True))
    ready_text.append(" ◉", style=STYLES["cortex_primary"])

    console.print(Panel(
        Align.center(ready_text),
        border_style=Style(color=CORTEX_THEME["success"]),
        box=box.ROUNDED,
    ))
    time.sleep(0.2)


# =============================================================================
# THEMED PANELS
# =============================================================================

def cortex_question_panel(
    question: str,
    atom_type: str,
    module: Optional[int] = None,
    retry_count: int = 0,
) -> Panel:
    """
    Create a themed question panel.

    Args:
        question: The question text
        atom_type: Type of atom (mcq, parsons, numeric, flashcard)
        module: Module number (optional)
        retry_count: Number of retries for this question

    Returns:
        Rich Panel with ASI styling
    """
    # Type-specific colors
    type_colors = {
        "mcq": CORTEX_THEME["accent"],
        "parsons": CORTEX_THEME["warning"],
        "numeric": CORTEX_THEME["secondary"],
        "flashcard": CORTEX_THEME["primary"],
        "cloze": CORTEX_THEME["primary"],
    }
    border_color = type_colors.get(atom_type.lower(), CORTEX_THEME["primary"])

    # Build header
    header = Text()
    header.append(f"[{atom_type.upper()}]", style=Style(color=border_color, bold=True))
    if module:
        header.append(f" Module {module}", style=STYLES["cortex_dim"])
    if retry_count > 0:
        header.append(f" [RETRY #{retry_count}]", style=STYLES["cortex_warning"])

    # Question content
    content = Text(question, style=Style(color=CORTEX_THEME["white"]))

    return Panel(
        Align.left(content),
        title=header,
        title_align="left",
        border_style=Style(color=border_color),
        box=box.HEAVY,
        padding=(1, 2),
    )


def cortex_result_panel(
    passed: bool,
    answer: str,
    explanation: Optional[str] = None,
) -> Panel:
    """
    Create a themed result panel.

    Args:
        passed: Whether the answer was correct
        answer: The correct answer
        explanation: Optional explanation text

    Returns:
        Rich Panel with success/error styling
    """
    color = CORTEX_THEME["success"] if passed else CORTEX_THEME["error"]
    status = "CORRECT" if passed else "INCORRECT"
    icon = "◉" if passed else "✗"

    content = Text()
    content.append(f"{icon} {status}\n\n", style=Style(color=color, bold=True))
    content.append("Answer: ", style=STYLES["cortex_dim"])
    content.append(answer, style=Style(color=CORTEX_THEME["white"], bold=True))

    if explanation:
        content.append("\n\n")
        content.append("Explanation: ", style=STYLES["cortex_warning"])
        content.append(explanation, style=STYLES["cortex_dim"])

    return Panel(
        content,
        border_style=Style(color=color),
        box=box.HEAVY,
        padding=(1, 2),
    )


# =============================================================================
# ASI-STYLE PROMPTS
# =============================================================================

ASI_PROMPTS = {
    "mcq": ">_ SELECT OPTION",
    "parsons": ">_ SEQUENCE ORDER",
    "numeric": ">_ INPUT VECTOR",
    "flashcard": ">_ RECALL STATUS",
    "default": ">_ INPUT",
}


def get_asi_prompt(atom_type: str, suffix: str = "") -> str:
    """
    Get ASI-style prompt for a given atom type.

    Args:
        atom_type: Type of atom
        suffix: Optional suffix like "[A-D]" or "(Y/N)"

    Returns:
        Formatted prompt string with ASI styling
    """
    base = ASI_PROMPTS.get(atom_type.lower(), ASI_PROMPTS["default"])
    if suffix:
        return f"[cyan]{base}[/cyan] {suffix}: "
    return f"[cyan]{base}[/cyan]: "


# =============================================================================
# SPINNER FOR LOADING STATES
# =============================================================================

class CortexSpinner:
    """
    Animated brain spinner for loading states.

    Usage:
        with CortexSpinner(console, "Loading atoms..."):
            do_something_slow()
    """

    def __init__(self, console: Console, message: str = "Processing..."):
        self.console = console
        self.message = message
        self.live = None
        self.frame_index = 0

    def __enter__(self):
        self.live = Live(console=self.console, refresh_per_second=4)
        self.live.__enter__()
        self._update()
        return self

    def __exit__(self, *args):
        if self.live:
            self.live.__exit__(*args)

    def _update(self):
        frame = Text(BRAIN_FRAMES[self.frame_index % len(BRAIN_FRAMES)])
        frame.stylize(Style(color=CORTEX_THEME["primary"]))

        status = Text()
        status.append(self.message, style=STYLES["cortex_accent"])

        content = Text()
        content.append_text(frame)
        content.append("\n")
        content.append_text(status)

        panel = Panel(
            Align.center(content),
            title="[bold cyan]◉ CORTEX[/bold cyan]",
            border_style=Style(color=CORTEX_THEME["primary"]),
            box=box.HEAVY,
        )

        if self.live:
            self.live.update(panel)
        self.frame_index += 1

    def update_message(self, message: str):
        """Update the spinner message."""
        self.message = message
        self._update()


# =============================================================================
# NEURO-LINK STATUS BAR
# =============================================================================

def create_neurolink_bar(
    encoding: float,
    integration: float,
    focus: float,
    fatigue: float,
    width: int = 12,
) -> Text:
    """
    Create a live "Neuro-Link Status" bar visualization.

    Displays real-time cognitive metrics using ASCII-safe progress bars
    with color-coded status indicators.

    Args:
        encoding: Encoding strength (0-1) - how well facts stick
        integration: Integration capacity (0-1) - working memory function
        focus: Focus index (0-1) - attention/engagement
        fatigue: Fatigue level (0-1) - cognitive exhaustion

    Returns:
        Rich Text object with formatted neuro-link display
    """
    def make_bar(value: float, label: str, width: int = width) -> tuple[str, str]:
        """Create a single metric bar with appropriate color."""
        filled = int(value * width)
        empty = width - filled

        # Color based on value (except fatigue which is inverted)
        if label == "FATIGUE":
            # Fatigue: low is good (green), high is bad (red)
            if value < 0.3:
                color = CORTEX_THEME["success"]
            elif value < 0.6:
                color = CORTEX_THEME["warning"]
            else:
                color = CORTEX_THEME["error"]
        else:
            # Other metrics: high is good
            if value >= 0.7:
                color = CORTEX_THEME["success"]
            elif value >= 0.4:
                color = CORTEX_THEME["warning"]
            else:
                color = CORTEX_THEME["error"]

        bar = "#" * filled + "-" * empty
        return bar, color

    text = Text()
    text.append("[*] NEURO-LINK STATUS [*]\n\n", style=STYLES["cortex_primary"])

    # Encoding strength
    bar, color = make_bar(encoding, "ENCODING")
    text.append("ENCODING    ", style=STYLES["cortex_dim"])
    text.append(f"[{bar}] ", style=Style(color=color))
    text.append(f"{encoding:.0%}\n", style=Style(color=color, bold=True))

    # Integration capacity
    bar, color = make_bar(integration, "INTEGRATION")
    text.append("INTEGRATION ", style=STYLES["cortex_dim"])
    text.append(f"[{bar}] ", style=Style(color=color))
    text.append(f"{integration:.0%}\n", style=Style(color=color, bold=True))

    # Focus index
    bar, color = make_bar(focus, "FOCUS")
    text.append("FOCUS       ", style=STYLES["cortex_dim"])
    text.append(f"[{bar}] ", style=Style(color=color))
    text.append(f"{focus:.0%}\n", style=Style(color=color, bold=True))

    # Fatigue level (inverted coloring)
    bar, color = make_bar(fatigue, "FATIGUE")
    text.append("FATIGUE     ", style=STYLES["cortex_dim"])
    text.append(f"[{bar}] ", style=Style(color=color))
    text.append(f"{fatigue:.0%}", style=Style(color=color, bold=True))

    return text


def create_neurolink_panel(
    encoding: float = 1.0,
    integration: float = 1.0,
    focus: float = 1.0,
    fatigue: float = 0.0,
    diagnosis: str = "",
    strategy: str = "",
) -> Panel:
    """
    Create a complete Neuro-Link panel for the session dashboard.

    Args:
        encoding: Encoding strength (0-1)
        integration: Integration capacity (0-1)
        focus: Focus index (0-1)
        fatigue: Fatigue level (0-1)
        diagnosis: Current cognitive diagnosis (if any)
        strategy: Recommended remediation strategy (if any)

    Returns:
        Rich Panel with neuro-link visualization
    """
    content = create_neurolink_bar(encoding, integration, focus, fatigue)

    # Add diagnosis if present
    if diagnosis:
        content.append("\n\n")
        content.append("DIAGNOSIS: ", style=STYLES["cortex_dim"])
        content.append(diagnosis.upper(), style=STYLES["cortex_warning"])

    if strategy and strategy != "none":
        content.append("\n")
        content.append("STRATEGY: ", style=STYLES["cortex_dim"])
        content.append(strategy.upper(), style=STYLES["cortex_accent"])

    # Overall status indicator
    overall = (encoding + integration + focus + (1 - fatigue)) / 4
    if overall >= 0.7:
        status = "OPTIMAL"
        border_color = CORTEX_THEME["success"]
    elif overall >= 0.5:
        status = "NOMINAL"
        border_color = CORTEX_THEME["warning"]
    else:
        status = "DEGRADED"
        border_color = CORTEX_THEME["error"]

    return Panel(
        content,
        title=f"[bold cyan]NEURO-LINK[/bold cyan] [{status}]",
        border_style=Style(color=border_color),
        box=box.HEAVY,
        padding=(0, 1),
    )


def create_compact_neurolink(
    encoding: float = 1.0,
    integration: float = 1.0,
    focus: float = 1.0,
    fatigue: float = 0.0,
) -> Text:
    """
    Create a compact single-line neuro-link status for headers.

    Format: [E:##--] [I:###-] [F:####] [T:--##]

    Args:
        encoding, integration, focus, fatigue: Metrics (0-1)

    Returns:
        Rich Text object with compact display
    """
    def mini_bar(value: float, label: str, width: int = 4) -> tuple[str, str]:
        filled = int(value * width)
        empty = width - filled
        bar = "#" * filled + "-" * empty

        if label == "T":  # Fatigue inverted
            color = CORTEX_THEME["success"] if value < 0.3 else CORTEX_THEME["warning"] if value < 0.6 else CORTEX_THEME["error"]
        else:
            color = CORTEX_THEME["success"] if value >= 0.7 else CORTEX_THEME["warning"] if value >= 0.4 else CORTEX_THEME["error"]
        return bar, color

    text = Text()
    text.append("NEURO: ", style=STYLES["cortex_dim"])

    for metric, label in [(encoding, "E"), (integration, "I"), (focus, "F"), (fatigue, "T")]:
        bar, color = mini_bar(metric, label)
        text.append(f"[{label}:", style=STYLES["cortex_dim"])
        text.append(bar, style=Style(color=color))
        text.append("] ", style=STYLES["cortex_dim"])

    return text


# =============================================================================
# CCNA MODULE STRUGGLE VISUALIZATION
# =============================================================================

def create_struggle_heatmap(struggle_schema: dict[int, float]) -> Panel:
    """
    Create a visual heatmap of CCNA module struggles.

    Args:
        struggle_schema: Dict mapping module number to struggle intensity (0-1)

    Returns:
        Rich Panel with color-coded module grid
    """
    text = Text()
    text.append("[*] CCNA STRUGGLE HEATMAP [*]\n\n", style=STYLES["cortex_primary"])

    # Module titles (abbreviated)
    module_names = {
        1: "Networking Today",
        2: "Switch Config",
        3: "Protocols",
        4: "Physical Layer",
        5: "Number Systems",
        6: "Data Link",
        7: "Ethernet",
        8: "Network Layer",
        9: "Address Res",
        10: "Router Config",
        11: "IPv4",
        12: "IPv6",
        13: "ICMP",
        14: "Transport",
        15: "Application",
        16: "Security",
        17: "Small Network",
    }

    for mod in range(1, 18):
        struggle = struggle_schema.get(mod, 0.0)

        # Color based on struggle intensity
        if struggle >= 0.7:
            color = CORTEX_THEME["error"]
            indicator = "[!!!]"
        elif struggle >= 0.4:
            color = CORTEX_THEME["warning"]
            indicator = "[!! ]"
        elif struggle > 0:
            color = CORTEX_THEME["accent"]
            indicator = "[!  ]"
        else:
            color = CORTEX_THEME["success"]
            indicator = "[OK ]"

        # Progress bar
        bar = "#" * int(struggle * 10) + "-" * (10 - int(struggle * 10))

        text.append(f"M{mod:02d} ", style=STYLES["cortex_dim"])
        text.append(f"{indicator} ", style=Style(color=color))
        text.append(f"[{bar}] ", style=Style(color=color))
        text.append(f"{module_names.get(mod, '???')[:12]:12s}\n", style=Style(color=CORTEX_THEME["white"]))

    return Panel(
        text,
        title="[bold cyan]STRUGGLE MAP[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["secondary"]),
        box=box.HEAVY,
        padding=(0, 1),
    )
