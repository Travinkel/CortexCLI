-- Migration 003: Sync Audit Tables
-- Purpose: Track sync runs, timestamps, and checkpoints for incremental sync
-- Author: notion-learning-sync
-- Date: 2025-12-02

-- ============================================================================
-- Table: sync_runs
-- Purpose: Audit log of all sync operations with statistics
-- ============================================================================

CREATE TABLE IF NOT EXISTS sync_runs (
    id SERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,  -- 'flashcards', 'concepts', etc.
    sync_type TEXT NOT NULL CHECK (sync_type IN ('full', 'incremental')),

    -- Statistics
    pages_added INTEGER NOT NULL DEFAULT 0,
    pages_updated INTEGER NOT NULL DEFAULT 0,
    pages_skipped INTEGER NOT NULL DEFAULT 0,
    errors_count INTEGER NOT NULL DEFAULT 0,

    -- Timing
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_seconds NUMERIC(10, 2),

    -- Error tracking
    error_details JSONB,  -- Array of error messages

    -- Status
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),

    -- Context
    triggered_by TEXT,  -- 'cli', 'api', 'scheduler', 'manual'
    dry_run BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT sync_runs_entity_started_idx UNIQUE (entity_type, started_at)
);

-- Indexes for common queries
CREATE INDEX idx_sync_runs_entity_type ON sync_runs(entity_type);
CREATE INDEX idx_sync_runs_started_at ON sync_runs(started_at DESC);
CREATE INDEX idx_sync_runs_status ON sync_runs(status) WHERE status = 'running';

COMMENT ON TABLE sync_runs IS 'Audit log of Notion sync operations with statistics';
COMMENT ON COLUMN sync_runs.entity_type IS 'Type of Notion database synced';
COMMENT ON COLUMN sync_runs.sync_type IS 'Full sync or incremental sync';
COMMENT ON COLUMN sync_runs.error_details IS 'JSONB array of error messages (first 10)';

-- ============================================================================
-- Table: sync_checkpoints
-- Purpose: Store last successful sync timestamp per entity type
--          Enables reliable incremental sync and recovery
-- ============================================================================

CREATE TABLE IF NOT EXISTS sync_checkpoints (
    entity_type TEXT PRIMARY KEY,
    last_success_at TIMESTAMPTZ NOT NULL,
    last_sync_run_id INTEGER REFERENCES sync_runs(id),
    pages_synced_total INTEGER NOT NULL DEFAULT 0,

    -- Tracking
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for timestamp queries
CREATE INDEX idx_sync_checkpoints_last_success ON sync_checkpoints(last_success_at DESC);

COMMENT ON TABLE sync_checkpoints IS 'Last successful sync timestamp per entity type for incremental sync';
COMMENT ON COLUMN sync_checkpoints.last_success_at IS 'Timestamp of last successful sync completion';
COMMENT ON COLUMN sync_checkpoints.pages_synced_total IS 'Total pages synced across all runs';

-- ============================================================================
-- View: sync_runs_summary
-- Purpose: Quick overview of recent sync activity
-- ============================================================================

CREATE OR REPLACE VIEW sync_runs_summary AS
SELECT
    entity_type,
    COUNT(*) as total_runs,
    COUNT(*) FILTER (WHERE status = 'completed') as successful_runs,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_runs,
    SUM(pages_added) as total_added,
    SUM(pages_updated) as total_updated,
    SUM(errors_count) as total_errors,
    MAX(started_at) as last_run_at,
    AVG(duration_seconds) FILTER (WHERE status = 'completed') as avg_duration_seconds
FROM sync_runs
WHERE started_at > NOW() - INTERVAL '30 days'
GROUP BY entity_type
ORDER BY last_run_at DESC;

COMMENT ON VIEW sync_runs_summary IS 'Summary of sync activity over last 30 days per entity type';

-- ============================================================================
-- Function: update_sync_checkpoint
-- Purpose: Update checkpoint after successful sync
-- ============================================================================

CREATE OR REPLACE FUNCTION update_sync_checkpoint(
    p_entity_type TEXT,
    p_sync_run_id INTEGER,
    p_pages_synced INTEGER
) RETURNS VOID AS $$
BEGIN
    INSERT INTO sync_checkpoints (
        entity_type,
        last_success_at,
        last_sync_run_id,
        pages_synced_total,
        created_at,
        updated_at
    )
    VALUES (
        p_entity_type,
        NOW(),
        p_sync_run_id,
        p_pages_synced,
        NOW(),
        NOW()
    )
    ON CONFLICT (entity_type) DO UPDATE SET
        last_success_at = NOW(),
        last_sync_run_id = p_sync_run_id,
        pages_synced_total = sync_checkpoints.pages_synced_total + p_pages_synced,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_sync_checkpoint IS 'Upsert checkpoint after successful sync completion';

-- ============================================================================
-- Sample data for testing (optional)
-- ============================================================================

-- Uncomment to insert sample sync runs for testing
/*
INSERT INTO sync_runs (
    entity_type, sync_type, pages_added, pages_updated, pages_skipped,
    started_at, completed_at, duration_seconds, status, triggered_by
) VALUES
    ('flashcards', 'full', 150, 0, 0, NOW() - INTERVAL '2 hours', NOW() - INTERVAL '1 hour 55 minutes', 300.45, 'completed', 'cli'),
    ('concepts', 'incremental', 5, 12, 83, NOW() - INTERVAL '1 hour', NOW() - INTERVAL '55 minutes', 45.23, 'completed', 'scheduler');

-- Update checkpoints
SELECT update_sync_checkpoint('flashcards', 1, 150);
SELECT update_sync_checkpoint('concepts', 2, 17);
*/
