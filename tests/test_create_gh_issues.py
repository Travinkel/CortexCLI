import sys
import json
import os


def test_dry_run_prints_135_commands():
    # Import the module directly to avoid spawning an external python process
    from scripts import create_gh_issues as m

    issues = m.generate_issues()
    assert len(issues) == 135, f"Expected 135 issues from generate_issues(), got {len(issues)}"

    commands = [m.build_command(i) for i in issues]
    assert len(commands) == 135, f"Expected 135 commands, got {len(commands)}"

    for cmd in commands:
        assert cmd.startswith("gh issue create"), f"Unexpected command: {cmd}"
