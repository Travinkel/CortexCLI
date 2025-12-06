# Quickstart Guide

Get notion-learning-sync running in 10 minutes.

## Prerequisites

- Python 3.11 or later
- PostgreSQL 15 or later
- Notion account with API access
- (Optional) Anki with AnkiConnect plugin
- (Optional) Google Cloud account for Vertex AI or Gemini API key

## Step 1: Clone and Setup

```bash
cd E:\Repo\project-astartes\notion-learning-sync

# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Create Database

```bash
# Create PostgreSQL database
createdb notion_learning_sync

# Or using psql
psql -U postgres -c "CREATE DATABASE notion_learning_sync;"

# Run migrations
psql -d notion_learning_sync -f src/db/migrations/001_initial_schema.sql
```

Verify the database was created:

```bash
psql -d notion_learning_sync -c "\dt"
```

You should see 17 tables (7 staging + 10 canonical).

## Step 3: Get Notion API Key

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Click "New integration"
3. Name it "Learning Sync" and select your workspace
4. Copy the "Internal Integration Token" (starts with `secret_`)
5. Share your Notion databases with this integration:
   - Open each database in Notion
   - Click "..." → "Add connections" → Select your integration

## Step 4: Get Notion Database IDs

For each Notion database you want to sync:

1. Open the database in Notion
2. Copy the URL - it looks like:
   ```
   https://www.notion.so/{workspace}/{database_id}?v={view_id}
   ```
3. The `database_id` is the 32-character alphanumeric string

Example:
```
https://www.notion.so/myworkspace/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6?v=...
                                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                 This is your database_id
```

## Step 5: Configure Environment

Copy the example config:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Required
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/notion_learning_sync
NOTION_API_KEY=secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Your Notion database IDs
FLASHCARDS_DB_ID=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
CONCEPTS_DB_ID=b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6a1
CONCEPT_AREAS_DB_ID=c3d4e5f6g7h8i9j0k1l2m3n4o5p6a1b2
CONCEPT_CLUSTERS_DB_ID=d4e5f6g7h8i9j0k1l2m3n4o5p6a1b2c3
MODULES_DB_ID=e5f6g7h8i9j0k1l2m3n4o5p6a1b2c3d4
TRACKS_DB_ID=f6g7h8i9j0k1l2m3n4o5p6a1b2c3d4e5
PROGRAMS_DB_ID=g7h8i9j0k1l2m3n4o5p6a1b2c3d4e5f6

# Optional: Anki
ANKI_CONNECT_URL=http://127.0.0.1:8765
ANKI_DECK_NAME=LearningOS::Synced

# Optional: AI (for cleaning)
GEMINI_API_KEY=your_gemini_api_key
# OR
VERTEX_PROJECT=your-gcp-project-id
```

**Security Note**: Never commit your `.env` file to git!

## Step 6: Start the Service

```bash
# Development mode with auto-reload
uvicorn main:app --reload --port 8100

# Or using the entry point
python main.py
```

You should see:

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Starting notion-learning-sync service...
INFO:     Database tables initialized
INFO:     Service started on 127.0.0.1:8100
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8100 (Press CTRL+C to quit)
```

## Step 7: Verify Installation

Open your browser to http://localhost:8100/docs

You should see the FastAPI interactive documentation (Swagger UI).

### Test the health endpoint

```bash
curl http://localhost:8100/health
```

Expected response:

```json
{
  "status": "healthy",
  "timestamp": "2025-12-01T10:30:00.000Z",
  "components": {
    "database": "ok",
    "notion": "configured",
    "anki": "configured",
    "ai": "configured"
  },
  "config": {
    "protect_notion": true,
    "dry_run": false,
    "configured_databases": [
      "flashcards",
      "concepts",
      "concept_areas",
      "concept_clusters",
      "modules",
      "tracks",
      "programs"
    ]
  }
}
```

## Next Steps

Now that the service is running:

1. **Run your first sync** (coming soon)
   ```bash
   curl -X POST http://localhost:8100/api/sync/notion
   ```

2. **Explore the database**
   ```bash
   psql -d notion_learning_sync
   \dt  # List tables
   SELECT * FROM v_review_queue_summary;
   ```

3. **Learn about the architecture**
   - Read [Architecture Overview](architecture.md)
   - Understand [Database Schema](database-schema.md)

4. **Configure the cleaning pipeline**
   - See [Cleaning Pipeline](cleaning-pipeline.md)
   - Adjust atomicity thresholds in `.env`

5. **Set up Anki sync**
   - Install [AnkiConnect](https://foosoft.net/projects/anki-connect/)
   - Read [Anki Integration](anki-integration.md)

## Troubleshooting

### Database connection error

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution**: Ensure PostgreSQL is running and credentials are correct:

```bash
psql -U postgres -c "SELECT 1;"
```

### Notion API authentication error

```
notion_client.errors.APIResponseError: Authentication token is invalid
```

**Solution**:
1. Verify your API key in `.env` starts with `secret_`
2. Ensure you've shared your databases with the integration
3. Check the integration hasn't been deleted in Notion

### Import errors

```
ModuleNotFoundError: No module named 'fastapi'
```

**Solution**: Activate your virtual environment and reinstall dependencies:

```bash
venv\Scripts\activate
pip install -r requirements.txt
```

### Port already in use

```
OSError: [Errno 48] Address already in use
```

**Solution**: Either kill the process using port 8100 or use a different port:

```bash
uvicorn main:app --reload --port 8101
```

## Common Configuration Issues

### All databases showing as not configured

Check that your `.env` file:
1. Exists in the project root
2. Has no syntax errors
3. Uses the exact variable names (uppercase, with underscores)
4. Database IDs are 32 characters (no hyphens)

### AI provider not working

Gemini API:
```bash
# Test your API key
curl "https://generativelanguage.googleapis.com/v1/models?key=YOUR_API_KEY"
```

Vertex AI:
```bash
# Verify you're authenticated
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

## Getting Help

- Check the [Configuration Guide](configuration.md) for all settings
- Read the [API Reference](api-reference.md) for endpoint details
- Review logs in `logs/notion_learning_sync.log`
- Set `LOG_LEVEL=DEBUG` in `.env` for detailed logging

## What's Next?

You now have a working notion-learning-sync service! Here are some recommended next steps:

1. Configure your Notion databases to match the expected schema
2. Run a test sync with a small database
3. Explore the cleaning pipeline features
4. Set up automated syncing with a cron job or Windows Task Scheduler

Happy learning!
