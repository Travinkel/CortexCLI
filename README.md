#  Cortex-CLI

**The DARPA Digital Tutor for Developers**

`cortex-cli` is a terminal-based adaptive learning system designed to rival DARPA's Digital Tutor and Knewton's adaptive engine. It is a **personalized learning companion optimized for developers and technical learners** who live in the command line.

Built on cognitive science (FSRS, Cognitive Load Theory, Testing Effect), Cortex-CLI provides:
- 🧠 **Mastery-based learning** - Not time-based, but capability-based
- 🎯 **Adaptive content selection** - Z-Score algorithm prioritizes what you need most
- 📊 **Diagnostic feedback** - Identifies error classes, not just "right" or "wrong"
- 🔬 **Science-backed** - Every feature grounded in peer-reviewed research
- 💻 **Terminal-native** - Offline-first, scriptable, zero latency

While `right-learning` provides the full web-based platform experience and `greenlight` accelerates TDD/BDD workflows, `cortex-cli` owns the **knowledge consolidation** space—building deep, durable knowledge that compounds over time.

---

## The Right Learning Ecosystem

`cortex-cli` is not a standalone application; it is a specialized client for the `right-learning` platform and integrates with Greenlight for IDE-first, runtime learning atoms.

```
+-----------------------------------------------------------------------+
|                      right-learning (The Platform)                      |
|          Multi-user • Web-based • Enterprise-grade • Socratic AI        |
+-----------------------------------------------------------------------+
                                     ^
                                     | REST API
                                     |
+------------------------------------+-----------------------------------+
|                              cortex-cli (The Utility)                    |
|                 Single-user • Terminal • Fast • Scriptable               |
+------------------------------------+-----------------------------------+
|             API MODE             |         PIPELINE MODE         |        OFFLINE MODE        |
| (Terminal study sessions)        | (CI/CD content validation)    | (Air-gapped study)         |
+----------------------------------+-------------------------------+----------------------------+
```

### Greenlight Integration (IDE-first)

Greenlight is the IDE/workbench sibling to cortex-cli. It owns the high-friction, runtime atoms that benefit from an editor, diff view, and git safety rails, while cortex-cli keeps the fast terminal drills.

- Owned by Greenlight: code submission with tests/perf gates, debugging/fault isolation, diff review and “minimal fix” tasks, code understanding/trace, code construction/skeleton fill, config/CLI sequencing with terminal emulator, project-scale tasks with branches/worktrees and git guidance, architecture/trade-off reasoning tied to a codebase, testing/verification on real code.
- Owned by cortex-cli: recognition/recall (MCQ variants, cloze, short answer, numeric), structural drills (matching, sequencing, Parsons), lightweight meta-cognitive prompts, comparison/explanation/creative text atoms.
- Shared wrappers: confidence/difficulty ratings, reflection/self-correction flows, error tagging. If an atom requires running code, inspecting diffs, or suggesting git commands, it routes to Greenlight; cortex-cli can still show the result in the terminal.

### Three Core Roles

1.  **Developer's Companion (API Mode):** For quick, focused study sessions directly in your terminal. It connects to the `right-learning` API to fetch your profile and sync results.
2.  **Content Pipeline (Pipeline Mode):** A powerful ETL and validation tool. It can parse, validate, and ingest learning content from various sources (including Notion) into the `right-learning` platform. It's designed to run in CI/CD environments.
3.  **Offline Fallback (Offline Mode):** Export your study profile, use `cortex-cli` with a local SQLite database in an air-gapped environment (like on a plane), and import your progress back to the platform later.

---

## Learning Atom Types

Cortex-CLI implements a **universal taxonomy of learning atoms** based on cognitive science research:

### Recognition & Recall
- **Binary Choice** (True/False)
- **Multiple Choice** (with diagnostic distractors)
- **Cloze Deletion** (fill-in-the-blank)
- **Short Answer** (exact or fuzzy match)
- **Numeric Entry** (with unit awareness)

### Structural & Relational
- **Parsons Problems** (reorder code blocks)
- **Matching** (concept ↔ definition)
- **Sequencing** (order procedural steps)
- **Graph Construction** (prerequisite mapping)

### Production & Application
- **Code Submission** (sandboxed execution)
- **Debugging Challenges** (spot and fix bugs)
- **Design Decisions** (architecture trade-offs)
- **CLI Simulation** (terminal command sequences)

### Meta-Cognitive
- **Confidence Rating** (calibrate self-assessment)
- **Reflection Prompts** ("explain your reasoning")
- **Error Classification** (slip vs misconception)

**Total:** 80+ distinct atom types organized by cognitive operation.

See [Universal Taxonomy of Learning Atoms](docs/reference/learning-atoms.md) for the complete reference.

---

## Notion as an ETL Source

We have a specific philosophy for Notion: it is an **authoring and collaboration tool**, not a structured CMS. `cortex-cli` facilitates this by acting as the "T" (Transform) and "L" (Load) in an ETL pipeline.

1.  **Extract:** Use Notion's UI and AI features to draft and structure raw notes.
2.  **Transform & Load:** Use `cortex-cli` to pull this structured text, validate it against the platform's schema, and load it into the `right-learning` database as high-quality learning atoms.

---

## Quick Start

### Prerequisites

- Python 3.11+
- Access to a `right-learning` platform instance (for API mode) or a local PostgreSQL/SQLite database (for offline/pipeline mode).

### Installation

```bash
# Clone the repository
git clone https://github.com/rightlearning/cortex-cli.git
cd cortex-cli

# Set up virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows

# Install dependencies
pip install -e .
```

### Configuration

`cortex-cli` auto-detects its mode based on your environment.

1.  **API Mode (Default):**
    Create a `.env` file and configure the API endpoint:
    ```
    RIGHT_LEARNING_API_URL=https://api.right-learning.com
    RIGHT_LEARNING_API_KEY=your_api_key
    ```

2.  **Offline Mode:**
    If no API is reachable, it will default to using a local SQLite database. You can force this by setting `CORTEX_MODE=offline`.

3.  **Pipeline Mode:**
    This is auto-detected in CI environments (e.g., `CI=true`).

### Start Studying

```bash
# Check system readiness and mode
cortex status

# Start an adaptive study session (uses API by default)
cortex start

# Do a quick 5-minute review of your top struggle zones
cortex start --quick

# Focus on a specific module
cortex start -m 11
```

---

## CLI Commands

### Study Commands (`API` or `Offline` Mode)

- `cortex start`: Start a full, adaptive study session.
- `cortex start --quick`: Start a short session focused on top struggle areas.
- `cortex start -m <module_id>`: Focus a session on specific modules.
- `cortex resume`: Resume the last saved session.
- `cortex stats`: View your learning statistics.

### Focus Stream Commands (Local Study)

- `cortex study`: Start a Focus Stream study session using imported curriculum.
- `cortex study --course SDE2`: Focus on a specific course.
- `cortex study -c SDE2 -b 10 -k git`: 10 cards about Git from SDE2.
- `cortex queue`: Show the prioritized Focus Stream queue.
- `cortex queue --verbose`: Show Z-Score component breakdown.

### Curriculum Commands

- `cortex curriculum import <file>`: Import a curriculum file (SDE2.txt, PROGII.txt, etc.).
- `cortex curriculum list`: List imported curriculum courses.
- `cortex curriculum atoms <course>`: Show atoms for a specific course.

### Content Commands (`Pipeline` Mode)

- `cortex validate <path>`: Validate learning content in a local directory.
- `cortex validate --strict`: Fail CI checks on any validation warning.
- `cortex ingest <path>`: Ingest validated content into the platform.

### Sync Commands

- `cortex sync`: Sync progress from offline mode to the platform.
- `cortex export`: Export your profile and due cards for offline study.
- `cortex import <file>`: Import progress from an offline session.

---

## Split-Pane Interactive Learning

Cortex-CLI features a **Terminal User Interface (TUI)** with multiple layout modes optimized for different learning scenarios:

### Horizontal Split (Theory + Practice)
```
┌─────────────────────────────────────────────────┐
│ LEARN PANE                                      │
│ • Concept explanation                           │
│ • Examples                                      │
│ • ASCII diagrams                                │
├─────────────────────────────────────────────────┤
│ PRACTICE PANE                                   │
│ • Live coding                                   │
│ • Quiz area                                     │
│ • Terminal simulation                           │
├─────────────────────────────────────────────────┤
│ FEEDBACK PANE                                   │
│ • Diagnostic feedback (error class, hints)      │
└─────────────────────────────────────────────────┘
```

### Vertical Split (Side-by-side)
Perfect for comparing reference code with your solution.

### 3-Pane (Advanced)
Reference + Workspace + Console for complex CLI exercises.

See [TUI Design Documentation](docs/explanation/tui-design.md) for full details.

---

## Scientific Foundations

Every feature in Cortex-CLI is grounded in peer-reviewed cognitive science research:

| Research Area | Implementation |
|---------------|----------------|
| **Testing Effect** (Roediger & Butler) | Active recall atoms (Cloze, Short Answer) |
| **Cognitive Load Theory** (Sweller) | Parsons Problems, faded scaffolding |
| **Interleaving Effect** (Bjork) | Z-Score mixing algorithm |
| **Metacognition** (Zimmerman) | Confidence ratings, reflection prompts |
| **Hypercorrection Effect** (Metcalfe) | High-confidence errors trigger intervention |
| **Expertise Reversal** (Kalyuga) | Adaptive scaffolding based on mastery |

**Zero pseudoscience:** No Learning Styles, no Learning Pyramid, no Left/Right Brain myths.

See [Scientific Foundations](docs/reference/scientific-foundations.md) for complete research references.

---

## Documentation

- **[Vision: DARPA Digital Tutor](docs/explanation/vision-darpa-tutor.md)** - Strategic positioning and ecosystem architecture
- **[Learning Atoms Reference](docs/reference/learning-atoms.md)** - Complete taxonomy of 80+ atom types
- **[Scientific Foundations](docs/reference/scientific-foundations.md)** - Cognitive science research backing
- **[TUI Design](docs/explanation/tui-design.md)** - Split-pane interface architecture
- **[API Endpoints](docs/reference/api-endpoints.md)** - REST API reference
- **[Database Schema](docs/reference/database-schema.md)** - PostgreSQL schema documentation

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Check type safety
mypy src

# Lint and format
ruff check . --fix
```
