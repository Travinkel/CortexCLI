"""
Source presets for subdivided adaptive learning.

Provides filtering presets for:
- Module ranges (1-3, 4-7, etc.)
- ITN assessments (final, practice, skills)
- Topic themes (subnetting, osi-model, ipv6, etc.)
"""

from __future__ import annotations

from typing import TypedDict


class SourcePreset(TypedDict, total=False):
    """Configuration for a source preset."""

    modules: list[int]
    sections: list[str]
    source_file: str
    name: str


SOURCE_PRESETS: dict[str, SourcePreset] = {
    # === Module Ranges (with source file mapping) ===
    "modules-1-3": {
        "modules": [1, 2, 3],
        "source_file": "CCNAModule1-3.txt",
        "name": "Foundations",
    },
    "modules-4-7": {
        "modules": [4, 5, 6, 7],
        "source_file": "CCNAModule4-7.txt",
        "name": "Physical & Data Link",
    },
    "modules-8-10": {
        "modules": [8, 9, 10],
        "source_file": "CCNAModule8-10.txt",
        "name": "Network Layer Basics",
    },
    "modules-11-13": {
        "modules": [11, 12, 13],
        "source_file": "CCNAModule11-13.txt",
        "name": "IP Addressing",
    },
    "modules-14-15": {
        "modules": [14, 15],
        "source_file": "CCNAModule14-15.txt",
        "name": "Transport & Application",
    },
    "modules-16-17": {
        "modules": [16, 17],
        "source_file": "CCNAModule16-17.txt",
        "name": "Security & Integration",
    },

    # === ITN Assessments ===
    "itn-final": {
        "source_file": "ITNFinalPacketTracer.txt",
        "name": "ITN Final Packet Tracer",
    },
    "itn-practice": {
        "source_file": "ITNPracticeFinalExam.txt",
        "name": "ITN Practice Final Exam",
    },
    "itn-test": {
        "source_file": "ITNPracticeTest.txt",
        "name": "ITN Practice Test",
    },
    "itn-skills": {
        "source_file": "ITNSkillsAssessment.txt",
        "name": "ITN Skills Assessment",
    },

    # === Topic Themes (cross-module) ===
    "subnetting": {
        "sections": ["11.4", "11.5", "11.6", "11.7", "11.8"],
        "name": "Subnetting Mastery",
    },
    "osi-model": {
        "sections": ["3.1", "3.2", "3.3", "3.4"],
        "name": "OSI Model",
    },
    "binary-math": {
        "modules": [5],
        "sections": ["5.1", "5.2", "5.3"],
        "name": "Number Systems",
    },
    "ipv6": {
        "sections": ["12.1", "12.2", "12.3", "12.4", "12.5"],
        "name": "IPv6 Addressing",
    },
    "switching": {
        "modules": [6, 7],
        "name": "Switching & VLANs",
    },
    "routing": {
        "sections": ["16.1", "16.2", "16.3", "16.4"],
        "name": "Routing Fundamentals",
    },
    "security": {
        "sections": ["17.1", "17.2", "17.3", "17.4"],
        "name": "Network Security",
    },
    "transport": {
        "sections": ["14.1", "14.2", "14.3", "14.4"],
        "name": "TCP/UDP Transport",
    },
    "ios-config": {
        "sections": ["2.1", "2.2", "2.3", "2.4"],
        "name": "IOS Configuration",
    },
    "arp-dhcp": {
        "sections": ["9.1", "9.2", "9.3", "10.1", "10.2", "10.3"],
        "name": "ARP & DHCP",
    },
    "ethernet": {
        "sections": ["4.1", "4.2", "4.3", "4.4", "6.1", "6.2"],
        "name": "Ethernet Fundamentals",
    },

    # === Full Curriculum ===
    "all": {"modules": list(range(1, 18)), "name": "Full Curriculum"},
}


def parse_modules_arg(arg: str) -> list[int]:
    """
    Parse flexible module argument.

    Supports:
    - Single module: "5" -> [5]
    - Comma-separated: "5,7,9" -> [5, 7, 9]
    - Range: "5-7" -> [5, 6, 7]
    - Mixed: "1-3,11-13" -> [1, 2, 3, 11, 12, 13]

    Args:
        arg: Module specification string

    Returns:
        Sorted list of unique module numbers

    Raises:
        ValueError: If module number is out of range (1-17)
    """
    modules = []
    for part in arg.split(","):
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            try:
                start, end = part.split("-", 1)
                start_int = int(start.strip())
                end_int = int(end.strip())
                modules.extend(range(start_int, end_int + 1))
            except ValueError as e:
                raise ValueError(f"Invalid range '{part}': {e}") from e
        else:
            try:
                modules.append(int(part))
            except ValueError as e:
                raise ValueError(f"Invalid module number '{part}': {e}") from e

    # Validate range
    result = sorted(set(modules))
    invalid = [m for m in result if m < 1 or m > 17]
    if invalid:
        raise ValueError(f"Module numbers must be 1-17, got: {invalid}")

    return result


def parse_sections_arg(arg: str) -> list[str]:
    """
    Parse sections argument.

    Args:
        arg: Comma-separated section IDs (e.g., "11.1,11.2,11.3")

    Returns:
        List of section ID strings
    """
    return [s.strip() for s in arg.split(",") if s.strip()]


def get_preset(name: str) -> SourcePreset | None:
    """
    Get a source preset by name.

    Args:
        name: Preset name (case-insensitive)

    Returns:
        SourcePreset dict or None if not found
    """
    return SOURCE_PRESETS.get(name.lower())


def list_presets() -> list[tuple[str, str]]:
    """
    List all available presets.

    Returns:
        List of (preset_name, display_name) tuples
    """
    return [(k, v.get("name", k)) for k, v in SOURCE_PRESETS.items()]


def resolve_filters(
    modules_arg: str | None = None,
    sections_arg: str | None = None,
    source_preset: str | None = None,
) -> tuple[list[int] | None, list[str] | None, str | None]:
    """
    Resolve filtering arguments into concrete values.

    Priority:
    1. Explicit --modules and --sections override preset
    2. --source preset provides defaults
    3. None values mean "no filter" (all content)

    Args:
        modules_arg: --modules argument value
        sections_arg: --sections argument value
        source_preset: --source preset name

    Returns:
        Tuple of (modules, sections, source_file)
    """
    modules: list[int] | None = None
    sections: list[str] | None = None
    source_file: str | None = None

    # Start with preset if provided
    if source_preset:
        preset = get_preset(source_preset)
        if preset:
            modules = preset.get("modules")
            sections = preset.get("sections")
            source_file = preset.get("source_file")

    # Override with explicit arguments
    if modules_arg:
        modules = parse_modules_arg(modules_arg)

    if sections_arg:
        sections = parse_sections_arg(sections_arg)

    return modules, sections, source_file


def describe_filters(
    modules: list[int] | None,
    sections: list[str] | None,
    source_file: str | None,
) -> str:
    """
    Generate human-readable description of active filters.

    Args:
        modules: Active module filter
        sections: Active section filter
        source_file: Active source file filter

    Returns:
        Description string for display
    """
    parts = []

    if modules:
        if len(modules) == 1:
            parts.append(f"Module {modules[0]}")
        elif modules == list(range(modules[0], modules[-1] + 1)):
            parts.append(f"Modules {modules[0]}-{modules[-1]}")
        else:
            parts.append(f"Modules {','.join(map(str, modules))}")

    if sections:
        if len(sections) <= 3:
            parts.append(f"Sections {', '.join(sections)}")
        else:
            parts.append(f"Sections {sections[0]}...{sections[-1]} ({len(sections)} total)")

    if source_file:
        # Clean up filename for display
        display_name = source_file.replace(".txt", "").replace("CCNA", "").replace("ITN", "ITN ")
        parts.append(f"Source: {display_name}")

    if not parts:
        return "Full Curriculum (no filters)"

    return " | ".join(parts)
