# Configuration Guide

Complete guide to configuring notion-learning-sync.

## Configuration Overview

Notion-learning-sync uses **Pydantic Settings** for configuration management, which provides:
- Type-safe environment variables
- Validation at startup
- Clear error messages
- Default values with documentation
- `.env` file support

All configuration is managed through environment variables defined in `.env`.

## Quick Start

1. Copy the example config:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your values

3. Start the service:
   ```bash
   python main.py
   ```

## Configuration File Location

The `.env` file must be in the project root:

```
notion-learning-sync/
├── .env              ← Your configuration
├── .env.example      ← Template
├── config.py         ← Settings definition
└── main.py
```

**Important**: Never commit `.env` to git! It's already in `.gitignore`.

## Complete Configuration Reference

### Database Configuration

#### DATABASE_URL

**Required**: Yes
**Type**: PostgreSQL connection string
**Default**: `postgresql://postgres:learning123@localhost:5432/notion_learning_sync`

PostgreSQL database connection string in the format:
```
postgresql://[user]:[password]@[host]:[port]/[database]
```

**Examples**:
```bash
# Local development
DATABASE_URL=postgresql://postgres:mypassword@localhost:5432/notion_learning_sync

# Remote database
DATABASE_URL=postgresql://user:pass@db.example.com:5432/learning

# With special characters in password (URL-encode them)
DATABASE_URL=postgresql://user:p%40ssw0rd@localhost:5432/learning
```

**Connection pooling** (via SQLAlchemy):
- Default pool size: 5
- Max overflow: 10
- Pool recycle: 3600 seconds

---

### Notion API Configuration

#### NOTION_API_KEY

**Required**: Yes
**Type**: String
**Default**: Empty string (must be set)

Your Notion integration API key. Get this from:
1. Visit https://www.notion.so/my-integrations
2. Create a new integration
3. Copy the "Internal Integration Token" (starts with `secret_`)

**Example**:
```bash
NOTION_API_KEY=secret_1234567890abcdefghijklmnopqrstuvwxyz
```

**Security**:
- Never share this key
- Never commit to git
- Rotate regularly
- Use minimum required permissions

#### NOTION_VERSION

**Required**: No
**Type**: String
**Default**: `2022-06-28`

Notion API version to use. See [Notion API versioning](https://developers.notion.com/reference/versioning).

**Example**:
```bash
NOTION_VERSION=2022-06-28
```

**Note**: Only change if you need features from a newer API version.

---

### Notion Database IDs

All database IDs are **optional**. Only configure the databases you want to sync.

#### How to find Database IDs

1. Open your database in Notion
2. Copy the URL:
   ```
   https://www.notion.so/workspace/DATABASE_ID?v=VIEW_ID
   ```
3. The `DATABASE_ID` is the 32-character hex string

**Example URL**:
```
https://www.notion.so/myworkspace/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6?v=...
                                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                 This is your DATABASE_ID
```

#### FLASHCARDS_DB_ID

**Required**: No
**Type**: String (32 hex chars)
**Default**: None

Notion database ID for flashcards.

**Expected Notion schema**:
| Property | Type | Required | Description |
|----------|------|----------|-------------|
| CardID | Text | No | e.g., "NET-M1-015-DEC" |
| Question | Title | Yes | Front of flashcard |
| Answer | Rich Text | Yes | Back of flashcard |
| Concept | Relation | No | Link to Concepts DB |
| Module | Relation | No | Link to Modules DB |
| Status | Select | No | Active, Archived, etc. |

**Example**:
```bash
FLASHCARDS_DB_ID=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

#### CONCEPTS_DB_ID

Notion database ID for concepts (L2 - atomic knowledge units).

**Expected schema**:
| Property | Type | Description |
|----------|------|-------------|
| Name | Title | Concept name |
| Definition | Rich Text | Formal definition |
| Cluster | Relation | Link to Concept Clusters |
| Status | Select | to_learn, active, mastered, etc. |

**Example**:
```bash
CONCEPTS_DB_ID=b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6a1
```

#### CONCEPT_AREAS_DB_ID

Notion database ID for concept areas (L0 - top-level domains).

**Expected schema**:
| Property | Type | Description |
|----------|------|-------------|
| Name | Title | Area name (e.g., "Computer Science") |
| Description | Rich Text | Detailed description |
| Domain | Select | STEM, Humanities, etc. |

**Example**:
```bash
CONCEPT_AREAS_DB_ID=c3d4e5f6g7h8i9j0k1l2m3n4o5p6a1b2
```

#### CONCEPT_CLUSTERS_DB_ID

Notion database ID for concept clusters (L1 - thematic groupings).

**Expected schema**:
| Property | Type | Description |
|----------|------|-------------|
| Name | Title | Cluster name |
| ConceptArea | Relation | Parent area |
| ExamWeight | Number | Percentage (0-100) |

**Example**:
```bash
CONCEPT_CLUSTERS_DB_ID=d4e5f6g7h8i9j0k1l2m3n4o5p6a1b2c3
```

#### MODULES_DB_ID

Notion database ID for modules (week/chapter units).

**Example**:
```bash
MODULES_DB_ID=e5f6g7h8i9j0k1l2m3n4o5p6a1b2c3d4
```

#### TRACKS_DB_ID

Notion database ID for tracks (course-level progressions).

**Example**:
```bash
TRACKS_DB_ID=f6g7h8i9j0k1l2m3n4o5p6a1b2c3d4e5
```

#### PROGRAMS_DB_ID

Notion database ID for programs (degrees, certifications).

**Example**:
```bash
PROGRAMS_DB_ID=g7h8i9j0k1l2m3n4o5p6a1b2c3d4e5f6
```

---

### Anki Integration

#### ANKI_CONNECT_URL

**Required**: No
**Type**: URL
**Default**: `http://127.0.0.1:8765`

URL for the AnkiConnect plugin.

**Setup**:
1. Install [AnkiConnect](https://foosoft.net/projects/anki-connect/) plugin in Anki
2. Default port is 8765
3. Ensure Anki is running when syncing

**Example**:
```bash
ANKI_CONNECT_URL=http://127.0.0.1:8765

# Custom port
ANKI_CONNECT_URL=http://localhost:9000
```

**Testing connection**:
```bash
curl http://127.0.0.1:8765 -X POST -d '{"action":"version","version":6}'
```

#### ANKI_DECK_NAME

**Required**: No
**Type**: String
**Default**: `LearningOS::Synced`

Target Anki deck for synced cards. Use `::` for nested decks.

**Examples**:
```bash
# Top-level deck
ANKI_DECK_NAME=Notion Flashcards

# Nested deck
ANKI_DECK_NAME=LearningOS::Synced

# Deep nesting
ANKI_DECK_NAME=Studies::Computer Science::Networks
```

**Note**: The deck will be created automatically if it doesn't exist.

#### ANKI_NOTE_TYPE

**Required**: No
**Type**: String
**Default**: `Basic`

Anki note type to use for new cards.

**Common values**:
- `Basic` - Front/Back
- `Basic (and reversed card)` - Front/Back + Back/Front
- `Cloze` - Cloze deletion cards

**Example**:
```bash
ANKI_NOTE_TYPE=Basic
```

**Custom note types**: You can create custom note types in Anki, just use the exact name.

---

### AI Integration

Configure AI providers for content cleaning and rewriting.

#### GEMINI_API_KEY

**Required**: No (unless using AI features)
**Type**: String
**Default**: None

Google Gemini API key for AI operations.

**Setup**:
1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create an API key
3. Copy and paste into `.env`

**Example**:
```bash
GEMINI_API_KEY=AIzaSyABC123def456GHI789jkl012MNO345pqr678
```

**Free tier limits**:
- 60 requests per minute
- 1500 requests per day

#### VERTEX_PROJECT

**Required**: No (alternative to Gemini)
**Type**: String (GCP Project ID)
**Default**: None

Google Cloud project ID for Vertex AI (alternative to Gemini API).

**Setup**:
1. Create a GCP project
2. Enable Vertex AI API
3. Set up authentication: `gcloud auth application-default login`

**Example**:
```bash
VERTEX_PROJECT=my-learning-project-123456
```

**When to use Vertex vs Gemini**:
- **Gemini API**: Simpler, free tier, API key auth
- **Vertex AI**: Higher quotas, production use, IAM auth

#### VERTEX_LOCATION

**Required**: No
**Type**: String (GCP region)
**Default**: `us-central1`

Google Cloud region for Vertex AI.

**Common regions**:
- `us-central1` - Iowa, USA
- `us-east1` - South Carolina, USA
- `europe-west1` - Belgium
- `asia-northeast1` - Tokyo

**Example**:
```bash
VERTEX_LOCATION=us-central1
```

#### AI_MODEL

**Required**: No
**Type**: String
**Default**: `gemini-2.0-flash`

AI model to use for content operations.

**Gemini models**:
- `gemini-2.0-flash` - Fast, good for flashcards (recommended)
- `gemini-1.5-pro` - More capable, slower
- `gemini-1.0-pro` - Older, stable

**Example**:
```bash
AI_MODEL=gemini-2.0-flash
```

---

### Atomicity Thresholds

Evidence-based thresholds from spaced repetition research.

#### ATOMICITY_FRONT_MAX_WORDS

**Required**: No
**Type**: Integer
**Default**: 25

Maximum words allowed in flashcard questions.

**Source**: Wozniak (SuperMemo) and Gwern research on knowledge formulation.

**Rationale**: Questions longer than 25 words are typically:
- Harder to parse quickly
- Contain multiple sub-questions
- Violate "minimum information principle"

**Examples**:
```bash
# Default (recommended)
ATOMICITY_FRONT_MAX_WORDS=25

# More strict
ATOMICITY_FRONT_MAX_WORDS=20

# Relaxed
ATOMICITY_FRONT_MAX_WORDS=30
```

#### ATOMICITY_BACK_OPTIMAL_WORDS

**Required**: No
**Type**: Integer
**Default**: 5

Optimal words for flashcard answers.

**Source**: SuperMemo research on retention rates.

**Rationale**: Answers ≤5 words have:
- Higher retention rates
- Faster recall
- Less cognitive load

**Example**:
```bash
ATOMICITY_BACK_OPTIMAL_WORDS=5
```

#### ATOMICITY_BACK_WARNING_WORDS

**Required**: No
**Type**: Integer
**Default**: 15

Warning threshold for verbose answers.

**Rationale**: Answers >15 words typically need splitting into multiple cards.

**Example**:
```bash
ATOMICITY_BACK_WARNING_WORDS=15
```

#### ATOMICITY_BACK_MAX_CHARS

**Required**: No
**Type**: Integer
**Default**: 120

Maximum characters for answers.

**Source**: Cognitive Load Theory (CLT) - working memory limits.

**Rationale**: ~120 characters is the upper limit for comfortable single-item recall.

**Example**:
```bash
ATOMICITY_BACK_MAX_CHARS=120
```

#### ATOMICITY_MODE

**Required**: No
**Type**: String (`relaxed` or `strict`)
**Default**: `relaxed`

Atomicity enforcement mode.

**Modes**:
- `relaxed`: Warn about violations, don't block
- `strict`: Reject cards that violate thresholds

**Example**:
```bash
# Warn but allow (recommended for new users)
ATOMICITY_MODE=relaxed

# Strict enforcement
ATOMICITY_MODE=strict
```

---

### Sync Behavior

#### SYNC_INTERVAL_MINUTES

**Required**: No
**Type**: Integer
**Default**: 120 (2 hours)

Auto-sync interval in minutes. Set to 0 to disable.

**Examples**:
```bash
# Every 2 hours (default)
SYNC_INTERVAL_MINUTES=120

# Every 30 minutes (aggressive)
SYNC_INTERVAL_MINUTES=30

# Daily
SYNC_INTERVAL_MINUTES=1440

# Disable auto-sync
SYNC_INTERVAL_MINUTES=0
```

**Note**: Manual syncs via API are always available.

#### PROTECT_NOTION

**Required**: No
**Type**: Boolean
**Default**: `true`

Prevent writes back to Notion (safety flag).

**Values**:
- `true`: Read-only mode (recommended)
- `false`: Allow writes to Notion

**Example**:
```bash
# Read-only (recommended)
PROTECT_NOTION=true

# Allow writes (dangerous!)
PROTECT_NOTION=false
```

**Important**: Always keep this `true` unless you have a specific reason to write back to Notion.

#### DRY_RUN

**Required**: No
**Type**: Boolean
**Default**: `false`

Log actions without making database changes.

**Use cases**:
- Testing configuration
- Previewing sync results
- Debugging issues

**Example**:
```bash
# Normal mode
DRY_RUN=false

# Test mode (log only, no changes)
DRY_RUN=true
```

---

### Logging

#### LOG_LEVEL

**Required**: No
**Type**: String
**Default**: `INFO`

Logging verbosity level.

**Levels** (from most to least verbose):
- `DEBUG` - All details, SQL queries, API requests
- `INFO` - Normal operations, sync summaries
- `WARNING` - Warnings and errors
- `ERROR` - Errors only

**Examples**:
```bash
# Production
LOG_LEVEL=INFO

# Development/debugging
LOG_LEVEL=DEBUG

# Minimal output
LOG_LEVEL=ERROR
```

#### LOG_FILE

**Required**: No
**Type**: String (file path)
**Default**: `logs/notion_learning_sync.log`

Log file path. Set to empty string for stdout only.

**Examples**:
```bash
# Default
LOG_FILE=logs/notion_learning_sync.log

# Custom path
LOG_FILE=/var/log/notion-sync.log

# Stdout only (no file)
LOG_FILE=

# Windows path
LOG_FILE=C:\logs\notion_sync.log
```

**Log rotation**: Logs rotate at 10MB by default (configurable in code).

---

### API Server

#### API_HOST

**Required**: No
**Type**: String (IP address)
**Default**: `127.0.0.1`

API server host/IP to bind to.

**Values**:
- `127.0.0.1` - Localhost only (secure)
- `0.0.0.0` - All interfaces (for Docker/remote access)

**Examples**:
```bash
# Localhost only (recommended for dev)
API_HOST=127.0.0.1

# All interfaces (for production/Docker)
API_HOST=0.0.0.0
```

#### API_PORT

**Required**: No
**Type**: Integer
**Default**: 8100

API server port.

**Example**:
```bash
API_PORT=8100

# Custom port
API_PORT=3000
```

---

## Configuration Validation

The service validates configuration at startup. If there are errors, you'll see clear messages:

### Missing required config
```
ValidationError: 1 validation error for Settings
notion_api_key
  Field required [type=missing]
```

**Fix**: Set the missing variable in `.env`

### Invalid type
```
ValidationError: 1 validation error for Settings
atomicity_front_max_words
  Input should be a valid integer [type=int_type]
```

**Fix**: Ensure numeric values don't have quotes in `.env`

### Invalid database URL
```
ValueError: Invalid database URL format
```

**Fix**: Check your `DATABASE_URL` format

---

## Configuration Best Practices

### Development Setup

```bash
# .env for development
DATABASE_URL=postgresql://postgres:dev@localhost:5432/notion_learning_sync
NOTION_API_KEY=secret_dev_key_here
FLASHCARDS_DB_ID=your_test_db_id

# Relaxed settings for development
ATOMICITY_MODE=relaxed
PROTECT_NOTION=true
DRY_RUN=false
LOG_LEVEL=DEBUG

# No AI (save on API calls)
GEMINI_API_KEY=
```

### Production Setup

```bash
# .env for production
DATABASE_URL=postgresql://user:secure_pass@prod-db:5432/learning
NOTION_API_KEY=secret_prod_key_here

# All databases configured
FLASHCARDS_DB_ID=...
CONCEPTS_DB_ID=...
# etc.

# Production settings
ATOMICITY_MODE=strict
PROTECT_NOTION=true
DRY_RUN=false
LOG_LEVEL=INFO
SYNC_INTERVAL_MINUTES=120

# AI enabled
GEMINI_API_KEY=prod_api_key
```

### Security Checklist

- [ ] `.env` is in `.gitignore`
- [ ] API keys are never committed to git
- [ ] `PROTECT_NOTION=true` in production
- [ ] Database password is strong
- [ ] `API_HOST=127.0.0.1` unless needed otherwise
- [ ] Regular key rotation

---

## Environment-Specific Configs

You can use different `.env` files per environment:

```bash
# Development
cp .env.example .env.dev

# Production
cp .env.example .env.prod

# Testing
cp .env.example .env.test
```

Then specify which to use:

```bash
# Linux/Mac
export ENV_FILE=.env.prod
python main.py

# Windows
set ENV_FILE=.env.prod
python main.py
```

Or modify `config.py`:
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", ".env"),
        ...
    )
```

---

## Programmatic Access

Access settings in Python code:

```python
from config import get_settings

settings = get_settings()

# Read values
print(settings.database_url)
print(settings.atomicity_front_max_words)

# Helper methods
configured_dbs = settings.get_configured_notion_databases()
has_ai = settings.has_ai_configured()
```

---

## Troubleshooting

### Config not loading

**Problem**: Changes to `.env` not taking effect

**Solution**:
1. Ensure `.env` is in the project root
2. Restart the service (config is loaded once at startup)
3. Check for syntax errors in `.env`
4. Don't use quotes unless values contain spaces

### Database connection fails

**Problem**: Can't connect to PostgreSQL

**Solutions**:
1. Check PostgreSQL is running: `pg_isready`
2. Verify credentials: `psql $DATABASE_URL -c "SELECT 1;"`
3. Check firewall/network
4. Ensure database exists: `createdb notion_learning_sync`

### Notion API errors

**Problem**: Authentication errors with Notion

**Solutions**:
1. Verify API key starts with `secret_`
2. Check integration has access to databases
3. Ensure databases are shared with the integration
4. Test API key manually: [Notion API Explorer](https://developers.notion.com/)

---

## Reference

### Complete .env Template

See [.env.example](../.env.example) in the project root.

### Configuration Schema

See [config.py](../config.py) for the complete Pydantic model with types and defaults.

### Default Values Summary

| Setting | Default | Can be Empty? |
|---------|---------|---------------|
| `DATABASE_URL` | `postgresql://postgres:learning123@localhost:5432/notion_learning_sync` | No |
| `NOTION_API_KEY` | `""` | No (must set) |
| `NOTION_VERSION` | `2022-06-28` | No |
| `ANKI_CONNECT_URL` | `http://127.0.0.1:8765` | No |
| `ANKI_DECK_NAME` | `LearningOS::Synced` | No |
| `ATOMICITY_FRONT_MAX_WORDS` | `25` | No |
| `ATOMICITY_BACK_OPTIMAL_WORDS` | `5` | No |
| `ATOMICITY_BACK_WARNING_WORDS` | `15` | No |
| `ATOMICITY_BACK_MAX_CHARS` | `120` | No |
| `ATOMICITY_MODE` | `relaxed` | No |
| `SYNC_INTERVAL_MINUTES` | `120` | No |
| `PROTECT_NOTION` | `true` | No |
| `DRY_RUN` | `false` | No |
| `LOG_LEVEL` | `INFO` | No |
| `LOG_FILE` | `logs/notion_learning_sync.log` | Yes |
| `API_HOST` | `127.0.0.1` | No |
| `API_PORT` | `8100` | No |

---

## Next Steps

- [Quickstart Guide](quickstart.md) - Set up and run the service
- [Database Schema](database-schema.md) - Understand the data model
- [Cleaning Pipeline](cleaning-pipeline.md) - Configure content quality
