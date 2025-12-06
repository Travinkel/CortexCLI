# Deployment Guide

Comprehensive guide for deploying notion-learning-sync in development, staging, and production environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Database Initialization](#database-initialization)
- [Configuration](#configuration)
- [Running Migrations](#running-migrations)
- [Service Startup](#service-startup)
- [Monitoring and Logging](#monitoring-and-logging)
- [Backup Strategy](#backup-strategy)
- [Troubleshooting](#troubleshooting)
- [Production Checklist](#production-checklist)

---

## Prerequisites

### System Requirements

**Minimum**:
- CPU: 2 cores
- RAM: 4 GB
- Storage: 20 GB (database growth depends on content volume)
- OS: Windows 10/11, Ubuntu 20.04+, macOS 12+

**Recommended**:
- CPU: 4+ cores
- RAM: 8+ GB
- Storage: 50 GB SSD
- OS: Ubuntu 22.04 LTS

### Software Dependencies

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.11+ | Application runtime |
| PostgreSQL | 15+ | Database |
| Anki | 24.06+ | Flashcard app (optional) |
| AnkiConnect | 6+ | Anki API add-on (optional) |

### External Services

| Service | Required | Purpose |
|---------|----------|---------|
| Notion API | Yes | Content source |
| Gemini AI | Optional | Card rewriting |
| Vertex AI | Optional | Alternative AI provider |

---

## Environment Setup

### Development Environment

**1. Clone Repository**:
```bash
git clone https://github.com/yourusername/notion-learning-sync.git
cd notion-learning-sync
```

**2. Create Virtual Environment**:
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

**3. Install Dependencies**:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development
```

**4. Verify Installation**:
```bash
python -c "import src; print('Installation successful')"
```

---

### Staging Environment

Use Docker for consistent staging environment:

**1. Create docker-compose.yml**:
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: notion_learning_sync
      POSTGRES_USER: nls_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nls_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  app:
    build: .
    environment:
      DATABASE_URL: postgresql://nls_user:${POSTGRES_PASSWORD}@postgres:5432/notion_learning_sync
      NOTION_API_KEY: ${NOTION_API_KEY}
      PROTECT_NOTION: "true"
    ports:
      - "8100:8100"
    depends_on:
      postgres:
        condition: service_healthy
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8100

volumes:
  postgres_data:
```

**2. Start Services**:
```bash
docker-compose up -d
```

**3. Verify Health**:
```bash
curl http://localhost:8100/health
```

---

### Production Environment

**Option A: VM Deployment** (DigitalOcean, AWS EC2, GCP Compute Engine)

**Option B: Container Deployment** (Docker, Kubernetes)

**Option C: Serverless** (AWS Lambda, Google Cloud Run - future)

---

## Database Initialization

### PostgreSQL Installation

**Ubuntu/Debian**:
```bash
sudo apt update
sudo apt install postgresql-15 postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**macOS (Homebrew)**:
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Windows**:
Download installer from [postgresql.org](https://www.postgresql.org/download/windows/)

---

### Create Database

```bash
# Switch to postgres user
sudo -u postgres psql

# In psql console
CREATE DATABASE notion_learning_sync;
CREATE USER nls_user WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE notion_learning_sync TO nls_user;
\q
```

**Verify Connection**:
```bash
psql -h localhost -U nls_user -d notion_learning_sync
```

---

### Database Configuration

**Enable Required Extensions** (for Phase 2.5 embeddings):
```sql
-- Connect to database
\c notion_learning_sync

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgvector (Phase 2.5)
CREATE EXTENSION IF NOT EXISTS vector;
```

**Set Connection Limits**:
```sql
ALTER DATABASE notion_learning_sync SET max_connections = 100;
```

**Configure Performance** (optional):
```sql
-- For development: faster but less durable
ALTER SYSTEM SET fsync = off;
ALTER SYSTEM SET synchronous_commit = off;

-- For production: keep defaults (safe)
-- (Do not disable fsync in production!)
```

---

## Configuration

### Environment Variables

Create `.env` file in project root:

```bash
# Database
DATABASE_URL=postgresql://nls_user:password@localhost:5432/notion_learning_sync

# Notion API
NOTION_API_KEY=secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
PROTECT_NOTION=true  # Prevent accidental writes

# Notion Database IDs (18 databases)
FLASHCARDS_DB_ID=abc123def456...
CONCEPTS_DB_ID=def456ghi789...
CONCEPT_AREAS_DB_ID=ghi789jkl012...
CONCEPT_CLUSTERS_DB_ID=jkl012mno345...
MODULES_DB_ID=mno345pqr678...
TRACKS_DB_ID=pqr678stu901...
PROGRAMS_DB_ID=stu901vwx234...
ACTIVITIES_DB_ID=vwx234yza567...
SESSIONS_DB_ID=yza567bcd890...
QUIZZES_DB_ID=bcd890efg123...
CRITICAL_SKILLS_DB_ID=efg123hij456...
RESOURCES_DB_ID=hij456klm789...
MENTAL_MODELS_DB_ID=klm789nop012...
EVIDENCE_DB_ID=nop012qrs345...
BRAIN_REGIONS_DB_ID=qrs345tuv678...
TRAINING_PROTOCOLS_DB_ID=tuv678wxy901...
PRACTICE_LOGS_DB_ID=wxy901zab234...
ASSESSMENTS_DB_ID=zab234cde567...

# AnkiConnect
ANKI_CONNECT_URL=http://localhost:8765
ANKI_DECK_NAME=LearningOS::Synced
ANKI_NOTE_TYPE=Basic

# AI Configuration
AI_MODEL=gemini-2.0-flash
GEMINI_API_KEY=your_gemini_api_key
# VERTEX_PROJECT_ID=your-gcp-project  # Optional: Vertex AI
# VERTEX_LOCATION=us-central1

# Quality Thresholds (Evidence-Based)
ATOMICITY_FRONT_MAX_WORDS=25
ATOMICITY_BACK_OPTIMAL_WORDS=5
ATOMICITY_BACK_WARNING_WORDS=15
ATOMICITY_BACK_MAX_CHARS=120
ATOMICITY_MODE=relaxed  # strict, relaxed, research

# Sync Configuration
SYNC_INTERVAL_MINUTES=120
SYNC_DRY_RUN=false

# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_DIR=logs
```

---

### Configuration Validation

Verify configuration before starting service:

```bash
python -c "from config import get_settings; s = get_settings(); print(f'Config valid. Databases: {len(s.get_configured_notion_databases())}')"
```

Expected output:
```
Config valid. Databases: 18
```

---

## Running Migrations

### Manual Migration Execution

```bash
# Navigate to project root
cd notion-learning-sync

# Run migrations
python scripts/run_migrations.py

# Expected output:
# ✓ 001_initial_schema already executed
# ⟳ Executing 002_anki_import...
# ✓ 002_anki_import executed successfully
# ⟳ Executing 003_sync_audit...
# ✓ 003_sync_audit executed successfully
```

---

### Migration Script

If `scripts/run_migrations.py` doesn't exist, create it:

```python
# scripts/run_migrations.py
import psycopg2
from pathlib import Path
from config import get_settings

def run_migrations():
    """Execute all pending migrations in order."""
    settings = get_settings()
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()

    # Create migrations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            executed_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.commit()

    # Get executed migrations
    cursor.execute("SELECT version FROM schema_migrations")
    executed = {row[0] for row in cursor.fetchall()}

    # Find migration files
    migrations_dir = Path("src/db/migrations")
    migration_files = sorted(migrations_dir.glob("*.sql"))

    for migration_file in migration_files:
        version = migration_file.stem

        if version in executed:
            print(f"✓ {version} already executed")
            continue

        print(f"⟳ Executing {version}...")
        sql = migration_file.read_text()

        try:
            cursor.execute(sql)
            cursor.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,)
            )
            conn.commit()
            print(f"✓ {version} executed successfully")
        except Exception as e:
            conn.rollback()
            print(f"✗ {version} failed: {e}")
            raise

    cursor.close()
    conn.close()
    print("\n✓ All migrations completed")

if __name__ == "__main__":
    run_migrations()
```

Make executable:
```bash
chmod +x scripts/run_migrations.py
```

---

### Rollback Migrations

**Warning**: Be cautious with rollbacks. Always backup first.

```bash
# Manual rollback example
psql -h localhost -U nls_user -d notion_learning_sync

# In psql:
BEGIN;
DROP TABLE IF EXISTS review_queue CASCADE;
DELETE FROM schema_migrations WHERE version = '005_review_queue';
COMMIT;
```

---

## Service Startup

### Development Mode

Run with auto-reload for development:

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8100
```

Output:
```
INFO:     Uvicorn running on http://0.0.0.0:8100
INFO:     Application startup complete
```

**Verify**:
```bash
curl http://localhost:8100/health
```

---

### Production Mode

**Option 1: Uvicorn with Workers**

```bash
uvicorn src.api.main:app \
  --host 0.0.0.0 \
  --port 8100 \
  --workers 4 \
  --log-level info \
  --access-log
```

**Option 2: Gunicorn with Uvicorn Workers** (recommended)

```bash
gunicorn src.api.main:app \
  --bind 0.0.0.0:8100 \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --access-logfile logs/access.log \
  --error-logfile logs/error.log \
  --log-level info
```

---

### Systemd Service (Linux)

Create `/etc/systemd/system/notion-learning-sync.service`:

```ini
[Unit]
Description=Notion Learning Sync Service
After=network.target postgresql.service

[Service]
Type=notify
User=nls
Group=nls
WorkingDirectory=/opt/notion-learning-sync
Environment="PATH=/opt/notion-learning-sync/venv/bin"
EnvironmentFile=/opt/notion-learning-sync/.env
ExecStart=/opt/notion-learning-sync/venv/bin/gunicorn \
  src.api.main:app \
  --bind 0.0.0.0:8100 \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --log-level info

Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

**Enable and Start**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable notion-learning-sync
sudo systemctl start notion-learning-sync
sudo systemctl status notion-learning-sync
```

---

### CLI Usage

Run CLI commands:

```bash
# Sync from Notion
python -m src.cli.main sync notion --incremental

# Import from Anki
python -m src.cli.main anki import --deck "CCNA Study"

# Run cleaning pipeline
python -m src.cli.main clean run --rewrite

# View review queue
python -m src.cli.main review list
```

---

## Monitoring and Logging

### Log Files

Logs are written to `logs/` directory:

```
logs/
├── nls_2025-12-02.log         # Daily application log
├── errors_2025-12-02.log      # Error-only log
└── access.log                 # HTTP access log (production)
```

**Log Rotation**: Configured in `src/logging_config.py`:
- Daily rotation
- 30-day retention for application logs
- 90-day retention for error logs
- ZIP compression for old logs

---

### Monitoring Endpoints

**Health Check**:
```bash
curl http://localhost:8100/health
```

**Metrics** (future):
```bash
curl http://localhost:8100/metrics
```

---

### External Monitoring

**Uptime Monitoring**:
- Use services like UptimeRobot, Pingdom, or StatusCake
- Monitor `/health` endpoint every 5 minutes

**Log Aggregation** (production):
- Send logs to ELK Stack, Splunk, or Datadog
- Alert on ERROR and CRITICAL logs

**Performance Monitoring**:
- Use New Relic, DataDog, or Prometheus
- Track: API latency, database query time, sync duration

---

## Backup Strategy

### Database Backups

**Automated Daily Backup** (cron job):

```bash
# Create backup script
cat > /opt/backups/backup_nls.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=/opt/backups/nls
DATE=$(date +%Y%m%d_%H%M%S)
FILE="$BACKUP_DIR/nls_backup_$DATE.sql.gz"

mkdir -p $BACKUP_DIR

pg_dump -h localhost -U nls_user notion_learning_sync | gzip > $FILE

# Keep last 30 days
find $BACKUP_DIR -name "nls_backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: $FILE"
EOF

chmod +x /opt/backups/backup_nls.sh

# Add to crontab
crontab -e
# Add line: 0 2 * * * /opt/backups/backup_nls.sh
```

**Manual Backup**:
```bash
pg_dump -h localhost -U nls_user notion_learning_sync > backup.sql
```

**Restore from Backup**:
```bash
psql -h localhost -U nls_user -d notion_learning_sync < backup.sql
```

---

### Configuration Backups

Backup `.env` file securely:

```bash
# Encrypt backup
gpg --symmetric --cipher-algo AES256 .env

# Store .env.gpg in secure location (not in git!)

# Restore
gpg --decrypt .env.gpg > .env
```

---

## Troubleshooting

### Common Issues

#### Issue: Service won't start

**Symptoms**:
```
uvicorn.error.lifespan.startup: Application startup failed
```

**Diagnosis**:
```bash
# Check configuration
python -c "from config import get_settings; get_settings()"

# Check database connection
psql -h localhost -U nls_user -d notion_learning_sync
```

**Solutions**:
1. Verify `.env` file exists and is loaded
2. Check DATABASE_URL is correct
3. Ensure PostgreSQL is running
4. Verify database user has proper permissions

---

#### Issue: Notion API authentication fails

**Symptoms**:
```
NotionAPIError: Invalid API key
```

**Solutions**:
1. Verify NOTION_API_KEY in `.env`
2. Check API key has not expired
3. Confirm integration has access to databases
4. Test with curl:
   ```bash
   curl -H "Authorization: Bearer $NOTION_API_KEY" \
        -H "Notion-Version: 2022-06-28" \
        https://api.notion.com/v1/users/me
   ```

---

#### Issue: Database migration fails

**Symptoms**:
```
✗ 003_sync_audit failed: relation "sync_runs" already exists
```

**Solutions**:
1. Check `schema_migrations` table:
   ```sql
   SELECT * FROM schema_migrations ORDER BY executed_at;
   ```
2. Manually mark migration as executed if it ran partially:
   ```sql
   INSERT INTO schema_migrations (version) VALUES ('003_sync_audit');
   ```
3. Or rollback and re-run

---

#### Issue: High memory usage

**Symptoms**: Python process using >2GB RAM

**Diagnosis**:
```bash
# Check memory usage
ps aux | grep python

# Check database connection pool
psql -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'notion_learning_sync';"
```

**Solutions**:
1. Reduce batch size for large syncs
2. Adjust connection pool settings
3. Enable garbage collection more frequently
4. Use streaming for large datasets

---

#### Issue: Slow sync performance

**Symptoms**: Sync taking >5 minutes for 1000 cards

**Diagnosis**:
```bash
# Check Notion API rate limiting
curl -I https://api.notion.com

# Check database performance
psql -c "EXPLAIN ANALYZE SELECT * FROM stg_notion_flashcards LIMIT 100;"
```

**Solutions**:
1. Verify indexes exist on frequently queried columns
2. Use incremental sync instead of full sync
3. Increase batch size (if memory allows)
4. Check network latency to Notion API

---

## Production Checklist

### Pre-Deployment

- [ ] Environment variables configured (`.env` file)
- [ ] Database created and accessible
- [ ] Migrations executed successfully
- [ ] Notion API key configured and tested
- [ ] All 18 Notion database IDs configured
- [ ] AnkiConnect accessible (if using Anki sync)
- [ ] Gemini API key configured (if using AI rewriting)
- [ ] Health check endpoint responding
- [ ] Logs directory writable
- [ ] Backup script configured

### Security

- [ ] `PROTECT_NOTION=true` enabled
- [ ] Database password is strong (16+ chars)
- [ ] `.env` file not committed to git
- [ ] PostgreSQL not exposed to internet
- [ ] API authentication configured (future)
- [ ] HTTPS enabled (production)
- [ ] Firewall rules configured
- [ ] Regular security updates scheduled

### Monitoring

- [ ] Uptime monitoring configured
- [ ] Error alerting configured
- [ ] Log rotation enabled
- [ ] Backup verification tested
- [ ] Disk space monitoring enabled
- [ ] Database backup scheduled (daily)

### Documentation

- [ ] Architecture documented
- [ ] Deployment process documented
- [ ] Troubleshooting guide available
- [ ] Rollback procedure documented
- [ ] Contact information for support

---

## Scaling Considerations

### Vertical Scaling

Increase resources for single instance:
- CPU: 4 → 8 cores
- RAM: 8 → 16 GB
- Storage: 50 → 100 GB SSD

### Horizontal Scaling (Future)

Run multiple application instances:
- Load balancer (nginx, HAProxy)
- Shared PostgreSQL database
- Redis for caching (Phase 2.5+)
- Background job queue (Celery, RQ)

---

## Further Reading

- [Architecture Overview](./architecture.md)
- [Configuration Guide](./configuration.md)
- [API Reference](./api-reference.md)
- [Testing Guide](./testing-guide.md)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Uvicorn Deployment](https://www.uvicorn.org/deployment/)
