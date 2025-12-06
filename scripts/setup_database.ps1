# Database Setup Script for notion-learning-sync
# Run this from the notion-learning-sync directory

Write-Host "=== Setting up notion-learning-sync database ===" -ForegroundColor Cyan

# Configuration
$DB_NAME = "notion_learning_sync"
$DB_USER = "postgres"
$DB_PASSWORD = "learning123"
$DB_HOST = "localhost"
$DB_PORT = "5432"

# Set PGPASSWORD for psql commands
$env:PGPASSWORD = $DB_PASSWORD

# Step 1: Create database if it doesn't exist
Write-Host "`n[1/3] Creating database..." -ForegroundColor Yellow
$dbExists = psql -h $DB_HOST -p $DB_PORT -U $DB_USER -lqt | Select-String -Pattern "\b$DB_NAME\b"

if ($dbExists) {
    Write-Host "Database '$DB_NAME' already exists." -ForegroundColor Green
} else {
    psql -h $DB_HOST -p $DB_PORT -U $DB_USER -c "CREATE DATABASE $DB_NAME;"
    Write-Host "Database '$DB_NAME' created." -ForegroundColor Green
}

# Step 2: Run migrations
Write-Host "`n[2/3] Running migrations..." -ForegroundColor Yellow

$migrations = @(
    "src\db\migrations\001_initial_schema.sql",
    "src\db\migrations\002_anki_import.sql",
    "src\db\migrations\003_sync_audit.sql",
    "src\db\migrations\004_semantic_embeddings.sql"
)

foreach ($migration in $migrations) {
    if (Test-Path $migration) {
        Write-Host "  Running: $migration"
        psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f $migration
    } else {
        Write-Host "  Skipping (not found): $migration" -ForegroundColor Red
    }
}

# Step 3: Verify pgvector extension
Write-Host "`n[3/3] Verifying pgvector extension..." -ForegroundColor Yellow
$pgvectorCheck = psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "SELECT extname FROM pg_extension WHERE extname = 'vector';" -t

if ($pgvectorCheck -match "vector") {
    Write-Host "pgvector extension is installed." -ForegroundColor Green
} else {
    Write-Host "WARNING: pgvector extension not found!" -ForegroundColor Red
    Write-Host "Install it with: CREATE EXTENSION vector;" -ForegroundColor Yellow
}

Write-Host "`n=== Database setup complete! ===" -ForegroundColor Cyan
Write-Host "You can now start the API with: uvicorn src.api.main:app --reload"
