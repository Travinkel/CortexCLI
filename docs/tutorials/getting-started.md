# Tutorial: Getting Started with Cortex

This tutorial guides you through setting up Cortex from scratch. By the end, you will have a working system that syncs content from Notion to PostgreSQL and is ready for Anki integration.

**Time required**: 15-20 minutes

**Prerequisites**:
- Python 3.11+
- PostgreSQL 15+
- A Notion account with at least one database
- Git

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/project-astartes/notion-learning-sync.git
cd notion-learning-sync
```

---

## Step 2: Create a Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

---

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs FastAPI, SQLAlchemy, Typer, Rich, Pydantic, and Loguru.

---

## Step 4: Create the PostgreSQL Database

```bash
createdb notion_learning_sync
```

Verify:
```bash
psql -U postgres -c "\l" | grep notion_learning_sync
```

---

## Step 5: Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with required settings:

```bash
# Database connection
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/notion_learning_sync

# Notion API credentials
NOTION_API_KEY=secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Getting Your Notion API Key

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **New integration**
3. Name it "Cortex" and select your workspace
4. Copy the Internal Integration Token (starts with `secret_`)

### Getting Notion Database IDs

Extract the 32-character ID from the database URL:

```
https://www.notion.so/myworkspace/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6?v=...
                                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                 This is your database ID
```

Add to `.env`:
```bash
FLASHCARDS_DB_ID=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
CONCEPTS_DB_ID=b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6a1
```

### Share Databases with Integration

For each Notion database:
1. Open the database
2. Click **...** menu > **Add connections**
3. Select your "Cortex" integration

---

## Step 6: Initialize the Database

```bash
nls db migrate --migration 001
```

Verify tables exist:
```bash
psql -d notion_learning_sync -c "\dt"
```

Expected tables: `stg_notion_flashcards`, `clean_atoms`, `clean_concepts`, `sync_log`.

---

## Step 7: Test the Configuration

```bash
nls info
```

Expected output:
```
notion-learning-sync Configuration
+-----------------+-------------------------------+
| Setting         | Value                         |
+-----------------+-------------------------------+
| Database URL    | localhost:5432/notion_...     |
| Notion API Key  | ***                           |
| PROTECT_NOTION  | True                          |
+-----------------+-------------------------------+
```

---

## Step 8: Run Your First Sync

```bash
# Preview without changes
nls sync notion --dry-run

# Run actual sync
nls sync notion
```

Expected output:
```
Sync Results
+---------------+-------+---------+---------+
| Entity Type   | Added | Updated | Skipped |
+---------------+-------+---------+---------+
| flashcards    | 150   | 0       | 0       |
| concepts      | 45    | 0       | 0       |
+---------------+-------+---------+---------+
```

---

## Step 9: Verify the Data

```bash
psql -d notion_learning_sync -c "SELECT COUNT(*) FROM clean_atoms;"
```

Or start the API server:
```bash
uvicorn main:app --reload --port 8100
```

Open [http://localhost:8100/docs](http://localhost:8100/docs) for the Swagger UI.

---

## Step 10: Run a Quality Check

```bash
nls clean check --limit 100
```

---

## Summary

You have:
1. Created a PostgreSQL database with the Cortex schema
2. Configured Notion integration
3. Synced content from Notion to PostgreSQL
4. Verified quality metrics for learning atoms

---

## Next Steps

- [First Study Session](first-study-session.md) - Run your first adaptive study session
- [Configure Anki Sync](../how-to/configure-anki-sync.md) - Set up bidirectional Anki sync

---

## Troubleshooting

### Database Connection Error

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution**: Verify PostgreSQL is running (`pg_isready`) and check credentials in `.env`.

### Notion Authentication Error

```
notion_client.errors.APIResponseError: Authentication token is invalid
```

**Solution**: Verify API key starts with `secret_` and databases are shared with the integration.

### Module Not Found

```
ModuleNotFoundError: No module named 'fastapi'
```

**Solution**: Activate virtual environment and reinstall: `pip install -r requirements.txt`.
