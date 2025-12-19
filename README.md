#  Cortex-CLI

**The "Swiss Army Knife" for the Right Learning Platform.**

`cortex-cli` is a powerful, terminal-based cognitive learning companion. It is designed for developers, content creators, and power-users within the Right Learning ecosystem. While `right-learning` provides the full web-based platform experience, `cortex-cli` offers speed, scriptability, and offline capabilities.

---

## The Right Learning Ecosystem

`cortex-cli` is not a standalone application; it is a specialized client for the `right-learning` platform.

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

### Three Core Roles

1.  **Developer's Companion (API Mode):** For quick, focused study sessions directly in your terminal. It connects to the `right-learning` API to fetch your profile and sync results.
2.  **Content Pipeline (Pipeline Mode):** A powerful ETL and validation tool. It can parse, validate, and ingest learning content from various sources (including Notion) into the `right-learning` platform. It's designed to run in CI/CD environments.
3.  **Offline Fallback (Offline Mode):** Export your study profile, use `cortex-cli` with a local SQLite database in an air-gapped environment (like on a plane), and import your progress back to the platform later.

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
