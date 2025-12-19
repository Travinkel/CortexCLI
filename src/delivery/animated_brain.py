"""
Animated Brain Component using asciimatics.

Creates a pulsing 3D cyberbrain animation for the Cortex boot sequence.
Features volumetric depth shading and neural pulse effects.
"""

from __future__ import annotations

import time
from typing import Callable

from asciimatics.effects import Effect
from asciimatics.event import KeyboardEvent
from asciimatics.exceptions import StopApplication
from asciimatics.renderers import FigletText, StaticRenderer
from asciimatics.scene import Scene
from asciimatics.screen import Screen

# =============================================================================
# 3D VOLUMETRIC BRAIN - ASCII ART WITH DEPTH
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

# Compact 3D brain for smaller terminals
BRAIN_3D_COMPACT = [
    # Frame 1: Base
    r"""
         ▄▄████████▄▄
       ██▒▒░░░░░░░░▒▒██
      █▒░░╔════════╗░░▒█
     █▒░░░║ CORTEX ║░░░▒█
     █▒░░░╚════════╝░░░▒█
      █▒░░░░░░░░░░░░░░▒█
       ██▒▒░░░░░░░░▒▒██
         ▀▀████████▀▀
      ────┤ READY ├────
    """,
    # Frame 2: Left pulse
    r"""
         ▄▄████████▄▄
       ██*▒░░░░░░░░▒▒██
      █*▒░░╔════════╗░░▒█
     █*▒░░░║*CORTEX ║░░░▒█
     █*▒░░░╚════════╝░░░▒█
      █*▒░░░░░░░░░░░░░▒█
       ██*▒░░░░░░░░▒▒██
         ▀▀████████▀▀
      ────┤ PULSE ├────
    """,
    # Frame 3: Right pulse
    r"""
         ▄▄████████▄▄
       ██▒▒░░░░░░░░▒*██
      █▒░░╔════════╗░*▒█
     █▒░░░║ CORTEX*║░░*▒█
     █▒░░░╚════════╝░░*▒█
      █▒░░░░░░░░░░░░░*▒█
       ██▒▒░░░░░░░░▒*██
         ▀▀████████▀▀
      ────┤ SYNC  ├────
    """,
    # Frame 4: Full activation
    r"""
         ▄▄████████▄▄
       ██*▒░░░░░░░░▒*██
      █*▒░░╔════════╗░*▒█
     █*▒░░░║*CORTEX*║░░*▒█
     █*▒░░░╚════════╝░░*▒█
      █*▒░░░░░░░░░░░░░*▒█
       ██*▒░░░░░░░░▒*██
         ▀▀████████▀▀
      ────┤ACTIVE ├────
    """,
]

# Legacy simple brain for very small terminals or fallback
SIMPLE_BRAIN_FRAMES = [
    r"""
     /\  ___  /\
    |  \/   \/  |
    | CORTEX AI |
     \_________/
    """,
    r"""
     /\ *___* /\
    | *\/   \/* |
    | CORTEX AI |
     \_________/
    """,
    r"""
     /\  ___  /\
    |  \/   \/  |
    |*CORTEX AI*|
     \_________/
    """,
]

# Keep legacy BRAIN_FRAMES alias for backwards compatibility
BRAIN_FRAMES = BRAIN_3D_FRAMES


class BrainPulseEffect(Effect):
    """
    Custom effect that pulses the 3D brain ASCII art.

    Renders volumetric depth using gradient shading:
    - █ (solid) = brightest/closest - white
    - ▓ (dark shade) = medium depth - cyan
    - ▒ (medium shade) = deeper - blue
    - ░ (light shade) = deepest - dark blue
    - * (pulse markers) = magenta/pink activation
    """

    def __init__(self, screen: Screen, frames: list[str] | None = None, **kwargs):
        super().__init__(screen, **kwargs)
        self._frames = frames or BRAIN_FRAMES
        self._frame_index = 0
        self._last_update = 0
        self._update_interval = 0.18  # seconds between frames (slightly slower for 3D effect)

    def _update(self, frame_no):
        now = time.time()
        if now - self._last_update > self._update_interval:
            self._frame_index = (self._frame_index + 1) % len(self._frames)
            self._last_update = now

        # Get current frame
        brain_art = self._frames[self._frame_index]
        lines = brain_art.split("\n")

        # Center the brain
        start_y = max(0, (self._screen.height - len(lines)) // 2 - 2)
        max_width = max(len(line) for line in lines)
        start_x = max(0, (self._screen.width - max_width) // 2)

        # Draw with 3D depth coloring
        for i, line in enumerate(lines):
            if start_y + i < self._screen.height:
                for j, char in enumerate(line):
                    x = start_x + j
                    y = start_y + i
                    if x < self._screen.width and y < self._screen.height:
                        # Neural pulse markers - bright magenta
                        if char == '*':
                            self._screen.print_at(char, x, y, colour=Screen.COLOUR_MAGENTA, attr=Screen.A_BOLD)
                        # Solid blocks - brightest (white/cyan)
                        elif char == '█':
                            self._screen.print_at(char, x, y, colour=Screen.COLOUR_WHITE, attr=Screen.A_BOLD)
                        # Dark shade - medium depth (cyan)
                        elif char == '▓':
                            self._screen.print_at(char, x, y, colour=Screen.COLOUR_CYAN, attr=Screen.A_BOLD)
                        # Medium shade - deeper (blue)
                        elif char == '▒':
                            self._screen.print_at(char, x, y, colour=Screen.COLOUR_BLUE)
                        # Light shade - deepest (dark)
                        elif char == '░':
                            self._screen.print_at(char, x, y, colour=Screen.COLOUR_BLUE)
                        # Box drawing and special chars - cyan
                        elif char in '╔╗╚╝║═─┤├▄▀':
                            self._screen.print_at(char, x, y, colour=Screen.COLOUR_CYAN)
                        # Default - cyan for structure
                        else:
                            self._screen.print_at(char, x, y, colour=Screen.COLOUR_CYAN)

    @property
    def stop_frame(self):
        return self._stop_frame

    @property
    def delete_count(self):
        return 0

    def reset(self):
        self._frame_index = 0


class StatusTextEffect(Effect):
    """
    Effect that shows animated status messages.
    """

    def __init__(self, screen: Screen, messages: list[str], **kwargs):
        super().__init__(screen, **kwargs)
        self._messages = messages
        self._current_msg_index = 0
        self._char_index = 0
        self._last_update = 0
        self._char_interval = 0.02  # typing speed
        self._message_hold = 1.0  # hold complete message
        self._message_complete_time = None

    def _update(self, frame_no):
        if self._current_msg_index >= len(self._messages):
            return

        now = time.time()
        msg = self._messages[self._current_msg_index]

        # Typing animation
        if self._char_index < len(msg):
            if now - self._last_update > self._char_interval:
                self._char_index += 1
                self._last_update = now
        else:
            # Message complete
            if self._message_complete_time is None:
                self._message_complete_time = now
            elif now - self._message_complete_time > self._message_hold:
                # Move to next message
                self._current_msg_index += 1
                self._char_index = 0
                self._message_complete_time = None
                return

        # Display current message state
        display_text = msg[:self._char_index]
        y = self._screen.height - 4
        x = max(0, (self._screen.width - len(msg)) // 2)

        # Clear line
        self._screen.print_at(" " * self._screen.width, 0, y)

        # Print prefix
        self._screen.print_at("> ", x - 2, y, colour=Screen.COLOUR_GREEN, attr=Screen.A_BOLD)
        self._screen.print_at(display_text, x, y, colour=Screen.COLOUR_WHITE)

        # Blinking cursor
        if int(now * 2) % 2 == 0 and self._char_index < len(msg):
            self._screen.print_at("_", x + self._char_index, y, colour=Screen.COLOUR_GREEN)

    @property
    def stop_frame(self):
        return self._stop_frame

    @property
    def delete_count(self):
        return 0

    def reset(self):
        self._current_msg_index = 0
        self._char_index = 0


def run_brain_animation(
    duration: float = 3.0,
    messages: list[str] | None = None,
) -> None:
    """
    Run the animated 3D brain boot sequence.

    Args:
        duration: How long to show the animation (seconds)
        messages: Status messages to display during animation

    Frame selection based on terminal size:
    - Large (height >= 25, width >= 80): Full 3D brain with depth shading
    - Medium (height >= 15, width >= 50): Compact 3D brain
    - Small: Legacy simple ASCII brain
    """
    if messages is None:
        messages = [
            "Initializing neural pathways...",
            "Loading knowledge graph...",
            "Calibrating cognitive engine...",
            "CORTEX ONLINE",
        ]

    def demo(screen: Screen):
        # Choose brain size based on terminal dimensions
        if screen.height >= 25 and screen.width >= 80:
            # Full 3D volumetric brain
            frames = BRAIN_3D_FRAMES
        elif screen.height >= 15 and screen.width >= 50:
            # Compact 3D brain
            frames = BRAIN_3D_COMPACT
        else:
            # Fallback to simple ASCII
            frames = SIMPLE_BRAIN_FRAMES

        effects = [
            BrainPulseEffect(screen, frames=frames, stop_frame=int(duration * 20)),
            StatusTextEffect(screen, messages, stop_frame=int(duration * 20)),
        ]

        scenes = [Scene(effects, duration=int(duration * 20), clear=True)]

        # Run with exception handling for keyboard interrupt
        try:
            screen.play(scenes, stop_on_resize=True, repeat=False)
        except StopApplication:
            pass

    try:
        Screen.wrapper(demo, catch_interrupt=True)
    except Exception:
        # Fallback to non-animated display if asciimatics fails
        print("\n" + BRAIN_3D_COMPACT[0])
        for msg in messages:
            print(f"> {msg}")
            time.sleep(0.3)


def run_quick_brain_pulse(duration: float = 1.5) -> None:
    """
    Run a quick brain pulse animation (shorter for session start).
    """
    def demo(screen: Screen):
        # Use compact 3D for quick pulses
        if screen.height >= 15 and screen.width >= 50:
            frames = BRAIN_3D_COMPACT
        else:
            frames = SIMPLE_BRAIN_FRAMES
        effects = [
            BrainPulseEffect(screen, frames=frames, stop_frame=int(duration * 20)),
        ]
        scenes = [Scene(effects, duration=int(duration * 20), clear=True)]
        try:
            screen.play(scenes, stop_on_resize=True, repeat=False)
        except StopApplication:
            pass

    try:
        Screen.wrapper(demo, catch_interrupt=True)
    except Exception:
        # Silently fail for quick animation
        pass


if __name__ == "__main__":
    # Test the animation
    run_brain_animation(
        duration=5.0,
        messages=[
            "Testing neural pathways...",
            "Loading test data...",
            "Animation complete!",
        ],
    )
