#!/usr/bin/env python3
"""Script to update documentation files with new feature documentation."""

import os

# Base path for docs
BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_PATH = os.path.join(BASE_PATH, "docs")

# Architecture additions to insert after Adaptive Layer section
ARCHITECTURE_ADDITIONS = '''### Cortex Session Layer

Interactive study sessions with remediation support.

```
src/cortex/
  session.py         # CortexSession class - main study loop
    - _post_break_grace      # Fatigue detection grace period
    - sync_anki()            # Bi-directional Anki sync
    - _offer_remediation_menu()  # Post-session options
    - _generate_study_notes()    # Adaptive notes generation
    - _full_anki_sync()          # Full push+pull sync
```

**Key Features**:
- Fatigue detection with post-break grace period (5 questions)
- Automatic Anki stat sync at session start
- Post-session remediation menu (notes, questions, sync)
- Adaptive study notes based on error rate

### Content Generation Layer

LLM-powered content generation for study support.

```
src/content/generation/
  llm_generator.py   # LLMFlashcardGenerator class
    - generate_from_section()   # Generate cards from section
    - generate_study_notes()    # Adaptive study notes
      - STUDY_NOTES_PROMPT      # Prompt template
```

**Study Notes Depth**:
- `brief` - error rate < 25%
- `standard` - error rate 25-50%
- `comprehensive` - error rate >= 50%

### Delivery Layer'''

# Study notes generation new file
STUDY_NOTES_CONTENT = '''# Study Notes Generation

This document explains the adaptive study notes generation feature, which creates personalized review materials based on learner struggles during study sessions.

---

## Overview

When learners struggle with specific sections during a Cortex study session, the system can generate targeted study notes using LLM. The depth and content of notes adapt based on error rate, ensuring learners receive appropriate support without cognitive overload.

**Location**: `src/content/generation/llm_generator.py`

---

## Adaptive Depth Selection

Note depth automatically adjusts based on section-specific error rate:

| Error Rate | Depth | Content Volume | Use Case |
|------------|-------|----------------|----------|
| < 25% | `brief` | Core concept only | Near-mastery; minor clarification needed |
| 25-50% | `standard` | Core + memory anchors | Moderate struggle; reinforcement needed |
| >= 50% | `comprehensive` | Full deep-dive | Significant gaps; thorough remediation required |

### Rationale

Adaptive depth prevents two failure modes:
1. **Under-support**: Brief notes when comprehensive review is needed
2. **Cognitive overload**: Excessive detail for concepts nearly mastered

---

## Note Structure

Generated notes follow a consistent structure optimized for retention:

### Core Concept
Essential definition and explanation of the topic. Written in clear, technical language appropriate for the subject matter.

### What You Got Wrong
Specific analysis of errors made during the session:
- Common misconceptions identified
- Pattern analysis across multiple errors
- Distinction between similar concepts often confused

### Memory Anchors
Mnemonic devices and associations to aid retention:
- Acronyms and abbreviations
- Visual analogies
- Real-world comparisons
- Memorable phrases

### Quick Reference
Condensed summary for rapid review:
- Key facts in bullet form
- Comparison tables
- Decision trees for troubleshooting

### Key Commands
CLI/configuration commands relevant to the topic (when applicable):
- Exact syntax with parameters
- Common variations
- Verification commands

---

## Implementation

### Prompt Template

The `STUDY_NOTES_PROMPT` template in `src/content/generation/llm_generator.py`:

```python
STUDY_NOTES_PROMPT = """
Generate study notes for the following section based on learner struggles.

Section: {section_title}
Content: {section_content}

Learner Data:
- Error patterns: {error_patterns}
- Cognitive state: {cognitive_state}
- Struggle areas: {struggle_data}

Depth: {depth}

Structure your notes with:
1. Core Concept - essential definition
2. What You Got Wrong - specific error analysis
3. Memory Anchors - mnemonics and associations
4. Quick Reference - condensed summary
5. Key Commands - relevant CLI commands (if applicable)
"""
```

### Generator Method

```python
def generate_study_notes(
    self,
    section_content: str,
    section_id: str,
    section_title: str,
    struggle_data: dict,
    error_patterns: list[str],
    cognitive_state: dict,
    depth: str = "standard",
) -> str:
    """Generate adaptive study notes for a struggled section."""
    prompt = STUDY_NOTES_PROMPT.format(
        section_title=section_title,
        section_content=section_content,
        error_patterns=error_patterns,
        cognitive_state=cognitive_state,
        struggle_data=struggle_data,
        depth=depth,
    )
    return self._call_llm(prompt)
```

### Depth Calculation

In `src/cortex/session.py`:

```python
def _calculate_section_error_rate(self, section_id: str) -> float:
    section_atoms = [a for a in self._session_atoms if a.get("section_id") == section_id]
    if not section_atoms:
        return 0.0
    incorrect = sum(1 for a in section_atoms if a.get("_incorrect"))
    return incorrect / len(section_atoms)

def _determine_depth(self, error_rate: float) -> str:
    if error_rate < 0.25:
        return "brief"
    elif error_rate < 0.50:
        return "standard"
    return "comprehensive"
```

---

## Output Handling

### Terminal Display

Notes are rendered using Rich markdown for optimal terminal display:

```python
from rich.console import Console
from rich.markdown import Markdown

console = Console()
console.print(Markdown(notes))
```

### File Persistence

Notes are saved to disk for later reference:

```
outputs/notes/{timestamp}-{section_ids}.md
```

Example: `outputs/notes/20251212-143022-3.2-5.1.md`

### File Format

Saved notes include metadata header:

```markdown
---
generated: 2025-12-12T14:30:22
sections: [3.2, 5.1]
depth: comprehensive
session_id: abc123
---

# Study Notes: Section 3.2 - IP Addressing

## Core Concept
...
```

---

## Configuration

### Environment Variables

```bash
# Output directory for saved notes
STUDY_NOTES_OUTPUT_DIR=outputs/notes

# LLM provider for generation
GEMINI_API_KEY=your-api-key
```

### Default Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Output format | Markdown | Rich-compatible markdown |
| Auto-save | Enabled | Always save to disk |
| Display | Enabled | Show in terminal |

---

## Integration Points

### Session Integration

Study notes generation integrates with the post-session remediation menu:

1. User completes study session
2. System identifies struggled sections
3. Remediation menu presents option 1: "Generate study notes"
4. User selects option
5. System calculates depth per section
6. LLM generates notes
7. Notes displayed and saved

### Anki Integration

Generated notes can inform Anki filtered deck queries:
- Notes reference section IDs
- Same sections used for Anki suggestions
- Enables coordinated desktop + mobile review

---

## Design Decisions

### Why Adaptive Depth?

Fixed-depth notes fail learners:
- **Too brief**: Missing information for confused learners
- **Too detailed**: Cognitive overload for near-mastery concepts

Adaptive depth matches support to need.

### Why Include Error Analysis?

Generic notes miss the learning opportunity. Specific error analysis:
- Addresses actual misconceptions
- Provides targeted correction
- Creates retrieval cues tied to mistakes

### Why Persist to Disk?

Terminal output is ephemeral. Disk persistence enables:
- Later review without regeneration
- Note accumulation over time
- Integration with other study tools

### Why Markdown Format?

Markdown provides:
- Terminal rendering via Rich
- Web/editor compatibility
- Lightweight file size
- Human-readable source

---

## See Also

- [Session Remediation](session-remediation.md) - Post-session remediation system
- [Cognitive Diagnosis](cognitive-diagnosis.md) - NCDE error classification
- [Configure Anki Sync](../how-to/configure-anki-sync.md) - Anki integration
'''

# Anki sync additions
ANKI_SYNC_ADDITIONS = '''
---

## Automatic Session Sync

Cortex automatically synchronizes with Anki at session start to ensure scheduling decisions reflect mobile reviews.

### How It Works

When you start a Cortex session:

1. System attempts to connect to Anki via AnkiConnect
2. If connected, pulls latest FSRS statistics
3. Updates local database with Anki review data
4. Session queue reflects current memory state

### Graceful Degradation

If Anki is unavailable:
- Session continues without sync
- Warning logged: "Anki not available - skipping sync"
- No user action required

### Implementation

In `src/cortex/session.py`:

```python
def sync_anki(self):
    """Pull FSRS stats from Anki before loading queue."""
    try:
        self._anki_client.pull_stats()
        logger.info("Anki stats synced")
    except ConnectionError:
        logger.info("Anki not available - skipping sync")
```

---

## Post-Session Full Sync

The remediation menu offers full bidirectional sync after study sessions.

### Menu Option

```
[3] Full Anki sync (push atoms + pull stats)
```

### What It Does

| Direction | Operation | Data |
|-----------|-----------|------|
| **Push** | Cortex -> Anki | New atoms, updated content |
| **Pull** | Anki -> Cortex | FSRS stability, review counts, due dates |

### Use Cases

- After adding new content to database
- After extended mobile study session
- Before starting focused Cortex session

### Implementation

```python
def _full_anki_sync(self):
    """Perform full bidirectional Anki sync."""
    console.print("[cyan]Pushing atoms to Anki...[/cyan]")
    self._anki_client.push_atoms()

    console.print("[cyan]Pulling stats from Anki...[/cyan]")
    self._anki_client.pull_stats()

    console.print("[green]Sync complete[/green]")
```

'''

def update_architecture():
    """Update architecture.md with new components."""
    path = os.path.join(DOCS_PATH, "explanation", "architecture.md")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the Delivery Layer section and insert before it
    marker = "### Delivery Layer\n\nPresents content to learners."
    if marker in content and "### Cortex Session Layer" not in content:
        content = content.replace(marker, ARCHITECTURE_ADDITIONS)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated: {path}")
    else:
        print(f"Skipped (already updated or marker not found): {path}")

def create_study_notes_doc():
    """Create study-notes-generation.md."""
    path = os.path.join(DOCS_PATH, "explanation", "study-notes-generation.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(STUDY_NOTES_CONTENT)
    print(f"Created: {path}")

def update_anki_sync():
    """Update configure-anki-sync.md with automatic sync info."""
    path = os.path.join(DOCS_PATH, "how-to", "configure-anki-sync.md")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Add before See Also section
    marker = "---\n\n## See Also"
    if marker in content and "## Automatic Session Sync" not in content:
        content = content.replace(marker, ANKI_SYNC_ADDITIONS + marker)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated: {path}")
    else:
        print(f"Skipped (already updated or marker not found): {path}")

def update_index():
    """Update index.md with new documentation entry."""
    path = os.path.join(DOCS_PATH, "index.md")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Add Study Notes Generation to Explanation section
    marker = "| [Session Remediation](explanation/session-remediation.md) | Hints, retry logic, and post-session suggestions |"
    new_entry = "| [Study Notes Generation](explanation/study-notes-generation.md) | Adaptive study notes algorithm |"

    if marker in content and new_entry not in content:
        content = content.replace(marker, marker + "\n" + new_entry)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated: {path}")
    else:
        print(f"Skipped (already updated or marker not found): {path}")

def update_first_study_session():
    """Update first-study-session.md with remediation menu info."""
    path = os.path.join(DOCS_PATH, "tutorials", "first-study-session.md")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the session end suggestions section and update
    old_section = '''### Session End Suggestions

If you struggled with specific sections, Cortex generates an Anki filtered deck query:

```
ANKI STUDY SUGGESTION

You struggled with 2 section(s). Use this filtered deck query:

deck:CCNA::ITN::* (tag:section:3.2 OR tag:section:5.1) -is:suspended

[Instructions: Anki -> Tools -> Create Filtered Deck -> paste query]
```

See [Session Remediation](../explanation/session-remediation.md) for details on how hints are generated.'''

    new_section = '''### Session End Remediation

If you struggled with specific sections, Cortex presents a remediation menu:

```
REMEDIATION OPTIONS

You struggled with 2 section(s). What would you like to do?

  [1] Generate study notes for struggled topics
  [2] Generate additional practice questions
  [3] Full Anki sync (push atoms + pull stats)
  [s] Skip remediation

Your choice:
```

| Option | What It Does |
|--------|--------------|
| **1** | Generates adaptive study notes based on your error rate |
| **2** | Creates new practice questions using LLM |
| **3** | Syncs your progress to Anki for mobile review |
| **s** | Skips remediation and exits |

See [Session Remediation](../explanation/session-remediation.md) for details on hints and remediation options.'''

    if old_section in content:
        content = content.replace(old_section, new_section)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated: {path}")
    else:
        print(f"Skipped (section not found or already updated): {path}")

def update_cli_commands():
    """Update cli-commands.md with remediation info."""
    path = os.path.join(DOCS_PATH, "reference", "cli-commands.md")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Add session persistence note about remediation
    old_text = '''### Session Persistence

- Auto-saves every 5 questions
- **Ctrl+C** saves and quits
- Resume with `nls cortex resume`
- Sessions expire after 24 hours'''

    new_text = '''### Session Persistence

- Auto-saves every 5 questions
- **Ctrl+C** saves and quits
- Resume with `nls cortex resume`
- Sessions expire after 24 hours

### Post-Session Remediation

At session end, if you struggled with sections, a remediation menu appears:

| Option | Action |
|--------|--------|
| `1` | Generate study notes for struggled topics |
| `2` | Generate additional practice questions |
| `3` | Full Anki sync (push + pull) |
| `s` | Skip remediation |'''

    if old_text in content and "### Post-Session Remediation" not in content:
        content = content.replace(old_text, new_text)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated: {path}")
    else:
        print(f"Skipped (already updated or text not found): {path}")

if __name__ == "__main__":
    print("Updating documentation files...")
    update_architecture()
    create_study_notes_doc()
    update_anki_sync()
    update_index()
    update_first_study_session()
    update_cli_commands()
    print("Done!")
