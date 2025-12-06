-- Migration 001: Initial Schema for notion-learning-sync
--
-- This creates the staging tables (raw from Notion) and canonical tables (clean output).
-- The staging → canonical pattern enables:
--   1. Notion remains source of truth (staging can be rebuilt)
--   2. Cleaning pipeline runs between staging and canonical
--   3. Canonical tables are the trusted output for all consumers

-- ========================================
-- STAGING TABLES (Raw from Notion)
-- Ephemeral, can be rebuilt from Notion anytime
-- ========================================

CREATE TABLE IF NOT EXISTS stg_notion_flashcards (
    notion_page_id TEXT PRIMARY KEY,
    raw_properties JSONB NOT NULL,
    raw_content JSONB,              -- Page blocks for AI enrichment
    last_synced_at TIMESTAMPTZ DEFAULT now(),
    sync_hash TEXT                  -- MD5 of properties to detect changes
);

CREATE TABLE IF NOT EXISTS stg_notion_concepts (
    notion_page_id TEXT PRIMARY KEY,
    raw_properties JSONB NOT NULL,
    parent_type TEXT,               -- 'area', 'cluster', or NULL
    parent_notion_id TEXT,
    last_synced_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stg_notion_concept_areas (
    notion_page_id TEXT PRIMARY KEY,
    raw_properties JSONB NOT NULL,
    last_synced_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stg_notion_concept_clusters (
    notion_page_id TEXT PRIMARY KEY,
    raw_properties JSONB NOT NULL,
    parent_area_notion_id TEXT,
    last_synced_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stg_notion_modules (
    notion_page_id TEXT PRIMARY KEY,
    raw_properties JSONB NOT NULL,
    last_synced_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stg_notion_tracks (
    notion_page_id TEXT PRIMARY KEY,
    raw_properties JSONB NOT NULL,
    last_synced_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stg_notion_programs (
    notion_page_id TEXT PRIMARY KEY,
    raw_properties JSONB NOT NULL,
    last_synced_at TIMESTAMPTZ DEFAULT now()
);

-- ========================================
-- CANONICAL TABLES - KNOWLEDGE HIERARCHY
-- Clean, validated output
-- ========================================

CREATE TABLE IF NOT EXISTS clean_concept_areas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notion_id TEXT UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    domain TEXT,
    display_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_clean_concept_areas_name ON clean_concept_areas(name);

CREATE TABLE IF NOT EXISTS clean_concept_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notion_id TEXT UNIQUE,
    concept_area_id UUID REFERENCES clean_concept_areas(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    description TEXT,
    exam_weight DECIMAL(5,2),
    display_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_clean_concept_clusters_area ON clean_concept_clusters(concept_area_id);

CREATE TABLE IF NOT EXISTS clean_concepts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notion_id TEXT UNIQUE,
    cluster_id UUID REFERENCES clean_concept_clusters(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    definition TEXT,
    domain TEXT,
    status TEXT DEFAULT 'to_learn',  -- to_learn, active, reviewing, mastered, stale
    dec_score DECIMAL(4,2),          -- Declarative knowledge 0-10
    proc_score DECIMAL(4,2),         -- Procedural knowledge 0-10
    app_score DECIMAL(4,2),          -- Application knowledge 0-10
    last_reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_clean_concepts_cluster ON clean_concepts(cluster_id);
CREATE INDEX IF NOT EXISTS idx_clean_concepts_status ON clean_concepts(status);

-- ========================================
-- CANONICAL TABLES - CURRICULUM STRUCTURE
-- ========================================

CREATE TABLE IF NOT EXISTS clean_programs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notion_id TEXT UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active',
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS clean_tracks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notion_id TEXT UNIQUE,
    program_id UUID REFERENCES clean_programs(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    description TEXT,
    display_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_clean_tracks_program ON clean_tracks(program_id);

CREATE TABLE IF NOT EXISTS clean_modules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notion_id TEXT UNIQUE,
    track_id UUID REFERENCES clean_tracks(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    description TEXT,
    week_order INT,
    status TEXT DEFAULT 'not_started',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_clean_modules_track ON clean_modules(track_id);
CREATE INDEX IF NOT EXISTS idx_clean_modules_week ON clean_modules(week_order);

-- ========================================
-- CANONICAL TABLES - LEARNING ATOMS
-- Clean flashcards and other content
-- ========================================

CREATE TABLE IF NOT EXISTS clean_atoms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notion_id TEXT,                 -- NULL if AI-generated
    card_id TEXT UNIQUE,            -- e.g., "NET-M1-015-DEC"

    -- Content
    atom_type TEXT NOT NULL DEFAULT 'flashcard',
    front TEXT NOT NULL,
    back TEXT,

    -- Relationships
    concept_id UUID REFERENCES clean_concepts(id) ON DELETE SET NULL,
    module_id UUID REFERENCES clean_modules(id) ON DELETE SET NULL,

    -- Quality metadata (from cleaning pipeline)
    quality_score DECIMAL(3,2),
    is_atomic BOOLEAN DEFAULT true,
    front_word_count INT,
    back_word_count INT,
    atomicity_status TEXT,          -- 'atomic', 'verbose', 'needs_split'

    -- Review status
    needs_review BOOLEAN DEFAULT false,
    rewrite_count INT DEFAULT 0,
    last_rewrite_at TIMESTAMPTZ,

    -- Anki sync
    anki_note_id BIGINT,
    anki_card_id BIGINT,
    anki_deck TEXT,
    anki_exported_at TIMESTAMPTZ,

    -- Anki review stats (pulled back)
    anki_ease_factor DECIMAL(4,3),
    anki_interval_days INT,
    anki_review_count INT DEFAULT 0,
    anki_lapses INT DEFAULT 0,
    anki_last_review TIMESTAMPTZ,
    anki_due_date DATE,

    -- FSRS metrics (computed from Anki stats)
    stability_days DECIMAL(8,2),
    retrievability DECIMAL(5,4),

    -- Source tracking
    source TEXT DEFAULT 'notion',   -- 'notion', 'ai_batch', 'manual'
    batch_id TEXT,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_clean_atoms_notion ON clean_atoms(notion_id);
CREATE INDEX IF NOT EXISTS idx_clean_atoms_concept ON clean_atoms(concept_id);
CREATE INDEX IF NOT EXISTS idx_clean_atoms_module ON clean_atoms(module_id);
CREATE INDEX IF NOT EXISTS idx_clean_atoms_needs_review ON clean_atoms(needs_review) WHERE needs_review = true;
CREATE INDEX IF NOT EXISTS idx_clean_atoms_anki ON clean_atoms(anki_note_id) WHERE anki_note_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_clean_atoms_due ON clean_atoms(anki_due_date) WHERE anki_due_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_clean_atoms_source ON clean_atoms(source);

-- ========================================
-- REVIEW QUEUE
-- AI-generated content pending approval
-- ========================================

CREATE TABLE IF NOT EXISTS review_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Content
    atom_type TEXT NOT NULL DEFAULT 'flashcard',
    front TEXT NOT NULL,
    back TEXT,
    concept_id UUID REFERENCES clean_concepts(id) ON DELETE SET NULL,
    module_id UUID REFERENCES clean_modules(id) ON DELETE SET NULL,

    -- Original (before rewrite)
    original_front TEXT,
    original_back TEXT,
    original_atom_id UUID REFERENCES clean_atoms(id) ON DELETE SET NULL,

    -- Review workflow
    status TEXT DEFAULT 'pending',  -- 'pending', 'approved', 'rejected', 'edited'
    source TEXT NOT NULL,           -- 'notion_ai', 'vertex', 'gemini', 'duplicate_merge'
    batch_id TEXT,

    -- Quality metrics
    quality_score DECIMAL(3,2),
    ai_confidence DECIMAL(3,2),
    rewrite_reason TEXT,

    -- After approval
    approved_at TIMESTAMPTZ,
    approved_atom_id UUID REFERENCES clean_atoms(id) ON DELETE SET NULL,
    reviewer_notes TEXT,

    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_review_queue_status ON review_queue(status);
CREATE INDEX IF NOT EXISTS idx_review_queue_batch ON review_queue(batch_id);
CREATE INDEX IF NOT EXISTS idx_review_queue_pending ON review_queue(created_at) WHERE status = 'pending';

-- ========================================
-- SYNC & AUDIT LOGS
-- ========================================

CREATE TABLE IF NOT EXISTS sync_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sync_type TEXT NOT NULL,        -- 'notion_full', 'notion_incremental', 'anki_push', 'anki_pull'
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT DEFAULT 'running',  -- 'running', 'completed', 'failed'
    items_processed INT DEFAULT 0,
    items_added INT DEFAULT 0,
    items_updated INT DEFAULT 0,
    items_removed INT DEFAULT 0,
    error_message TEXT,
    details JSONB
);

CREATE INDEX IF NOT EXISTS idx_sync_log_type ON sync_log(sync_type);
CREATE INDEX IF NOT EXISTS idx_sync_log_status ON sync_log(status);
CREATE INDEX IF NOT EXISTS idx_sync_log_started ON sync_log(started_at DESC);

CREATE TABLE IF NOT EXISTS cleaning_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    atom_id UUID REFERENCES clean_atoms(id) ON DELETE CASCADE,
    operation TEXT NOT NULL,        -- 'atomicity_check', 'prefix_normalize', 'ai_rewrite', 'duplicate_merge'
    old_value JSONB,
    new_value JSONB,
    performed_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cleaning_log_atom ON cleaning_log(atom_id);
CREATE INDEX IF NOT EXISTS idx_cleaning_log_operation ON cleaning_log(operation);

-- ========================================
-- VIEWS FOR CONVENIENCE
-- ========================================

-- Due atoms (for study sessions)
CREATE OR REPLACE VIEW v_due_atoms AS
SELECT
    a.*,
    c.name as concept_name,
    m.name as module_name,
    cl.name as cluster_name,
    ca.name as area_name
FROM clean_atoms a
LEFT JOIN clean_concepts c ON a.concept_id = c.id
LEFT JOIN clean_modules m ON a.module_id = m.id
LEFT JOIN clean_concept_clusters cl ON c.cluster_id = cl.id
LEFT JOIN clean_concept_areas ca ON cl.concept_area_id = ca.id
WHERE a.anki_due_date <= CURRENT_DATE
  AND a.is_atomic = true
  AND a.needs_review = false;

-- Atom statistics by concept
CREATE OR REPLACE VIEW v_concept_atom_stats AS
SELECT
    c.id as concept_id,
    c.name as concept_name,
    c.status,
    COUNT(a.id) as total_atoms,
    COUNT(a.id) FILTER (WHERE a.is_atomic = true) as atomic_count,
    COUNT(a.id) FILTER (WHERE a.needs_review = true) as needs_review_count,
    COUNT(a.id) FILTER (WHERE a.anki_note_id IS NOT NULL) as in_anki_count,
    AVG(a.anki_ease_factor) as avg_ease,
    AVG(a.anki_interval_days) as avg_interval
FROM clean_concepts c
LEFT JOIN clean_atoms a ON a.concept_id = c.id
GROUP BY c.id, c.name, c.status;

-- Review queue summary
CREATE OR REPLACE VIEW v_review_queue_summary AS
SELECT
    source,
    status,
    COUNT(*) as count,
    MIN(created_at) as oldest,
    MAX(created_at) as newest
FROM review_queue
GROUP BY source, status
ORDER BY source, status;
