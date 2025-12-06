-- Migration 006: CCNA Content Generation Tracking
-- Supports Phase 4: High-Quality CCNA Content Generation
--
-- Tables:
--   - ccna_generation_jobs: Track generation jobs and status
--   - ccna_module_coverage: Track content coverage per module
--   - anki_learning_state_backup: Backup learning state before migration
--   - anki_card_migrations: Track card replacements for learning state transfer

-- ============================================================================
-- CCNA Generation Jobs
-- ============================================================================
-- Track the status and progress of content generation jobs

CREATE TABLE IF NOT EXISTS ccna_generation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id VARCHAR(20) NOT NULL,                    -- NET-M1, NET-M2, etc.
    job_type VARCHAR(30) NOT NULL DEFAULT 'full',      -- full, incremental, qa_only
    status VARCHAR(20) NOT NULL DEFAULT 'pending',     -- pending, running, completed, failed, cancelled

    -- Progress tracking
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    sections_total INT DEFAULT 0,
    sections_processed INT DEFAULT 0,

    -- Generation results
    atoms_generated INT DEFAULT 0,
    atoms_passed_qa INT DEFAULT 0,                     -- Grade B or better
    atoms_flagged INT DEFAULT 0,                       -- Grade C or D, needs review
    atoms_rejected INT DEFAULT 0,                      -- Grade F, regenerate

    -- Atom type breakdown
    flashcards_generated INT DEFAULT 0,
    mcq_generated INT DEFAULT 0,
    cloze_generated INT DEFAULT 0,
    parsons_generated INT DEFAULT 0,
    other_types_generated INT DEFAULT 0,

    -- Quality metrics
    avg_quality_score DECIMAL(5, 2),                   -- Average quality score (0-100)
    grade_distribution JSONB,                          -- {"A": 10, "B": 20, ...}

    -- Error handling
    error_message TEXT,
    retry_count INT DEFAULT 0,

    -- Metadata
    config_snapshot JSONB,                             -- Settings used for this job
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_ccna_jobs_module_status
    ON ccna_generation_jobs(module_id, status);
CREATE INDEX IF NOT EXISTS idx_ccna_jobs_status
    ON ccna_generation_jobs(status);
CREATE INDEX IF NOT EXISTS idx_ccna_jobs_created
    ON ccna_generation_jobs(created_at DESC);


-- ============================================================================
-- CCNA Module Coverage
-- ============================================================================
-- Track content coverage and quality metrics per module

CREATE TABLE IF NOT EXISTS ccna_module_coverage (
    module_id VARCHAR(20) PRIMARY KEY,                 -- NET-M1, NET-M2, etc.
    module_number INT NOT NULL,
    title VARCHAR(200),

    -- Source content metrics
    total_lines INT NOT NULL DEFAULT 0,
    total_sections INT NOT NULL DEFAULT 0,
    total_subsections INT NOT NULL DEFAULT 0,
    total_commands INT NOT NULL DEFAULT 0,
    total_tables INT NOT NULL DEFAULT 0,
    total_key_terms INT NOT NULL DEFAULT 0,

    -- Estimated vs actual atoms
    estimated_atoms INT NOT NULL DEFAULT 0,
    actual_atoms INT NOT NULL DEFAULT 0,
    coverage_percentage DECIMAL(5, 2),                 -- (actual/estimated) * 100

    -- Quality breakdown by grade
    grade_a_count INT DEFAULT 0,
    grade_b_count INT DEFAULT 0,
    grade_c_count INT DEFAULT 0,
    grade_d_count INT DEFAULT 0,
    grade_f_count INT DEFAULT 0,

    -- Atom type distribution
    flashcard_count INT DEFAULT 0,
    mcq_count INT DEFAULT 0,
    cloze_count INT DEFAULT 0,
    parsons_count INT DEFAULT 0,
    true_false_count INT DEFAULT 0,
    matching_count INT DEFAULT 0,
    ranking_count INT DEFAULT 0,
    short_answer_count INT DEFAULT 0,
    other_count INT DEFAULT 0,

    -- Quality metrics
    avg_quality_score DECIMAL(5, 2),
    hallucination_rate DECIMAL(5, 4),                  -- Fraction of rejected atoms

    -- Status
    status VARCHAR(20) DEFAULT 'not_started',          -- not_started, in_progress, completed, needs_review
    last_generation_job_id UUID REFERENCES ccna_generation_jobs(id),

    -- Timestamps
    first_analyzed_at TIMESTAMPTZ,
    last_analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    last_generated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================================
-- Anki Learning State Backup
-- ============================================================================
-- Backup learning state before card migrations to enable state transfer

CREATE TABLE IF NOT EXISTS anki_learning_state_backup (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Card identification
    card_id VARCHAR(100) NOT NULL,                     -- Original card_id (e.g., NET-M1-001)
    anki_nid BIGINT,                                   -- Anki note ID
    anki_cid BIGINT,                                   -- Anki card ID

    -- FSRS state
    stability DECIMAL(10, 4),                          -- S value in days
    difficulty DECIMAL(5, 4),                          -- D value (0-1)

    -- Anki scheduling state
    due_date DATE,
    interval_days INT,
    ease_factor DECIMAL(6, 4),                         -- e.g., 2.5000
    queue_type INT,                                    -- 0=new, 1=learn, 2=review, 3=day learn
    card_type INT,                                     -- 0=new, 1=learn, 2=review, 3=relearn

    -- Learning history
    total_reviews INT DEFAULT 0,
    total_lapses INT DEFAULT 0,
    last_review_date TIMESTAMPTZ,
    first_review_date TIMESTAMPTZ,

    -- Content for matching
    front_text TEXT,
    back_text TEXT,
    tags TEXT[],

    -- Quality grade at backup time
    quality_grade CHAR(1),                             -- A, B, C, D, F

    -- Backup metadata
    backup_reason VARCHAR(50),                         -- migration, qa_refresh, manual
    backed_up_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for matching and lookups
CREATE INDEX IF NOT EXISTS idx_anki_backup_card_id
    ON anki_learning_state_backup(card_id);
CREATE INDEX IF NOT EXISTS idx_anki_backup_backed_up
    ON anki_learning_state_backup(backed_up_at DESC);
CREATE INDEX IF NOT EXISTS idx_anki_backup_reason
    ON anki_learning_state_backup(backup_reason);


-- ============================================================================
-- Anki Card Migrations
-- ============================================================================
-- Track card replacements and learning state transfers

CREATE TABLE IF NOT EXISTS anki_card_migrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source and target cards
    old_card_id VARCHAR(100) NOT NULL,                 -- Card being replaced
    new_card_id VARCHAR(100) NOT NULL,                 -- Replacement card

    -- Matching confidence
    similarity_score DECIMAL(5, 4),                    -- Semantic similarity (0-1)
    match_type VARCHAR(20),                            -- exact, semantic, manual

    -- State transfer
    state_transferred BOOLEAN DEFAULT FALSE,
    transfer_attempted_at TIMESTAMPTZ,
    transfer_completed_at TIMESTAMPTZ,
    transfer_error TEXT,

    -- Old state snapshot
    old_stability DECIMAL(10, 4),
    old_difficulty DECIMAL(5, 4),
    old_interval_days INT,
    old_reviews INT,
    old_lapses INT,

    -- New state after transfer
    new_stability DECIMAL(10, 4),
    new_difficulty DECIMAL(5, 4),

    -- Metadata
    migration_job_id UUID REFERENCES ccna_generation_jobs(id),
    migrated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    UNIQUE(old_card_id, new_card_id)
);

-- Indexes for lookups
CREATE INDEX IF NOT EXISTS idx_card_migrations_old
    ON anki_card_migrations(old_card_id);
CREATE INDEX IF NOT EXISTS idx_card_migrations_new
    ON anki_card_migrations(new_card_id);
CREATE INDEX IF NOT EXISTS idx_card_migrations_job
    ON anki_card_migrations(migration_job_id);
CREATE INDEX IF NOT EXISTS idx_card_migrations_transferred
    ON anki_card_migrations(state_transferred);


-- ============================================================================
-- Section-Level Tracking (Optional granular tracking)
-- ============================================================================
-- Track generation status at section level for detailed progress

CREATE TABLE IF NOT EXISTS ccna_section_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Section identification
    module_id VARCHAR(20) NOT NULL,
    section_id VARCHAR(50) NOT NULL,                   -- NET-M1-S1, NET-M1-S1-1, etc.
    section_title VARCHAR(200),
    section_level INT,                                 -- 2, 3, or 4
    parent_section_id VARCHAR(50),

    -- Content metrics
    content_length INT,
    command_count INT DEFAULT 0,
    table_count INT DEFAULT 0,
    key_term_count INT DEFAULT 0,
    estimated_atoms INT DEFAULT 0,

    -- Generation status
    status VARCHAR(20) DEFAULT 'pending',              -- pending, processing, completed, failed
    atoms_generated INT DEFAULT 0,
    atoms_approved INT DEFAULT 0,

    -- Last generation
    last_job_id UUID REFERENCES ccna_generation_jobs(id),
    last_generated_at TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(module_id, section_id)
);

CREATE INDEX IF NOT EXISTS idx_section_status_module
    ON ccna_section_status(module_id);
CREATE INDEX IF NOT EXISTS idx_section_status_status
    ON ccna_section_status(status);


-- ============================================================================
-- Generated Atoms (Extended tracking for QA)
-- ============================================================================
-- Extended tracking for generated atoms with QA metadata

CREATE TABLE IF NOT EXISTS ccna_generated_atoms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Atom identification
    card_id VARCHAR(100) NOT NULL UNIQUE,              -- NET-M1-S1-FC-001
    atom_type VARCHAR(30) NOT NULL,                    -- flashcard, mcq, cloze, parsons, etc.

    -- Source tracking
    module_id VARCHAR(20) NOT NULL,
    section_id VARCHAR(50) NOT NULL,
    generation_job_id UUID REFERENCES ccna_generation_jobs(id),

    -- Content
    front TEXT,                                        -- Question/prompt
    back TEXT,                                         -- Answer
    content_json JSONB,                                -- Full content for non-flashcard types
    knowledge_type VARCHAR(20),                        -- factual, conceptual, procedural

    -- Quality grading
    quality_grade CHAR(1),                             -- A, B, C, D, F
    quality_score DECIMAL(5, 2),                       -- 0-100
    quality_details JSONB,                             -- Breakdown of quality factors

    -- QA flags
    is_atomic BOOLEAN DEFAULT TRUE,
    is_accurate BOOLEAN DEFAULT TRUE,                  -- Verified against source
    is_clear BOOLEAN DEFAULT TRUE,
    needs_review BOOLEAN DEFAULT FALSE,
    was_regenerated BOOLEAN DEFAULT FALSE,
    regeneration_count INT DEFAULT 0,

    -- Tags and categorization
    tags TEXT[],
    bloom_level VARCHAR(20),                           -- remember, understand, apply, etc.

    -- Timestamps
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    last_qa_at TIMESTAMPTZ,

    -- Relationships
    replaces_card_id VARCHAR(100),                     -- If this replaces an existing card
    migration_id UUID REFERENCES anki_card_migrations(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_generated_atoms_module
    ON ccna_generated_atoms(module_id);
CREATE INDEX IF NOT EXISTS idx_generated_atoms_section
    ON ccna_generated_atoms(section_id);
CREATE INDEX IF NOT EXISTS idx_generated_atoms_type
    ON ccna_generated_atoms(atom_type);
CREATE INDEX IF NOT EXISTS idx_generated_atoms_grade
    ON ccna_generated_atoms(quality_grade);
CREATE INDEX IF NOT EXISTS idx_generated_atoms_needs_review
    ON ccna_generated_atoms(needs_review) WHERE needs_review = TRUE;


-- ============================================================================
-- Views
-- ============================================================================

-- Module quality summary view
CREATE OR REPLACE VIEW ccna_module_quality_summary AS
SELECT
    mc.module_id,
    mc.title,
    mc.total_sections,
    mc.estimated_atoms,
    mc.actual_atoms,
    mc.coverage_percentage,
    mc.grade_a_count,
    mc.grade_b_count,
    mc.grade_c_count,
    mc.grade_d_count,
    mc.grade_f_count,
    mc.avg_quality_score,
    CASE
        WHEN mc.actual_atoms = 0 THEN 0
        ELSE ROUND(
            (mc.grade_a_count + mc.grade_b_count)::DECIMAL / mc.actual_atoms * 100,
            2
        )
    END AS good_quality_percentage,
    mc.status,
    mc.last_generated_at
FROM ccna_module_coverage mc
ORDER BY mc.module_id;


-- Generation job summary view
CREATE OR REPLACE VIEW ccna_job_summary AS
SELECT
    j.id,
    j.module_id,
    j.job_type,
    j.status,
    j.started_at,
    j.completed_at,
    EXTRACT(EPOCH FROM (j.completed_at - j.started_at))::INT AS duration_seconds,
    j.sections_total,
    j.sections_processed,
    j.atoms_generated,
    j.atoms_passed_qa,
    j.atoms_flagged,
    j.atoms_rejected,
    j.avg_quality_score,
    CASE
        WHEN j.atoms_generated = 0 THEN 0
        ELSE ROUND(
            j.atoms_passed_qa::DECIMAL / j.atoms_generated * 100,
            2
        )
    END AS pass_rate,
    j.error_message
FROM ccna_generation_jobs j
ORDER BY j.created_at DESC;


-- ============================================================================
-- Functions
-- ============================================================================

-- Function to update module coverage after generation
CREATE OR REPLACE FUNCTION update_module_coverage_stats(p_module_id VARCHAR(20))
RETURNS VOID AS $$
DECLARE
    v_grade_counts RECORD;
    v_type_counts RECORD;
    v_total INT;
    v_avg_score DECIMAL(5,2);
BEGIN
    -- Count atoms by grade
    SELECT
        COUNT(*) FILTER (WHERE quality_grade = 'A') AS grade_a,
        COUNT(*) FILTER (WHERE quality_grade = 'B') AS grade_b,
        COUNT(*) FILTER (WHERE quality_grade = 'C') AS grade_c,
        COUNT(*) FILTER (WHERE quality_grade = 'D') AS grade_d,
        COUNT(*) FILTER (WHERE quality_grade = 'F') AS grade_f,
        COUNT(*) AS total,
        AVG(quality_score) AS avg_score
    INTO v_grade_counts
    FROM ccna_generated_atoms
    WHERE module_id = p_module_id;

    -- Count atoms by type
    SELECT
        COUNT(*) FILTER (WHERE atom_type = 'flashcard') AS flashcard,
        COUNT(*) FILTER (WHERE atom_type = 'mcq') AS mcq,
        COUNT(*) FILTER (WHERE atom_type = 'cloze') AS cloze,
        COUNT(*) FILTER (WHERE atom_type = 'parsons') AS parsons,
        COUNT(*) FILTER (WHERE atom_type = 'true_false') AS true_false,
        COUNT(*) FILTER (WHERE atom_type = 'matching') AS matching,
        COUNT(*) FILTER (WHERE atom_type = 'ranking') AS ranking,
        COUNT(*) FILTER (WHERE atom_type = 'short_answer') AS short_answer,
        COUNT(*) FILTER (WHERE atom_type NOT IN ('flashcard', 'mcq', 'cloze', 'parsons', 'true_false', 'matching', 'ranking', 'short_answer')) AS other_type
    INTO v_type_counts
    FROM ccna_generated_atoms
    WHERE module_id = p_module_id;

    -- Update coverage table
    UPDATE ccna_module_coverage
    SET
        actual_atoms = COALESCE(v_grade_counts.total, 0),
        coverage_percentage = CASE
            WHEN estimated_atoms > 0
            THEN ROUND(COALESCE(v_grade_counts.total, 0)::DECIMAL / estimated_atoms * 100, 2)
            ELSE 0
        END,
        grade_a_count = COALESCE(v_grade_counts.grade_a, 0),
        grade_b_count = COALESCE(v_grade_counts.grade_b, 0),
        grade_c_count = COALESCE(v_grade_counts.grade_c, 0),
        grade_d_count = COALESCE(v_grade_counts.grade_d, 0),
        grade_f_count = COALESCE(v_grade_counts.grade_f, 0),
        flashcard_count = COALESCE(v_type_counts.flashcard, 0),
        mcq_count = COALESCE(v_type_counts.mcq, 0),
        cloze_count = COALESCE(v_type_counts.cloze, 0),
        parsons_count = COALESCE(v_type_counts.parsons, 0),
        true_false_count = COALESCE(v_type_counts.true_false, 0),
        matching_count = COALESCE(v_type_counts.matching, 0),
        ranking_count = COALESCE(v_type_counts.ranking, 0),
        short_answer_count = COALESCE(v_type_counts.short_answer, 0),
        other_count = COALESCE(v_type_counts.other_type, 0),
        avg_quality_score = v_grade_counts.avg_score,
        hallucination_rate = CASE
            WHEN v_grade_counts.total > 0
            THEN ROUND(v_grade_counts.grade_f::DECIMAL / v_grade_counts.total, 4)
            ELSE 0
        END,
        updated_at = NOW()
    WHERE module_id = p_module_id;
END;
$$ LANGUAGE plpgsql;


-- Function to get migration candidates (good cards to preserve)
CREATE OR REPLACE FUNCTION get_preservation_candidates(p_module_id VARCHAR(20))
RETURNS TABLE (
    card_id VARCHAR(100),
    quality_grade CHAR(1),
    stability DECIMAL(10,4),
    total_reviews INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        b.card_id,
        b.quality_grade,
        b.stability,
        b.total_reviews
    FROM anki_learning_state_backup b
    WHERE b.card_id LIKE p_module_id || '%'
      AND b.quality_grade IN ('A', 'B')
      AND b.total_reviews > 0
    ORDER BY b.total_reviews DESC, b.stability DESC;
END;
$$ LANGUAGE plpgsql;
