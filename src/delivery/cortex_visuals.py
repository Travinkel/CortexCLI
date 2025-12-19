"""
Cortex ASI Visual Components.

"Digital Neocortex" aesthetic with cyan/electric blue color scheme.
Provides ASCII art, spinners, and themed UI components.
"""

from __future__ import annotations

import time

from rich import box
from rich.align import Align
from rich.console import Console
from rich.columns import Columns
from rich.live import Live
from rich.panel import Panel
from rich.style import Style
from rich.text import Text
from rich.syntax import Syntax

# =============================================================================
# ASI COLOR THEME - PINK CYBERBRAIN
# =============================================================================

CORTEX_THEME = {
    "primary": "#FF69B4",  # Hot Pink - main accent
    "secondary": "#DA70D6",  # Orchid - secondary accent
    "accent": "#FF1493",  # Deep Pink - highlights
    "background": "#1a0a1a",  # Deep Purple-Black - background
    "success": "#00FF88",  # Neon Green - correct answers
    "warning": "#FFD700",  # Gold - warnings/retries
    "error": "#FF3366",  # Hot Pink/Red - incorrect
    "dim": "#6a5578",  # Muted purple-gray - secondary text
    "white": "#F0E0F0",  # Pink-white - primary text
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
# 3D ASCII ART ENGINE - ISOMETRIC PANELS WITH DEPTH
# Creates volumetric visual effects using Unicode box-drawing and shading
# =============================================================================

# 3D Border characters for isometric effect
BORDER_3D = {
    # Main panel (front face)
    "tl": "╔",  # top-left
    "tr": "╗",  # top-right
    "bl": "╚",  # bottom-left
    "br": "╝",  # bottom-right
    "h": "═",   # horizontal
    "v": "║",   # vertical
    # Shadow/depth (right face)
    "sh_v": "▓",   # shadow vertical
    "sh_br": "▓",  # shadow bottom-right
    "sh_h": "▓",   # shadow horizontal
    # Light highlight (top face for 3D effect)
    "hl_h": "░",   # highlight horizontal
    "hl_tr": "░",  # highlight top-right
}

# Depth shading characters (darkest to lightest)
DEPTH_CHARS = ["█", "▓", "▒", "░", " "]


def create_3d_panel(
    content: str | Text,
    title: str = "",
    width: int | None = None,
    border_color: str | None = None,
    shadow_depth: int = 2,
    glow: bool = False,
) -> Text:
    """
    Create a 3D isometric panel with depth shadow effect.

    The panel appears to "float" above the terminal with a shadow
    cast to the bottom-right, creating depth perception.

    Args:
        content: Text content to display inside the panel
        title: Optional title for the panel header
        width: Panel width (auto-calculated if None)
        border_color: Color for the border (uses theme primary if None)
        shadow_depth: Shadow offset in characters (1-3)
        glow: If True, adds a subtle glow effect around the panel

    Returns:
        Rich Text object with the 3D panel rendered
    """
    color = border_color or CORTEX_THEME["primary"]
    shadow_color = CORTEX_THEME["dim"]
    content_str = str(content) if not isinstance(content, str) else content
    lines = content_str.split("\n")

    # Calculate width
    if width is None:
        content_width = max(len(line) for line in lines) if lines else 20
        title_width = len(title) + 4 if title else 0
        width = max(content_width + 4, title_width + 4, 30)

    inner_width = width - 2
    shadow_depth = min(max(shadow_depth, 1), 3)

    result = Text()

    # Top border with title
    if title:
        title_str = f" {title} "
        padding = inner_width - len(title_str)
        left_pad = padding // 2
        right_pad = padding - left_pad
        top_line = f"{BORDER_3D['tl']}{BORDER_3D['h'] * left_pad}{title_str}{BORDER_3D['h'] * right_pad}{BORDER_3D['tr']}"
    else:
        top_line = f"{BORDER_3D['tl']}{BORDER_3D['h'] * inner_width}{BORDER_3D['tr']}"

    # Add glow effect (subtle highlight above panel)
    if glow:
        glow_line = " " + "░" * (inner_width + 2)
        result.append(glow_line + "\n", style=Style(color=color))

    # Top border
    result.append(top_line, style=Style(color=color, bold=True))
    # Shadow extends from top-right
    result.append(DEPTH_CHARS[2] * shadow_depth + "\n", style=Style(color=shadow_color))

    # Content lines with side borders and shadow
    for i, line in enumerate(lines):
        padded_line = line[:inner_width].ljust(inner_width)
        result.append(BORDER_3D["v"], style=Style(color=color, bold=True))
        result.append(padded_line, style=Style(color=CORTEX_THEME["white"]))
        result.append(BORDER_3D["v"], style=Style(color=color, bold=True))
        # Right shadow (darker at top, lighter at bottom)
        shadow_char = DEPTH_CHARS[min(1 + i // 3, len(DEPTH_CHARS) - 2)]
        result.append(shadow_char * shadow_depth + "\n", style=Style(color=shadow_color))

    # Bottom border
    bottom_line = f"{BORDER_3D['bl']}{BORDER_3D['h'] * inner_width}{BORDER_3D['br']}"
    result.append(bottom_line, style=Style(color=color, bold=True))
    result.append(DEPTH_CHARS[1] * shadow_depth + "\n", style=Style(color=shadow_color))

    # Bottom shadow (extends below panel)
    shadow_line = " " + DEPTH_CHARS[2] * (inner_width + shadow_depth + 1)
    result.append(shadow_line + "\n", style=Style(color=shadow_color))

    return result


def create_holographic_header(
    text: str,
    width: int = 80,
    style: str = "circuit",
) -> Text:
    """
    Create a holographic-style header with circuit/neural patterns.

    Styles:
    - "circuit": Electronic circuit board aesthetic
    - "neural": Brain neural network pattern
    - "matrix": Falling code aesthetic
    - "cyber": Cyberpunk neon style

    Args:
        text: Header text to display
        width: Width of the header
        style: Visual style ("circuit", "neural", "matrix", "cyber")

    Returns:
        Rich Text with the holographic header
    """
    result = Text()

    # Style-specific decorations
    patterns = {
        "circuit": ("┌─", "─┐", "└─", "─┘", "─", "│", "●", "○"),
        "neural": ("╭─", "─╮", "╰─", "─╯", "─", "│", "◉", "◯"),
        "matrix": ("▛▀", "▀▜", "▙▄", "▄▟", "▀", "▌", "█", "░"),
        "cyber": ("╔═", "═╗", "╚═", "═╝", "═", "║", "◆", "◇"),
    }

    tl, tr, bl, br, h, v, dot_on, dot_off = patterns.get(style, patterns["neural"])

    # Calculate text positioning
    text_with_spaces = f" {text} "
    padding = width - len(text_with_spaces) - 4
    left_pad = padding // 2
    right_pad = padding - left_pad

    # Top decoration line with circuit nodes
    node_line = ""
    for i in range(width):
        if i % 8 == 0:
            node_line += dot_on
        elif i % 4 == 0:
            node_line += dot_off
        else:
            node_line += h if i % 2 == 0 else "─"

    result.append(node_line + "\n", style=Style(color=CORTEX_THEME["secondary"]))

    # Main header line
    result.append(tl, style=Style(color=CORTEX_THEME["primary"]))
    result.append(h * left_pad, style=Style(color=CORTEX_THEME["primary"]))
    result.append(text_with_spaces, style=Style(color=CORTEX_THEME["white"], bold=True))
    result.append(h * right_pad, style=Style(color=CORTEX_THEME["primary"]))
    result.append(tr + "\n", style=Style(color=CORTEX_THEME["primary"]))

    # Bottom decoration
    result.append(node_line + "\n", style=Style(color=CORTEX_THEME["secondary"]))

    return result


def create_depth_meter(
    value: float,
    label: str,
    width: int = 20,
    show_3d: bool = True,
) -> Text:
    """
    Create a 3D progress/meter bar with depth effect.

    Args:
        value: Value between 0.0 and 1.0
        label: Label for the meter
        width: Width of the bar
        show_3d: If True, adds shadow for 3D effect

    Returns:
        Rich Text with the depth meter
    """
    value = max(0.0, min(1.0, value))
    filled = int(value * width)
    empty = width - filled

    # Color based on value
    if value >= 0.7:
        bar_color = CORTEX_THEME["success"]
    elif value >= 0.4:
        bar_color = CORTEX_THEME["warning"]
    else:
        bar_color = CORTEX_THEME["error"]

    result = Text()

    # Label
    result.append(f"{label:12s} ", style=STYLES["cortex_dim"])

    # 3D bar with highlight on top
    if show_3d:
        # Top highlight
        result.append("░" * filled + " " * empty + "\n", style=Style(color=bar_color))
        result.append(" " * 13, style="default")  # Align with label

    # Main bar
    result.append("▓" * filled, style=Style(color=bar_color, bold=True))
    result.append("░" * empty, style=Style(color=CORTEX_THEME["dim"]))
    result.append(f" {value:.0%}", style=Style(color=bar_color, bold=True))

    # Bottom shadow
    if show_3d:
        result.append("\n" + " " * 13, style="default")
        result.append("▒" * filled + " " * empty, style=Style(color=CORTEX_THEME["dim"]))

    return result


def create_isometric_cube(
    label: str,
    value: str,
    size: int = 5,
    color: str | None = None,
) -> Text:
    """
    Create a small isometric 3D cube with label and value.

    Perfect for displaying stats in a visually interesting way.

    Args:
        label: Label text (displayed on top face)
        value: Value text (displayed on front face)
        size: Cube size (3-7)
        color: Color for the cube (uses theme accent if None)

    Returns:
        Rich Text with the isometric cube
    """
    color = color or CORTEX_THEME["accent"]
    size = max(3, min(7, size))

    result = Text()

    # Top face (parallelogram)
    for i in range(size // 2):
        indent = " " * (size - i - 1)
        top_width = size + i * 2
        if i == 0:
            result.append(indent + "╱" + "─" * top_width + "╲\n", style=Style(color=color))
        else:
            result.append(indent + "│" + " " * top_width + "│\n", style=Style(color=color))

    # Front face with value
    for i in range(size):
        front_content = value[:size].center(size) if i == size // 2 else " " * size
        result.append("│" + front_content + "│", style=Style(color=color, bold=True))
        # Right face shadow
        result.append("▓" * (size // 2) + "\n", style=Style(color=CORTEX_THEME["dim"]))

    # Bottom edge
    result.append("└" + "─" * size + "┘", style=Style(color=color))
    result.append("▓" * (size // 2) + "\n", style=Style(color=CORTEX_THEME["dim"]))

    # Bottom shadow
    shadow_line = " " + "▒" * (size + size // 2 + 1)
    result.append(shadow_line + "\n", style=Style(color=CORTEX_THEME["dim"]))

    # Label below
    result.append(label.center(size + size // 2 + 2), style=Style(color=CORTEX_THEME["white"]))

    return result


def render_3d_menu(
    title: str,
    options: list[tuple[str, str]],
    selected: int = 0,
    width: int = 60,
) -> Text:
    """
    Render a 3D-styled menu with depth effects.

    Args:
        title: Menu title
        options: List of (key, description) tuples
        selected: Currently selected option index
        width: Menu width

    Returns:
        Rich Text with the 3D menu
    """
    result = Text()

    # Header with holographic effect
    result.append_text(create_holographic_header(title, width=width, style="neural"))
    result.append("\n")

    # Menu options with 3D effect on hover
    for i, (key, description) in enumerate(options):
        is_selected = (i == selected)

        if is_selected:
            # 3D raised effect for selected item
            result.append("  ╔═", style=Style(color=CORTEX_THEME["accent"]))
            result.append(f" {key} ", style=Style(color=CORTEX_THEME["white"], bold=True))
            result.append("═╗ ", style=Style(color=CORTEX_THEME["accent"]))
            result.append(description, style=Style(color=CORTEX_THEME["white"], bold=True))
            result.append("\n")
            result.append("  ╚═══╝▓", style=Style(color=CORTEX_THEME["dim"]))
            result.append("\n")
        else:
            # Flat appearance for unselected
            result.append(f"    [{key}] ", style=Style(color=CORTEX_THEME["secondary"]))
            result.append(description, style=Style(color=CORTEX_THEME["dim"]))
            result.append("\n")

    return result


def create_neural_border(width: int = 80) -> Text:
    """
    Create a decorative neural network border line.

    Args:
        width: Width of the border

    Returns:
        Rich Text with the neural border
    """
    result = Text()

    # Generate a neural network pattern
    pattern = ""
    for i in range(width):
        if i % 10 == 0:
            pattern += "◉"  # Node
        elif i % 5 == 0:
            pattern += "○"  # Connection point
        elif i % 2 == 0:
            pattern += "─"  # Connection
        else:
            pattern += "·"  # Synapse

    result.append(pattern, style=Style(color=CORTEX_THEME["secondary"]))

    return result


def create_3d_status_card(
    title: str,
    metrics: list[tuple[str, float, str]],
    width: int = 40,
) -> Text:
    """
    Create a 3D status card with multiple metrics.

    Args:
        title: Card title
        metrics: List of (label, value, unit) tuples
        width: Card width

    Returns:
        Rich Text with the status card
    """
    result = Text()

    inner_width = width - 4

    # Top with 3D effect
    result.append("  ╔" + "═" * inner_width + "╗░\n", style=Style(color=CORTEX_THEME["primary"]))

    # Title row
    title_centered = title.center(inner_width)
    result.append("  ║", style=Style(color=CORTEX_THEME["primary"]))
    result.append(title_centered, style=Style(color=CORTEX_THEME["white"], bold=True))
    result.append("║░\n", style=Style(color=CORTEX_THEME["primary"]))

    # Separator
    result.append("  ╠" + "═" * inner_width + "╣░\n", style=Style(color=CORTEX_THEME["primary"]))

    # Metrics
    for label, value, unit in metrics:
        # Determine color based on value
        if value >= 0.7:
            val_color = CORTEX_THEME["success"]
        elif value >= 0.4:
            val_color = CORTEX_THEME["warning"]
        else:
            val_color = CORTEX_THEME["error"]

        # Create mini bar
        bar_width = 10
        filled = int(value * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        result.append("  ║", style=Style(color=CORTEX_THEME["primary"]))
        result.append(f" {label:10s} [", style=Style(color=CORTEX_THEME["dim"]))
        result.append(bar, style=Style(color=val_color))
        result.append(f"] {value:.0%} {unit}".ljust(inner_width - 14 - bar_width), style=Style(color=val_color))
        result.append("║░\n", style=Style(color=CORTEX_THEME["primary"]))

    # Bottom with shadow
    result.append("  ╚" + "═" * inner_width + "╝░\n", style=Style(color=CORTEX_THEME["primary"]))
    result.append("   " + "░" * (inner_width + 1) + "\n", style=Style(color=CORTEX_THEME["dim"]))

    return result


# =============================================================================
# ASCII ART - 3D VOLUMETRIC CYBERBRAIN ANIMATION FRAMES
# Uses gradient shading: ░▒▓█ for depth perception
# =============================================================================

BRAIN_3D_FRAMES = [
    # Frame 1: Base state - 3D brain with depth shading
    r"""
                    ██████████████████████
               █████░░░░░░░░░░░░░░░░░░░░░█████
            ███░░▒▒▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒▒▒░░░░░███
          ██░░▒▒▓▓███████████████████▓▓▒▒░░░░░██
        ██░░▒▓▓██▀▀   ▄▄▄▄▄▄▄▄▄   ▀▀██▓▓▒░░░░░░██
       █░░▒▓██▀  ▄██▓▓▓▓▓▓▓▓▓▓▓██▄  ▀██▓▒░░░░░░░█
      █░░▒▓█▀ ▄██▓▒░░╔══════════╗░░▒▓██▄ ▀█▓▒░░░░█
     █░░▒▓█  ██▓▒░░░░║ NEURAL   ║░░░░▒▓██  █▓▒░░░░█
     █░░▒▓█ ██▓▒░░░░░║ CORTEX   ║░░░░░▒▓██ █▓▒░░░░█
     █░░▒▓█ ██▓▒░░░░░╚══════════╝░░░░░▒▓██ █▓▒░░░░█
      █░░▒▓█▄ ▀██▓▒░░░░░░░░░░░░░░░░▒▓██▀ ▄█▓▒░░░░█
       █░░▒▓██▄  ▀██▓▓▒▒▒▒▒▒▒▒▒▒▓▓██▀  ▄██▓▒░░░░█
        ██░░▒▓▓██▄▄   ▀▀▀▀▀▀▀▀▀   ▄▄██▓▓▒░░░░░██
          ██░░▒▒▓▓███████████████████▓▓▒▒░░░░██
            ███░░▒▒▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒▒▒░░░░░███
               █████░░░░░░░░░░░░░░░░░░░█████
                    ██████████████████████
            ─────────┤ C O R T E X ├─────────
    """,
    # Frame 2: Left hemisphere neural pulse
    r"""
                    ██████████████████████
               █████░░░░░░░░░░░░░░░░░░░░░█████
            ███*░▒▒▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒▒▒░░░░███
          ██*░▒▒▓▓███████████████████▓▓▒▒░░░░██
        ██*░▒▓▓██▀▀   ▄▄▄▄▄▄▄▄▄   ▀▀██▓▓▒░░░░░██
       █*░▒▓██▀  ▄██▓▓▓▓▓▓▓▓▓▓▓██▄  ▀██▓▒░░░░░░█
      █*░▒▓█▀ ▄██▓▒░░╔══════════╗░░▒▓██▄ ▀█▓▒░░░█
     █*░▒▓█  ██▓▒░░░░║*NEURAL   ║░░░░▒▓██  █▓▒░░░█
     █*░▒▓█ ██▓▒░░░░░║ CORTEX   ║░░░░░▒▓██ █▓▒░░░█
     █*░▒▓█ ██▓▒░░░░░╚══════════╝░░░░░▒▓██ █▓▒░░░█
      █*░▒▓█▄ ▀██▓▒░░░░░░░░░░░░░░░░▒▓██▀ ▄█▓▒░░░█
       █*░▒▓██▄  ▀██▓▓▒▒▒▒▒▒▒▒▒▒▓▓██▀  ▄██▓▒░░░█
        ██*░▒▓▓██▄▄   ▀▀▀▀▀▀▀▀▀   ▄▄██▓▓▒░░░░██
          ██░░▒▒▓▓███████████████████▓▓▒▒░░░██
            ███░░▒▒▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒▒▒░░░░███
               █████░░░░░░░░░░░░░░░░░░█████
                    ██████████████████████
            ─────────┤ S Y N A P S E ├────────
    """,
    # Frame 3: Right hemisphere neural pulse
    r"""
                    ██████████████████████
               █████░░░░░░░░░░░░░░░░░░░░░█████
            ███░░▒▒▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒▒▒░*░░███
          ██░░▒▒▓▓███████████████████▓▓▒▒░*░░██
        ██░░▒▓▓██▀▀   ▄▄▄▄▄▄▄▄▄   ▀▀██▓▓▒░*░░░██
       █░░▒▓██▀  ▄██▓▓▓▓▓▓▓▓▓▓▓██▄  ▀██▓▒░*░░░░█
      █░░▒▓█▀ ▄██▓▒░░╔══════════╗░░▒▓██▄ ▀█▓▒*░░█
     █░░▒▓█  ██▓▒░░░░║ NEURAL  *║░░░░▒▓██  █▓▒*░░█
     █░░▒▓█ ██▓▒░░░░░║ CORTEX   ║░░░░░▒▓██ █▓▒*░░█
     █░░▒▓█ ██▓▒░░░░░╚══════════╝░░░░░▒▓██ █▓▒*░░█
      █░░▒▓█▄ ▀██▓▒░░░░░░░░░░░░░░░░▒▓██▀ ▄█▓▒*░░█
       █░░▒▓██▄  ▀██▓▓▒▒▒▒▒▒▒▒▒▒▓▓██▀  ▄██▓▒*░░█
        ██░░▒▓▓██▄▄   ▀▀▀▀▀▀▀▀▀   ▄▄██▓▓▒░*░░██
          ██░░▒▒▓▓███████████████████▓▓▒▒*░░██
            ███░░▒▒▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒▒▒░*░░███
               █████░░░░░░░░░░░░░░░░░░█████
                    ██████████████████████
            ─────────┤ E N C O D E ├─────────
    """,
    # Frame 4: Center cortex activation
    r"""
                    ██████████████████████
               █████░░░░░░░░░░░░░░░░░░░░░█████
            ███░░▒▒▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒▒▒░░░░███
          ██░░▒▒▓▓███████████████████▓▓▒▒░░░░██
        ██░░▒▓▓██▀▀   ▄▄▄▄▄▄▄▄▄   ▀▀██▓▓▒░░░░░██
       █░░▒▓██▀  ▄██▓▓▓▓▓▓▓▓▓▓▓██▄  ▀██▓▒░░░░░░█
      █░░▒▓█▀ ▄██▓▒░░╔══════════╗░░▒▓██▄ ▀█▓▒░░░█
     █░░▒▓█  ██▓▒░░░░║**NEURAL**║░░░░▒▓██  █▓▒░░░█
     █░░▒▓█ ██▓▒░░░░░║**CORTEX**║░░░░░▒▓██ █▓▒░░░█
     █░░▒▓█ ██▓▒░░░░░╚══════════╝░░░░░▒▓██ █▓▒░░░█
      █░░▒▓█▄ ▀██▓▒░░░░░░░░░░░░░░░░▒▓██▀ ▄█▓▒░░░█
       █░░▒▓██▄  ▀██▓▓▒▒▒▒▒▒▒▒▒▒▓▓██▀  ▄██▓▒░░░█
        ██░░▒▓▓██▄▄   ▀▀▀▀▀▀▀▀▀   ▄▄██▓▓▒░░░░██
          ██░░▒▒▓▓███████████████████▓▓▒▒░░░██
            ███░░▒▒▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒▒▒░░░░███
               █████░░░░░░░░░░░░░░░░░░█████
                    ██████████████████████
            ─────────┤ A C T I V E ├─────────
    """,
    # Frame 5: Full neural network activation
    r"""
                    ██████████████████████
               █████*░░░░░░░░░░░░░░░░░░*█████
            ███*░▒▒▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒▒▒░*░███
          ██*░▒▒▓▓███████████████████▓▓▒▒░*░██
        ██*░▒▓▓██▀▀***▄▄▄▄▄▄▄▄▄***▀▀██▓▓▒░*░░██
       █*░▒▓██▀**▄██▓▓▓▓▓▓▓▓▓▓▓██▄**▀██▓▒░*░░░█
      █*░▒▓█▀*▄██▓▒░░╔══════════╗░░▒▓██▄*▀█▓▒*░░█
     █*░▒▓█**██▓▒░░░░║**NEURAL**║░░░░▒▓██**█▓▒*░░█
     █*░▒▓█*██▓▒░░░░░║**CORTEX**║░░░░░▒▓██*█▓▒*░░█
     █*░▒▓█*██▓▒░░░░░╚══════════╝░░░░░▒▓██*█▓▒*░░█
      █*░▒▓█▄*▀██▓▒░░░░░░░░░░░░░░░░▒▓██▀*▄█▓▒*░░█
       █*░▒▓██▄**▀██▓▓▒▒▒▒▒▒▒▒▒▒▓▓██▀**▄██▓▒*░░█
        ██*░▒▓▓██▄▄***▀▀▀▀▀▀▀▀▀***▄▄██▓▓▒░*░░██
          ██*░▒▒▓▓███████████████████▓▓▒▒*░░██
            ███*░▒▒▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒▒▒░*░███
               █████*░░░░░░░░░░░░░░░░*█████
                    ██████████████████████
            ─────────┤ O N L I N E ├─────────
    """,
]

# Legacy BRAIN_FRAMES alias for backwards compatibility
BRAIN_FRAMES = BRAIN_3D_FRAMES

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


def cortex_boot_sequence(
    console: Console, war_mode: bool = False, skip_animation: bool = False
) -> None:
    """
    Display a streamlined Cortex boot sequence.

    Optimized for quick startup while maintaining ASI aesthetic:
    - Animated brain using asciimatics (if available)
    - Brief brain animation fallback (3 frames max)
    - Single status progression
    - Immediate transition to ready state

    Args:
        console: Rich Console instance
        war_mode: If True, shows WAR MODE styling
        skip_animation: If True, skip the ASCII art animation entirely
    """
    console.clear()

    mode_text = "W A R   M O D E" if war_mode else "A D A P T I V E"
    mode_color = CORTEX_THEME["error"] if war_mode else CORTEX_THEME["primary"]

    if not skip_animation:
        # Try animated brain first
        try:
            from src.delivery.animated_brain import run_brain_animation

            boot_messages = [
                "Initializing neural pathways...",
                "Loading knowledge graph...",
                f"Engaging {mode_text}...",
                "CORTEX ONLINE",
            ]
            run_brain_animation(duration=2.5, messages=boot_messages)
            console.clear()  # Clear after animation

        except ImportError:
            # Fallback to static animation if asciimatics not available
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

    console.print(
        Panel(
            Align.center(ready_text),
            border_style=Style(color=CORTEX_THEME["success"]),
            box=box.ROUNDED,
        )
    )
    if not skip_animation:
        time.sleep(0.2)


# =============================================================================
# THEMED PANELS
# =============================================================================


def cortex_question_panel(
    question: str,
    atom_type: str,
    module: int | None = None,
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
    explanation: str | None = None,
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


def render_tf_feedback_panel(
    console: Console,
    correct: bool,
    correct_answer: str,
    user_answer: str,
    explanation: str | None = None,
) -> None:
    """
    Render educational feedback for True/False questions.

    Unlike generic result panels, this provides specific educational context
    for binary questions where retry isn't allowed.

    Args:
        console: Rich Console instance
        correct: Whether user's answer was correct
        correct_answer: The correct answer (True/False)
        user_answer: What the user answered
        explanation: Why the statement is true/false
    """
    color = CORTEX_THEME["success"] if correct else CORTEX_THEME["error"]
    icon = "◉" if correct else "✗"
    status = "CORRECT" if correct else "INCORRECT"

    content = Text()
    content.append(f"{icon} {status}\n\n", style=Style(color=color, bold=True))

    # Show answer comparison for wrong answers
    if not correct:
        content.append("You answered: ", style=STYLES["cortex_dim"])
        content.append(f"{user_answer}\n", style=Style(color=CORTEX_THEME["error"]))
        content.append("Correct answer: ", style=STYLES["cortex_dim"])
        content.append(f"{correct_answer}\n\n", style=Style(color=CORTEX_THEME["success"], bold=True))

    # Educational explanation - the key learning value
    if explanation:
        content.append("─" * 40 + "\n", style=STYLES["cortex_dim"])
        content.append("WHY: ", style=Style(color=CORTEX_THEME["warning"], bold=True))
        content.append(explanation, style=Style(color=CORTEX_THEME["white"]))
    else:
        # Fallback if no explanation available
        content.append("─" * 40 + "\n", style=STYLES["cortex_dim"])
        content.append(
            f"The statement is {correct_answer.upper()} - review this concept.",
            style=STYLES["cortex_dim"],
        )

    console.print(Panel(
        content,
        title="[bold]TRUE/FALSE FEEDBACK[/bold]",
        border_style=Style(color=color),
        box=box.HEAVY,
        padding=(1, 2),
    ))


def render_parsons_diff_panel(
    console: Console,
    user_sequence: list[str],
    correct_sequence: list[str],
    step_explanations: dict[int, str] | None = None,
) -> None:
    """
    Render enhanced side-by-side diff for Parsons problems.

    Shows:
    - Left column: User's sequence with status icons
    - Right column: Correct sequence
    - Color coding: ✓ green (correct position), ~ yellow (wrong position), ✗ red (extra)
    - Optional step explanations for key ordering reasons

    Args:
        console: Rich Console instance
        user_sequence: List of steps in user's order
        correct_sequence: List of steps in correct order
        step_explanations: Optional dict mapping step index to explanation why order matters
    """
    from rich.table import Table

    # Build comparison table
    table = Table(
        box=box.DOUBLE_EDGE,
        border_style=Style(color=CORTEX_THEME["error"]),
        show_header=True,
        header_style=Style(color=CORTEX_THEME["primary"], bold=True),
    )
    table.add_column("#", width=3, justify="center")
    table.add_column("Your Sequence", ratio=2, overflow="fold")
    table.add_column("", width=3, justify="center")  # Status
    table.add_column("Correct Sequence", ratio=2, overflow="fold")

    correct_set = set(correct_sequence)
    max_len = max(len(user_sequence), len(correct_sequence))

    for i in range(max_len):
        step_num = str(i + 1)
        user_step = user_sequence[i] if i < len(user_sequence) else ""
        correct_step = correct_sequence[i] if i < len(correct_sequence) else ""

        # Determine status
        if user_step == correct_step:
            icon = "✓"
            user_style = Style(color=CORTEX_THEME["success"])
            correct_style = Style(color=CORTEX_THEME["success"])
        elif user_step in correct_set:
            icon = "~"
            user_style = Style(color=CORTEX_THEME["warning"])
            correct_style = Style(color=CORTEX_THEME["dim"])
        elif user_step:
            icon = "✗"
            user_style = Style(color=CORTEX_THEME["error"])
            correct_style = Style(color=CORTEX_THEME["dim"])
        else:
            icon = "○"
            user_style = Style(color=CORTEX_THEME["dim"])
            correct_style = Style(color=CORTEX_THEME["warning"])

        table.add_row(
            Text(step_num, style=Style(color=CORTEX_THEME["dim"])),
            Text(user_step, style=user_style),
            Text(icon, style=user_style),
            Text(correct_step, style=correct_style),
        )

    # Legend
    legend = Text()
    legend.append("✓ ", style=Style(color=CORTEX_THEME["success"]))
    legend.append("Correct  ", style=Style(color=CORTEX_THEME["dim"]))
    legend.append("~ ", style=Style(color=CORTEX_THEME["warning"]))
    legend.append("Wrong position  ", style=Style(color=CORTEX_THEME["dim"]))
    legend.append("✗ ", style=Style(color=CORTEX_THEME["error"]))
    legend.append("Missing/Extra", style=Style(color=CORTEX_THEME["dim"]))

    content = Text()
    content.append_text(legend)
    content.append("\n\n")

    # Show step explanations if provided
    if step_explanations:
        content.append("─" * 50 + "\n", style=Style(color=CORTEX_THEME["dim"]))
        content.append("WHY ORDER MATTERS:\n", style=Style(color=CORTEX_THEME["warning"], bold=True))
        for idx, explanation in step_explanations.items():
            if idx < len(correct_sequence):
                content.append(f"  Step {idx + 1}: ", style=Style(color=CORTEX_THEME["primary"]))
                content.append(f"{explanation}\n", style=Style(color=CORTEX_THEME["white"]))

    console.print(Panel(
        Columns([table], padding=(1, 2)),
        title="[bold]SEQUENCE COMPARISON[/bold]",
        border_style=Style(color=CORTEX_THEME["error"]),
        box=box.HEAVY,
    ))

    if step_explanations:
        console.print(Panel(
            content,
            border_style=Style(color=CORTEX_THEME["warning"]),
            box=box.ROUNDED,
        ))


def prompt_flag_option(console: Console) -> str | None:
    """
    Prompt user to flag a problematic question after incorrect answer.

    Shows a subtle prompt that doesn't interrupt flow but allows reporting.

    Returns:
        flag_type if user chose to flag, None otherwise
    """
    from rich.prompt import Prompt

    console.print(
        "\n[dim]Think this question has an issue? "
        "Press [bold]f[/bold] to flag, [bold]Enter[/bold] to continue[/dim]"
    )

    response = Prompt.ask(
        "[dim]>[/dim]",
        default="",
        show_default=False,
    ).strip().lower()

    if response != "f":
        return None

    # Show flag type options
    console.print("\n[bold cyan]FLAG TYPE[/bold cyan]")
    console.print("  [cyan]1[/cyan] - Wrong answer (correct answer is incorrect)")
    console.print("  [cyan]2[/cyan] - Ambiguous (question unclear)")
    console.print("  [cyan]3[/cyan] - Typo (spelling/grammar)")
    console.print("  [cyan]4[/cyan] - Outdated (info no longer accurate)")
    console.print("  [cyan]5[/cyan] - Other")
    console.print("  [dim]c[/dim] - Cancel")

    flag_choice = Prompt.ask(
        ">_ [cyan]SELECT[/cyan]",
        choices=["1", "2", "3", "4", "5", "c"],
        default="c",
    )

    flag_types = {
        "1": "wrong_answer",
        "2": "ambiguous",
        "3": "typo",
        "4": "outdated",
        "5": "other",
    }

    flag_type = flag_types.get(flag_choice)

    if flag_type:
        # Optional reason
        reason = Prompt.ask(
            "[dim]Reason (optional, press Enter to skip)[/dim]",
            default="",
        ).strip()

        console.print(
            f"[green]Flag recorded:[/green] {flag_type}"
            + (f" - {reason}" if reason else "")
        )
        return {"type": flag_type, "reason": reason} if reason else {"type": flag_type}

    return None


def render_contrastive_panel(
    console: Console,
    concept_a: dict,
    concept_b: dict,
    confusion_evidence: str | None = None,
) -> None:
    """
    Render side-by-side concept comparison for discrimination errors.

    When learners confuse similar concepts, this panel shows them
    side-by-side with key differentiating facts highlighted.

    Args:
        console: Rich Console instance
        concept_a: Dict with 'name', 'definition', 'key_facts' (list), 'example'
        concept_b: Dict with same structure
        confusion_evidence: Optional string explaining why learner confused them
    """
    from rich.table import Table

    # Build comparison table
    table = Table(
        box=box.DOUBLE_EDGE,
        border_style=Style(color=CORTEX_THEME["primary"]),
        show_header=True,
        header_style=Style(color=CORTEX_THEME["primary"], bold=True),
        title="[bold]CONCEPT COMPARISON[/bold]",
        title_style=Style(color=CORTEX_THEME["warning"], bold=True),
    )

    name_a = concept_a.get("name", "Concept A")
    name_b = concept_b.get("name", "Concept B")

    table.add_column(name_a, ratio=1, style=Style(color=CORTEX_THEME["accent"]))
    table.add_column(name_b, ratio=1, style=Style(color=CORTEX_THEME["secondary"]))

    # Definition row
    def_a = concept_a.get("definition", "")
    def_b = concept_b.get("definition", "")
    table.add_row(
        Text(def_a, style=Style(color=CORTEX_THEME["white"])),
        Text(def_b, style=Style(color=CORTEX_THEME["white"])),
    )

    # Key facts rows
    facts_a = concept_a.get("key_facts", [])
    facts_b = concept_b.get("key_facts", [])
    max_facts = max(len(facts_a), len(facts_b))

    for i in range(max_facts):
        fact_a = facts_a[i] if i < len(facts_a) else ""
        fact_b = facts_b[i] if i < len(facts_b) else ""
        table.add_row(
            Text(f"• {fact_a}", style=Style(color=CORTEX_THEME["dim"])) if fact_a else Text(""),
            Text(f"• {fact_b}", style=Style(color=CORTEX_THEME["dim"])) if fact_b else Text(""),
        )

    # Example row (highlighted)
    example_a = concept_a.get("example", "")
    example_b = concept_b.get("example", "")
    if example_a or example_b:
        table.add_row(
            Text(f"Ex: {example_a}", style=Style(color=CORTEX_THEME["success"], italic=True)) if example_a else Text(""),
            Text(f"Ex: {example_b}", style=Style(color=CORTEX_THEME["success"], italic=True)) if example_b else Text(""),
        )

    console.print(Panel(
        table,
        border_style=Style(color=CORTEX_THEME["warning"]),
        box=box.HEAVY,
        padding=(1, 2),
    ))

    # Show confusion evidence if available
    if confusion_evidence:
        console.print(Panel(
            Text.assemble(
                ("WHY YOU MIGHT CONFUSE THEM: ", Style(color=CORTEX_THEME["warning"], bold=True)),
                (confusion_evidence, Style(color=CORTEX_THEME["dim"])),
            ),
            border_style=Style(color=CORTEX_THEME["dim"]),
            box=box.ROUNDED,
        ))


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
    Simple spinner for loading states using Rich's console.status().

    Usage:
        with CortexSpinner(console, "Loading atoms..."):
            do_something_slow()
    """

    def __init__(self, console: Console, message: str = "Processing..."):
        self.console = console
        self.message = message
        self._status = None

    def __enter__(self):
        # Use console.status() - handles concurrent output gracefully
        self._status = self.console.status(f"[cyan]{self.message}[/cyan]", spinner="dots")
        self._status.__enter__()
        return self

    def __exit__(self, *args):
        if self._status:
            self._status.__exit__(*args)

    def update_message(self, message: str):
        """Update the spinner message."""
        self.message = message
        if self._status:
            self._status.update(f"[cyan]{self.message}[/cyan]")


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
            color = (
                CORTEX_THEME["success"]
                if value < 0.3
                else CORTEX_THEME["warning"]
                if value < 0.6
                else CORTEX_THEME["error"]
            )
        else:
            color = (
                CORTEX_THEME["success"]
                if value >= 0.7
                else CORTEX_THEME["warning"]
                if value >= 0.4
                else CORTEX_THEME["error"]
            )
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
        text.append(
            f"{module_names.get(mod, '???')[:12]:12s}\n", style=Style(color=CORTEX_THEME["white"])
        )

    return Panel(
        text,
        title="[bold cyan]STRUGGLE MAP[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["secondary"]),
        box=box.HEAVY,
        padding=(0, 1),
    )


# =============================================================================
# Diagram-as-Code (Mermaid) renderer
# =============================================================================


def render_mermaid(console: Console, code: str) -> None:
    """Render Mermaid code as highlighted block in the CLI."""
    try:
        syntax = Syntax(code.strip(), "mermaid", theme="monokai", line_numbers=False)
        console.print("\n[bold cyan]  VISUALIZATION REQUIRED [/bold cyan]")
        console.print("[dim]Diagram-as-code (Mermaid). Follow the prompt shown with the diagram.[/dim]\n")
        console.print(syntax)
    except Exception:
        console.print("[yellow]Mermaid diagram:[/yellow]")
        console.print(code)


def render_contrastive_view(target_text: str, lure_text: str) -> Panel:
    """Render two columns for contrastive discrimination training."""
    panels = [
        Panel(target_text, title="TARGET", border_style="cyan", box=box.HEAVY),
        Panel(lure_text, title="LURE", border_style="magenta", box=box.HEAVY),
    ]
    return Panel(
        Columns(panels, equal=True, expand=True),
        title="[bold yellow]⚠️ INTERFERENCE DETECTED[/bold yellow]",
        border_style="yellow",
        box=box.HEAVY,
    )


def render_focus_reset(reason: str = "Your attention is drifting") -> Panel:
    """Render breathing/centering prompt for focus resets."""
    text = Text()
    text.append("\n FOCUS RESET TRIGGERED \n\n", style=Style(color=CORTEX_THEME["error"], bold=True))
    text.append(f"{reason}. Pausing for 5 seconds.\n", style=STYLES["cortex_warning"])
    text.append("\n[  Breath In  ]  ...  [  Breath Out  ]\n", style=STYLES["cortex_accent"])
    text.append("(System will resume automatically)\n", style=STYLES["cortex_dim"])
    return Panel(Align.center(text), border_style=CORTEX_THEME["warning"], box=box.HEAVY, padding=(1, 2))


# =============================================================================
# Content Reading Components
# =============================================================================


def render_module_header(module_num: int, title: str, description: str = "") -> Panel:
    """
    Render a module header for reading mode.

    Args:
        module_num: Module number (1-17)
        title: Module title
        description: Optional module description

    Returns:
        Rich Panel with styled header
    """
    text = Text()
    text.append(f"[*] MODULE {module_num}: ", style=STYLES["cortex_primary"])
    text.append(f"{title.upper()}\n", style=Style(color=CORTEX_THEME["white"], bold=True))

    if description:
        text.append(f"\n{description}", style=STYLES["cortex_dim"])

    return Panel(
        text,
        border_style=Style(color=CORTEX_THEME["primary"]),
        box=box.DOUBLE,
        padding=(0, 1),
    )


def render_section_header(section_id: str, title: str, level: int = 2) -> Text:
    """
    Render a section header with appropriate styling.

    Args:
        section_id: Section identifier (e.g., "11.2.3")
        title: Section title
        level: Header level (2=main, 3=sub, 4=sub-sub)

    Returns:
        Rich Text object with styled header
    """
    text = Text()

    # Indentation based on level
    indent = "  " * (level - 2)

    if level == 2:
        text.append(f"\n{indent}", style=STYLES["cortex_dim"])
        text.append(f"{section_id} ", style=STYLES["cortex_accent"])
        text.append(f"{title}\n", style=Style(color=CORTEX_THEME["white"], bold=True))
        text.append(f"{indent}" + "─" * 60 + "\n", style=STYLES["cortex_dim"])
    elif level == 3:
        text.append(f"\n{indent}", style=STYLES["cortex_dim"])
        text.append(f"{section_id} ", style=STYLES["cortex_secondary"])
        text.append(f"{title}\n", style=Style(color=CORTEX_THEME["white"]))
    else:
        text.append(f"\n{indent}", style=STYLES["cortex_dim"])
        text.append(f"{section_id} ", style=STYLES["cortex_dim"])
        text.append(f"{title}\n", style=Style(color=CORTEX_THEME["dim"]))

    return text


def render_section_content(
    content: str,
    key_terms: list | None = None,
    commands: list | None = None,
    level: int = 2,
) -> Text:
    """
    Render section content with formatting.

    Args:
        content: Main text content
        key_terms: List of KeyTerm objects to highlight
        commands: List of CLICommand objects to display
        level: Section level for indentation

    Returns:
        Rich Text object with formatted content
    """
    text = Text()
    indent = "  " * (level - 2)

    # Render main content
    if content.strip():
        for line in content.split("\n"):
            if line.strip():
                text.append(f"{indent}{line}\n", style=Style(color=CORTEX_THEME["white"]))
            else:
                text.append("\n")

    # Render key terms if present
    if key_terms:
        text.append(f"\n{indent}", style=STYLES["cortex_dim"])
        text.append("Key Terms:\n", style=STYLES["cortex_accent"])
        for term in key_terms:
            text.append(f"{indent}  • ", style=STYLES["cortex_dim"])
            text.append(f"{term.term}", style=Style(color=CORTEX_THEME["accent"], bold=True))
            if hasattr(term, "definition") and term.definition:
                text.append(f": {term.definition}\n", style=Style(color=CORTEX_THEME["white"]))
            else:
                text.append("\n")

    # Render commands if present
    if commands:
        text.append(f"\n{indent}", style=STYLES["cortex_dim"])
        text.append("CLI Commands:\n", style=STYLES["cortex_warning"])
        for cmd in commands:
            mode_str = f"({cmd.mode}) " if hasattr(cmd, "mode") and cmd.mode != "unknown" else ""
            text.append(f"{indent}  ", style=STYLES["cortex_dim"])
            text.append(f"{mode_str}", style=STYLES["cortex_dim"])
            text.append(f"{cmd.command}\n", style=Style(color=CORTEX_THEME["success"]))

    return text


def render_toc(
    module_num: int,
    title: str,
    entries: list,
    struggle_modules: set[int] | None = None,
) -> Panel:
    """
    Render table of contents for a module.

    Args:
        module_num: Module number
        title: Module title
        entries: List of TOCEntry objects
        struggle_modules: Set of module numbers marked as struggle areas

    Returns:
        Rich Panel with formatted TOC
    """
    text = Text()
    text.append(f"[*] MODULE {module_num}: {title.upper()}\n", style=STYLES["cortex_primary"])
    text.append("Table of Contents\n\n", style=STYLES["cortex_dim"])

    is_struggle = struggle_modules and module_num in struggle_modules

    for entry in entries:
        # Indentation based on level
        indent = "  " * (entry.level - 2)

        # Section number and title
        text.append(f"{indent}", style=STYLES["cortex_dim"])
        text.append(f"{entry.section_id:8s} ", style=STYLES["cortex_accent"] if entry.level == 2 else STYLES["cortex_dim"])
        text.append(f"{entry.title[:45]:45s}", style=Style(color=CORTEX_THEME["white"]))

        # Struggle indicator
        if is_struggle and entry.level == 2:
            text.append(" [FOCUS]", style=STYLES["cortex_warning"])

        text.append("\n")

    text.append(f"\nUse: nls cortex read {module_num} --section <id>", style=STYLES["cortex_dim"])

    return Panel(
        text,
        title=f"[bold cyan]MODULE {module_num} - TABLE OF CONTENTS[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["secondary"]),
        box=box.HEAVY,
        padding=(1, 2),
    )


def render_search_results(query: str, results: list, module_num: int) -> Panel:
    """
    Render search results with context.

    Args:
        query: Search query string
        results: List of SearchResult objects
        module_num: Module number searched

    Returns:
        Rich Panel with formatted search results
    """
    text = Text()
    text.append(f"Search: ", style=STYLES["cortex_dim"])
    text.append(f'"{query}"', style=STYLES["cortex_accent"])
    text.append(f" in Module {module_num}\n", style=STYLES["cortex_dim"])
    text.append(f"Found {len(results)} result(s)\n\n", style=STYLES["cortex_dim"])

    for i, result in enumerate(results[:10], 1):
        text.append(f"[{i}] ", style=STYLES["cortex_accent"])
        text.append(f"{result.section_id} ", style=STYLES["cortex_secondary"])
        text.append(f"{result.section_title}\n", style=Style(color=CORTEX_THEME["white"]))

        # Show context with match highlighted
        context = result.context.replace(result.match_text, f"[{result.match_text}]")
        text.append(f"    {context[:100]}...\n\n", style=STYLES["cortex_dim"])

    if len(results) > 10:
        text.append(f"... and {len(results) - 10} more results\n", style=STYLES["cortex_dim"])

    return Panel(
        text,
        title=f"[bold cyan]SEARCH RESULTS[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["secondary"]),
        box=box.HEAVY,
        padding=(1, 2),
    )


def render_reading_nav(
    current_section: str,
    has_prev: bool,
    has_next: bool,
    page_num: int = 1,
    total_pages: int = 1,
) -> Text:
    """
    Render navigation prompt for reading mode.

    Args:
        current_section: Current section ID
        has_prev: Whether previous section exists
        has_next: Whether next section exists
        page_num: Current page number (for long sections)
        total_pages: Total pages

    Returns:
        Rich Text with navigation options
    """
    text = Text()
    text.append("\n─" * 60 + "\n", style=STYLES["cortex_dim"])

    # Section info
    text.append(f"Section: {current_section}", style=STYLES["cortex_accent"])
    if total_pages > 1:
        text.append(f" (Page {page_num}/{total_pages})", style=STYLES["cortex_dim"])
    text.append("\n")

    # Navigation options
    options = []
    if has_prev:
        options.append("[p]rev")
    if has_next:
        options.append("[n]ext")
    options.append("[t]oc")
    options.append("[q]uit")

    text.append(" | ".join(options), style=STYLES["cortex_dim"])

    return text


# =============================================================================
# SESSION UI FUNCTIONS (Called by CortexSession)
# =============================================================================


def render_timer_panel(
    elapsed_seconds: float,
    war_mode: bool,
    correct: int,
    incorrect: int,
    current_index: int,
    queue_length: int,
    streak: int = 0,
) -> Panel:
    """
    Render compact header with mode, time, accuracy, and progress.

    Args:
        elapsed_seconds: Session duration in seconds
        war_mode: Whether war mode is active
        correct: Number of correct answers
        incorrect: Number of incorrect answers
        current_index: Current question index (1-based)
        queue_length: Total questions in queue
        streak: Current correct streak

    Returns:
        Rich Panel with session header
    """
    minutes = int(elapsed_seconds // 60)
    seconds = int(elapsed_seconds % 60)
    mode = "WAR" if war_mode else "ADAPTIVE"
    mode_color = CORTEX_THEME["error"] if war_mode else CORTEX_THEME["primary"]
    total = correct + incorrect
    accuracy = (correct / max(1, total)) * 100

    txt = Text()
    txt.append(f"CORTEX {mode}", style=Style(color=mode_color, bold=True))
    txt.append(f"  ⏱ {minutes:02d}:{seconds:02d}", style=Style(color=CORTEX_THEME["accent"]))
    txt.append(f"  ✓ {accuracy:.0f}%", style=Style(color=CORTEX_THEME["success"]))
    txt.append(f"  Q: {current_index}/{queue_length}", style=STYLES["cortex_dim"])
    if streak > 0:
        txt.append(f"  🔥{streak}", style=STYLES["cortex_warning"])

    return Panel(
        txt,
        padding=(0, 1),
        border_style=Style(color=mode_color),
        box=box.ROUNDED,
    )


def render_stats_panel(correct: int, incorrect: int) -> Panel:
    """
    Render session stats panel with clear metrics.

    Args:
        correct: Number of correct answers
        incorrect: Number of incorrect answers

    Returns:
        Rich Panel with score summary
    """
    total = correct + incorrect
    accuracy = (correct / max(1, total)) * 100
    streak = max(0, correct - incorrect)

    stats_text = Text()
    stats_text.append(f"✓ {correct}", style=STYLES["cortex_success"])
    stats_text.append(f"  ✗ {incorrect}", style=STYLES["cortex_error"])
    stats_text.append(f"\n{accuracy:.0f}% accuracy", style=STYLES["cortex_dim"])
    if streak > 0:
        stats_text.append(f"\n🔥 {streak} streak", style=Style(color=CORTEX_THEME["warning"]))

    return Panel(
        stats_text,
        title="[bold]Score[/bold]",
        border_style=Style(color=CORTEX_THEME["accent"]),
        box=box.ROUNDED,
        padding=(0, 1),
    )


def render_brain_state_panel(
    memory: float = 1.0,
    reasoning: float = 1.0,
    focus: float = 1.0,
    energy: float = 1.0,
) -> Panel:
    """
    Render Brain State panel with cognitive metrics.

    Metrics explained:
    - Memory: How well info is being retained (recent accuracy)
    - Reasoning: Performance on complex questions (Parsons, matching)
    - Focus: Consistency of responses (low error streaks = focused)
    - Energy: Mental fatigue level (inverse of fatigue)

    Args:
        memory: Memory metric (0-1)
        reasoning: Reasoning metric (0-1)
        focus: Focus metric (0-1)
        energy: Energy metric (0-1, inverse of fatigue)

    Returns:
        Rich Panel with brain state visualization
    """
    brain_text = Text()

    def add_metric(label: str, value: float, emoji_good: str, emoji_bad: str):
        emoji = emoji_good if value >= 0.6 else emoji_bad
        bar_width = 8
        filled = int(value * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        if value >= 0.7:
            color = CORTEX_THEME["success"]
        elif value >= 0.4:
            color = CORTEX_THEME["warning"]
        else:
            color = CORTEX_THEME["error"]

        brain_text.append(f"{emoji} {label}: ", style=STYLES["cortex_dim"])
        brain_text.append(f"{bar}\n", style=Style(color=color))

    add_metric("Memory", memory, "🧠", "💭")
    add_metric("Reasoning", reasoning, "⚡", "🔄")
    add_metric("Focus", focus, "🎯", "😵")
    add_metric("Energy", energy, "💪", "😴")

    # Add advice if struggling
    if energy < 0.4:
        brain_text.append(
            "\n💡 Take a break soon",
            style=Style(color=CORTEX_THEME["warning"], italic=True),
        )
    elif focus < 0.4:
        brain_text.append(
            "\n💡 Slow down, read carefully",
            style=Style(color=CORTEX_THEME["warning"], italic=True),
        )
    elif memory < 0.5:
        brain_text.append(
            "\n💡 Review basics first",
            style=Style(color=CORTEX_THEME["accent"], italic=True),
        )

    # Status color based on overall
    overall = (memory + reasoning + focus + energy) / 4
    if overall >= 0.7:
        border_color = CORTEX_THEME["success"]
    elif overall >= 0.5:
        border_color = CORTEX_THEME["warning"]
    else:
        border_color = CORTEX_THEME["error"]

    return Panel(
        brain_text,
        title="[bold]Brain State[/bold]",
        border_style=Style(color=border_color),
        box=box.ROUNDED,
        padding=(0, 1),
    )


def render_question_panel(
    front: str,
    atom_type: str,
    card_id: str = "",
) -> Panel:
    """
    Render the question panel for an atom.

    Args:
        front: Question text
        atom_type: Type of atom (mcq, parsons, etc.)
        card_id: Card identifier

    Returns:
        Rich Panel with question
    """
    return Panel(
        Text(front.strip() or "No prompt", style="bold"),
        title=f"{atom_type.upper()} · {card_id}",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(0, 1),
    )


def render_hint_panel(hint: str) -> Panel:
    """
    Render a hint panel for incorrect first attempt.

    Args:
        hint: Hint text

    Returns:
        Rich Panel with hint styling
    """
    hint_text = Text()
    hint_text.append("✗ Incorrect. ", style=Style(color=CORTEX_THEME["error"]))
    hint_text.append("Here's a hint:\n\n", style=STYLES["cortex_dim"])
    hint_text.append(f"  {hint}\n\n", style=Style(color=CORTEX_THEME["accent"], italic=True))
    hint_text.append("Try again...", style=STYLES["cortex_dim"])

    return Panel(
        hint_text,
        border_style=Style(color=CORTEX_THEME["warning"]),
        box=box.ROUNDED,
        padding=(0, 1),
    )


def render_requeue_panel() -> Panel:
    """Render the delayed re-queue message for T/F questions."""
    return Panel(
        "[yellow]✗ Incorrect. Re-queuing for spaced recall...[/yellow]",
        border_style=Style(color=CORTEX_THEME["warning"]),
        box=box.ROUNDED,
        padding=(0, 1),
    )


def render_offline_indicator() -> Text:
    """Render subtle offline mode indicator."""
    text = Text()
    text.append("Offline Mode: Changes cached", style=STYLES["cortex_dim"])
    return text


# =============================================================================
# SESSION UI FUNCTIONS (Called by CortexSession)
# =============================================================================


def render_session_dashboard(
    console: Console,
    mode: str,
    start_time: float,
    stats: dict,
    total: int,
    current: int,
    context=None,
    offline: bool = False,
) -> None:
    """
    Render the full session dashboard.

    Args:
        console: Rich Console instance
        mode: "WAR" or "ADAPTIVE"
        start_time: Session start time (monotonic)
        stats: Dict with correct, incorrect, streak
        total: Total questions
        current: Current question index
        context: Optional SessionContext for neuro-link
        offline: Whether in offline mode
    """
    console.clear()

    if offline:
        console.print(render_offline_indicator())

    # Header (start_time uses time.monotonic())
    elapsed = time.monotonic() - start_time if start_time else 0
    console.print(render_timer_panel(
        elapsed_seconds=elapsed,
        war_mode=(mode == "WAR"),
        correct=stats.get("correct", 0),
        incorrect=stats.get("incorrect", 0),
        current_index=current,
        queue_length=total,
        streak=stats.get("streak", 0),
    ))


def render_question_panel(console: Console, note: dict) -> None:
    """
    Render the question panel for an atom.

    Args:
        console: Rich Console instance
        note: Atom dict with front, atom_type, card_id
    """
    front = note.get("front", "").strip() or "No prompt"
    atom_type = note.get("atom_type", "note")
    card_id = note.get("card_id", "")

    panel = Panel(
        Text(front, style="bold"),
        title=f"{atom_type.upper()} · {card_id}",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(0, 1),
    )
    console.print(panel)


def render_hint_panel(console: Console, hint: str) -> None:
    """
    Render a hint panel for incorrect first attempt.

    Args:
        console: Rich Console instance
        hint: Hint text
    """
    hint_text = Text()
    hint_text.append("✗ Incorrect. ", style=Style(color=CORTEX_THEME["error"]))
    hint_text.append("Here's a hint:\n\n", style=STYLES["cortex_dim"])
    hint_text.append(f"  {hint}\n\n", style=Style(color=CORTEX_THEME["accent"], italic=True))
    hint_text.append("Try again...", style=STYLES["cortex_dim"])

    console.print(Panel(
        hint_text,
        border_style=Style(color=CORTEX_THEME["warning"]),
        box=box.ROUNDED,
        padding=(0, 1),
    ))


def render_result_panel(
    console: Console,
    correct: bool,
    answer: str,
    explanation: str | None = None,
) -> None:
    """
    Render the result panel after answering.

    Args:
        console: Rich Console instance
        correct: Whether answer was correct
        answer: The correct answer
        explanation: Optional explanation
    """
    console.print(cortex_result_panel(correct, answer, explanation))


def render_diagnosis_panel(console: Console, diagnosis) -> None:
    """
    Render cognitive diagnosis from NCDE.

    Args:
        console: Rich Console instance
        diagnosis: CognitiveDiagnosis object
    """
    if not diagnosis:
        return

    text = Text()
    text.append("DIAGNOSIS: ", style=STYLES["cortex_dim"])
    text.append(str(diagnosis.fail_mode.name if diagnosis.fail_mode else "NONE"), style=STYLES["cortex_warning"])

    if diagnosis.explanation:
        text.append(f"\n{diagnosis.explanation}", style=STYLES["cortex_dim"])

    console.print(Panel(
        text,
        border_style=Style(color=CORTEX_THEME["warning"]),
        box=box.ROUNDED,
        padding=(0, 1),
    ))


def trigger_micro_break(console: Console, message: str = "") -> None:
    """
    Trigger a micro-break with breathing prompt.

    Args:
        console: Rich Console instance
        message: Optional message
    """
    console.print(render_focus_reset(message))
    time.sleep(5)


def render_session_summary(
    console: Console,
    correct: int,
    incorrect: int,
    context=None,
    incorrect_atoms: list | None = None,
) -> None:
    """
    Render end-of-session summary.

    Args:
        console: Rich Console instance
        correct: Correct count
        incorrect: Incorrect count
        context: Optional SessionContext
        incorrect_atoms: List of incorrect atoms for remediation
    """
    total = correct + incorrect
    accuracy = (correct / max(1, total)) * 100

    text = Text()
    text.append("\n[*] SESSION COMPLETE [*]\n\n", style=STYLES["cortex_primary"])
    text.append(f"Correct: {correct}\n", style=STYLES["cortex_success"])
    text.append(f"Incorrect: {incorrect}\n", style=STYLES["cortex_error"])
    text.append(f"Accuracy: {accuracy:.0f}%\n", style=STYLES["cortex_accent"])

    if incorrect_atoms:
        text.append(f"\nStruggled sections: {len(incorrect_atoms)}", style=STYLES["cortex_warning"])

    border_color = CORTEX_THEME["success"] if accuracy >= 70 else CORTEX_THEME["warning"]

    console.print(Panel(
        text,
        title="[bold]Session Summary[/bold]",
        border_style=Style(color=border_color),
        box=box.HEAVY,
        padding=(1, 2),
    ))


# =============================================================================
# SIGNALS DASHBOARD - Transfer Testing & Memorization Detection
# =============================================================================


def render_signals_dashboard(
    transfer_data: list[dict],
    memorization_suspects: list[dict],
    note_effectiveness: list[dict],
    recommendations: list[dict],
) -> Panel:
    """
    Render the learning signals dashboard.

    Shows:
    - Per-section accuracy by format (T/F vs MCQ vs Parsons)
    - Flagged "memorization suspects" (high recognition, low transfer)
    - Note effectiveness (pre/post error rates)
    - Recommended actions per module

    Args:
        transfer_data: Per-section accuracy data with format breakdown
        memorization_suspects: Atoms flagged for memorization vs understanding
        note_effectiveness: Note improvement statistics
        recommendations: Per-module recommended actions

    Returns:
        Rich Panel with signals dashboard
    """
    text = Text()

    # Header
    text.append("[*] LEARNING SIGNALS DASHBOARD [*]\n\n", style=STYLES["cortex_primary"])

    # Section 1: Transfer Testing Summary
    text.append("TRANSFER TESTING (Memory vs Understanding)\n", style=STYLES["cortex_accent"])
    text.append("-" * 45 + "\n", style=STYLES["cortex_dim"])

    if transfer_data:
        text.append("Section         T/F     MCQ   Parsons  Transfer\n", style=STYLES["cortex_dim"])
        for section in transfer_data[:8]:  # Show top 8
            section_id = section.get("section_id", "?")[:12]
            tf_acc = section.get("tf_accuracy")
            mcq_acc = section.get("mcq_accuracy")
            parsons_acc = section.get("parsons_accuracy")
            transfer = section.get("transfer_score")

            text.append(f"{section_id:12s}  ", style=Style(color=CORTEX_THEME["white"]))

            # T/F accuracy
            if tf_acc is not None:
                tf_color = CORTEX_THEME["success"] if tf_acc >= 0.7 else (
                    CORTEX_THEME["warning"] if tf_acc >= 0.4 else CORTEX_THEME["error"]
                )
                text.append(f"{tf_acc:>5.0%}  ", style=Style(color=tf_color))
            else:
                text.append("  --   ", style=STYLES["cortex_dim"])

            # MCQ accuracy
            if mcq_acc is not None:
                mcq_color = CORTEX_THEME["success"] if mcq_acc >= 0.7 else (
                    CORTEX_THEME["warning"] if mcq_acc >= 0.4 else CORTEX_THEME["error"]
                )
                text.append(f"{mcq_acc:>5.0%}  ", style=Style(color=mcq_color))
            else:
                text.append("  --   ", style=STYLES["cortex_dim"])

            # Parsons accuracy
            if parsons_acc is not None:
                parsons_color = CORTEX_THEME["success"] if parsons_acc >= 0.7 else (
                    CORTEX_THEME["warning"] if parsons_acc >= 0.4 else CORTEX_THEME["error"]
                )
                text.append(f"{parsons_acc:>6.0%}  ", style=Style(color=parsons_color))
            else:
                text.append("   --   ", style=STYLES["cortex_dim"])

            # Transfer score
            if transfer is not None:
                transfer_color = CORTEX_THEME["success"] if transfer >= 0.7 else (
                    CORTEX_THEME["warning"] if transfer >= 0.4 else CORTEX_THEME["error"]
                )
                text.append(f"{transfer:>6.0%}", style=Style(color=transfer_color))
            else:
                text.append("   --", style=STYLES["cortex_dim"])

            text.append("\n")
    else:
        text.append("No transfer data yet. Complete more varied question types.\n", style=STYLES["cortex_dim"])

    text.append("\n")

    # Section 2: Memorization Suspects
    text.append("MEMORIZATION SUSPECTS (Recognition > Transfer Gap)\n", style=STYLES["cortex_warning"])
    text.append("-" * 45 + "\n", style=STYLES["cortex_dim"])

    if memorization_suspects:
        for suspect in memorization_suspects[:5]:
            section_id = suspect.get("section_id", "?")[:15]
            tf_acc = suspect.get("tf_accuracy", 0)
            procedural_acc = suspect.get("procedural_accuracy", 0)
            gap = tf_acc - procedural_acc

            text.append("[!] ", style=Style(color=CORTEX_THEME["error"]))
            text.append(f"{section_id:15s} ", style=Style(color=CORTEX_THEME["white"]))
            text.append(f"T/F: {tf_acc:.0%}", style=Style(color=CORTEX_THEME["success"]))
            text.append(" vs ", style=STYLES["cortex_dim"])
            text.append(f"Procedural: {procedural_acc:.0%}", style=Style(color=CORTEX_THEME["error"]))
            text.append(f" (gap: {gap:+.0%})\n", style=Style(color=CORTEX_THEME["warning"]))

        text.append("\nThese topics may need deeper practice, not just recognition.\n", style=STYLES["cortex_dim"])
    else:
        text.append("No memorization suspects detected.\n", style=Style(color=CORTEX_THEME["success"]))

    text.append("\n")

    # Section 3: Note Effectiveness
    text.append("NOTE EFFECTIVENESS (Pre/Post Error Rates)\n", style=STYLES["cortex_secondary"])
    text.append("-" * 45 + "\n", style=STYLES["cortex_dim"])

    if note_effectiveness:
        for note in note_effectiveness[:5]:
            title = note.get("title", "?")[:25]
            improvement = note.get("improvement")
            reads = note.get("read_count", 0)

            if improvement is not None:
                if improvement > 0:
                    text.append("[+] ", style=Style(color=CORTEX_THEME["success"]))
                    text.append(f"{title:25s} ", style=Style(color=CORTEX_THEME["white"]))
                    text.append(f"+{improvement:.0%} improvement", style=Style(color=CORTEX_THEME["success"]))
                else:
                    text.append("[-] ", style=Style(color=CORTEX_THEME["error"]))
                    text.append(f"{title:25s} ", style=Style(color=CORTEX_THEME["white"]))
                    text.append(f"{improvement:.0%} change", style=Style(color=CORTEX_THEME["error"]))
            else:
                text.append("[?] ", style=STYLES["cortex_dim"])
                text.append(f"{title:25s} ", style=Style(color=CORTEX_THEME["white"]))
                text.append("Pending (need post-read data)", style=STYLES["cortex_dim"])

            text.append(f" ({reads} reads)\n", style=STYLES["cortex_dim"])
    else:
        text.append("No note effectiveness data yet. Read notes and practice.\n", style=STYLES["cortex_dim"])

    text.append("\n")

    # Section 4: Recommended Actions
    text.append("RECOMMENDED ACTIONS\n", style=STYLES["cortex_accent"])
    text.append("-" * 45 + "\n", style=STYLES["cortex_dim"])

    if recommendations:
        for rec in recommendations[:5]:
            module = rec.get("module", "?")
            action = rec.get("action", "Review")
            reason = rec.get("reason", "")
            priority = rec.get("priority", "medium")

            priority_icons = {"high": "[!!!]", "medium": "[!! ]", "low": "[!  ]"}
            priority_colors = {
                "high": CORTEX_THEME["error"],
                "medium": CORTEX_THEME["warning"],
                "low": CORTEX_THEME["accent"],
            }

            icon = priority_icons.get(priority, "[*  ]")
            color = priority_colors.get(priority, CORTEX_THEME["dim"])

            text.append(f"{icon} ", style=Style(color=color))
            text.append(f"M{module:02d}: ", style=Style(color=CORTEX_THEME["accent"]))
            text.append(f"{action}", style=Style(color=CORTEX_THEME["white"]))
            if reason:
                text.append(f" - {reason[:30]}", style=STYLES["cortex_dim"])
            text.append("\n")
    else:
        text.append("No specific actions recommended. Keep studying!\n", style=Style(color=CORTEX_THEME["success"]))

    return Panel(
        text,
        title="[bold cyan]LEARNING SIGNALS[/bold cyan]",
        border_style=Style(color=CORTEX_THEME["secondary"]),
        box=box.HEAVY,
        padding=(1, 2),
    )


# =============================================================================
# SOCRATIC TUTORING PANELS
# =============================================================================


def render_socratic_panel(
    console: Console,
    question: str,
    scaffold_level: int = 0,
    is_opening: bool = False,
) -> None:
    """
    Render a Socratic tutoring question panel.

    Args:
        console: Rich Console instance
        question: The Socratic question to display
        scaffold_level: Current scaffolding level (0-4)
        is_opening: Whether this is the opening question
    """
    # Color progresses from cyan (pure Socratic) to magenta (heavy scaffolding)
    level_styles = {
        0: CORTEX_THEME["primary"],    # Pure Socratic - Pink
        1: CORTEX_THEME["secondary"],  # Nudge - Orchid
        2: CORTEX_THEME["warning"],    # Partial - Gold
        3: CORTEX_THEME["accent"],     # Worked - Deep Pink
        4: CORTEX_THEME["error"],      # Reveal - Hot Pink/Red
    }

    border_color = level_styles.get(scaffold_level, CORTEX_THEME["primary"])

    # Build content
    content = Text()

    if is_opening:
        content.append("Let's think through this together.\n\n", style=STYLES["cortex_dim"])

    content.append(question, style=Style(color=CORTEX_THEME["white"]))
    content.append("\n\n", style="default")
    content.append("(Type your thoughts, or 'skip' to see the answer)", style=STYLES["cortex_dim"])

    # Title varies by scaffold level
    titles = {
        0: "LET'S THINK TOGETHER",
        1: "THINKING TOGETHER",
        2: "HERE'S A HINT",
        3: "LET ME HELP",
        4: "THE ANSWER",
    }
    title = titles.get(scaffold_level, "LET'S THINK TOGETHER")

    panel = Panel(
        content,
        title=f"[bold]{title}[/bold]",
        border_style=Style(color=border_color),
        box=box.DOUBLE,
        padding=(1, 2),
    )
    console.print(panel)


def render_socratic_success_panel(
    console: Console,
    message: str,
    turns_count: int,
) -> None:
    """
    Render success message when learner solves through Socratic dialogue.

    Args:
        console: Rich Console instance
        message: Celebration message
        turns_count: Number of turns it took
    """
    content = Text()
    content.append("EXCELLENT!\n\n", style=STYLES["cortex_success"])
    content.append(message, style=Style(color=CORTEX_THEME["white"]))

    if turns_count <= 2:
        content.append("\n\nYou got there quickly!", style=STYLES["cortex_dim"])
    elif turns_count <= 4:
        content.append("\n\nGood persistence!", style=STYLES["cortex_dim"])
    else:
        content.append("\n\nThat's how real learning happens.", style=STYLES["cortex_dim"])

    panel = Panel(
        content,
        title="[bold green]BREAKTHROUGH[/bold green]",
        border_style=Style(color=CORTEX_THEME["success"]),
        box=box.DOUBLE,
        padding=(1, 2),
    )
    console.print(panel)


def render_remediation_panel(
    console: Console,
    recommendations: list[dict],
) -> None:
    """
    Render prerequisite gap recommendations.

    Args:
        console: Rich Console instance
        recommendations: List of recommendation dicts with "gap", "reason", "atoms"
    """
    if not recommendations:
        return

    content = Text()
    content.append("Based on our conversation, you might want to review:\n\n", style=STYLES["cortex_dim"])

    for rec in recommendations[:3]:  # Limit to 3 recommendations
        gap = rec.get("gap", "Unknown topic")
        reason = rec.get("reason", "")
        atoms = rec.get("atoms", [])

        content.append(f"  {gap}\n", style=Style(color=CORTEX_THEME["accent"], bold=True))

        if reason:
            content.append(f"    {reason}\n", style=STYLES["cortex_dim"])

        if atoms:
            content.append("    Suggested cards:\n", style=STYLES["cortex_dim"])
            for atom in atoms[:2]:  # Show max 2 atoms per gap
                front = atom.get("front", "")
                atom_type = atom.get("atom_type", "")
                content.append(f"      [{atom_type}] ", style=Style(color=CORTEX_THEME["secondary"]))
                content.append(f"{front}\n", style=Style(color=CORTEX_THEME["white"]))

        content.append("\n")

    panel = Panel(
        content,
        title="[bold yellow]RECOMMENDED REVIEW[/bold yellow]",
        border_style=Style(color=CORTEX_THEME["warning"]),
        box=box.ROUNDED,
        padding=(1, 2),
    )
    console.print(panel)


def render_dialogue_summary_panel(
    console: Console,
    resolution: str,
    turns_count: int,
    duration_ms: int,
    scaffold_level: int,
) -> None:
    """
    Render a summary of the Socratic dialogue session.

    Args:
        console: Rich Console instance
        resolution: How the dialogue ended
        turns_count: Total turns in dialogue
        duration_ms: Total duration
        scaffold_level: Maximum scaffold level reached
    """
    content = Text()

    # Resolution indicator
    resolution_styles = {
        "self_solved": (CORTEX_THEME["success"], "Self-Solved"),
        "guided_solved": (CORTEX_THEME["success"], "Guided Solution"),
        "gave_up": (CORTEX_THEME["warning"], "Skipped"),
        "revealed": (CORTEX_THEME["error"], "Answer Revealed"),
    }

    color, label = resolution_styles.get(resolution, (CORTEX_THEME["dim"], resolution))

    content.append("Outcome: ", style=STYLES["cortex_dim"])
    content.append(f"{label}\n", style=Style(color=color, bold=True))

    # Stats
    content.append(f"Dialogue turns: {turns_count}\n", style=STYLES["cortex_dim"])
    content.append(f"Duration: {duration_ms // 1000}s\n", style=STYLES["cortex_dim"])
    content.append(f"Scaffolding needed: Level {scaffold_level}/4\n", style=STYLES["cortex_dim"])

    panel = Panel(
        content,
        title="[dim]Dialogue Complete[/dim]",
        border_style=Style(color=CORTEX_THEME["dim"]),
        box=box.ROUNDED,
        padding=(0, 1),
    )
    console.print(panel)
