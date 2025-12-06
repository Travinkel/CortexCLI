-- Migration 008: CCNA Study Path and Mastery Tracking
-- Supports Phase 4.7: CLI Study Path with Adaptive Remediation
--
-- Tables:
--   - ccna_sections: Hierarchical section structure (103 main + 469 subsections)
--   - ccna_section_mastery: Mastery tracking per section per user
--
-- Views:
--   - v_module_mastery: Aggregated mastery by module
--   - v_sections_needing_remediation: Sections below mastery threshold
--   - v_daily_study_queue: Today's recommended study items

-- ============================================================================
-- CCNA Sections (Hierarchical Structure)
-- ============================================================================
-- Stores all 572 sections (17 modules × ~33 sections average)
-- Supports X.Y (main) and X.Y.Z (sub) formats

CREATE TABLE IF NOT EXISTS ccna_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Section identification
    module_number INTEGER NOT NULL,                      -- 1-17
    section_id TEXT NOT NULL UNIQUE,                     -- "1.2", "1.4.1", "10.1.3"
    title TEXT NOT NULL,

    -- Hierarchy
    level INTEGER NOT NULL,                              -- 2=main (X.Y), 3=sub (X.Y.Z)
    parent_section_id TEXT,                              -- NULL for main sections

    -- Content metrics (populated from parser)
    atom_count INTEGER DEFAULT 0,
    command_count INTEGER DEFAULT 0,
    key_term_count INTEGER DEFAULT 0,
    table_count INTEGER DEFAULT 0,
    word_count INTEGER DEFAULT 0,

    -- Display ordering
    display_order INTEGER,                               -- For correct UI ordering

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Self-referential FK (added after table exists)
    CONSTRAINT fk_parent_section
        FOREIGN KEY (parent_section_id)
        REFERENCES ccna_sections(section_id)
        ON DELETE SET NULL
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_sections_module ON ccna_sections(module_number);
CREATE INDEX IF NOT EXISTS idx_sections_level ON ccna_sections(level);
CREATE INDEX IF NOT EXISTS idx_sections_parent ON ccna_sections(parent_section_id);
CREATE INDEX IF NOT EXISTS idx_sections_order ON ccna_sections(display_order);


-- ============================================================================
-- Section Mastery Tracking
-- ============================================================================
-- Tracks mastery per section per user (default user for now)
-- Updated on each Anki sync

CREATE TABLE IF NOT EXISTS ccna_section_mastery (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Section reference
    section_id TEXT NOT NULL REFERENCES ccna_sections(section_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL DEFAULT 'default',             -- For future multi-user

    -- Mastery metrics
    mastery_score DECIMAL(5, 2),                         -- 0-100 (aggregated)
    avg_retrievability DECIMAL(5, 4),                    -- 0-1 from FSRS
    avg_stability_days DECIMAL(8, 2),                    -- Average stability in days
    avg_lapses DECIMAL(5, 2),                            -- Average lapses per atom

    -- Atom status counts
    atoms_total INTEGER DEFAULT 0,
    atoms_mastered INTEGER DEFAULT 0,                    -- 90%+ retrievability, <2 lapses
    atoms_learning INTEGER DEFAULT 0,                    -- 50-89% retrievability
    atoms_struggling INTEGER DEFAULT 0,                  -- <50% retrievability or >3 lapses
    atoms_new INTEGER DEFAULT 0,                         -- Never reviewed

    -- Quiz performance (for combined signal)
    mcq_attempts INTEGER DEFAULT 0,
    mcq_correct INTEGER DEFAULT 0,
    mcq_score DECIMAL(5, 2),                             -- Percentage correct
    last_mcq_date TIMESTAMPTZ,

    -- Review history
    total_reviews INTEGER DEFAULT 0,
    reviews_last_7_days INTEGER DEFAULT 0,
    reviews_last_30_days INTEGER DEFAULT 0,
    last_review_date TIMESTAMPTZ,
    first_review_date TIMESTAMPTZ,

    -- Remediation status
    needs_remediation BOOLEAN DEFAULT FALSE,
    remediation_reason TEXT,                             -- 'low_retrievability', 'high_lapses', 'low_mcq', 'combined'
    remediation_priority INTEGER DEFAULT 0,              -- Higher = more urgent
    last_remediation_date TIMESTAMPTZ,

    -- Study path status
    is_started BOOLEAN DEFAULT FALSE,
    is_completed BOOLEAN DEFAULT FALSE,                  -- Mastery threshold reached
    completed_at TIMESTAMPTZ,

    -- Timestamps
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure one record per section per user
    UNIQUE(section_id, user_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mastery_section ON ccna_section_mastery(section_id);
CREATE INDEX IF NOT EXISTS idx_mastery_user ON ccna_section_mastery(user_id);
CREATE INDEX IF NOT EXISTS idx_mastery_remediation ON ccna_section_mastery(needs_remediation)
    WHERE needs_remediation = TRUE;
CREATE INDEX IF NOT EXISTS idx_mastery_score ON ccna_section_mastery(mastery_score);
CREATE INDEX IF NOT EXISTS idx_mastery_priority ON ccna_section_mastery(remediation_priority DESC);


-- ============================================================================
-- Link atoms to sections
-- ============================================================================
-- Add section reference to clean_atoms table

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'clean_atoms' AND column_name = 'ccna_section_id'
    ) THEN
        ALTER TABLE clean_atoms ADD COLUMN ccna_section_id TEXT;
    END IF;
END $$;

-- Index for section-based queries
CREATE INDEX IF NOT EXISTS idx_atoms_ccna_section ON clean_atoms(ccna_section_id)
    WHERE ccna_section_id IS NOT NULL;


-- ============================================================================
-- Study Sessions Tracking
-- ============================================================================
-- Track daily study sessions for progress visualization

CREATE TABLE IF NOT EXISTS ccna_study_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id TEXT NOT NULL DEFAULT 'default',
    session_date DATE NOT NULL DEFAULT CURRENT_DATE,

    -- Session metrics
    duration_minutes INTEGER DEFAULT 0,
    cards_reviewed INTEGER DEFAULT 0,
    cards_new INTEGER DEFAULT 0,
    cards_remediation INTEGER DEFAULT 0,

    -- Performance
    correct_count INTEGER DEFAULT 0,
    incorrect_count INTEGER DEFAULT 0,

    -- Sections touched
    sections_practiced TEXT[],                           -- Array of section_ids

    -- Timestamps
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, session_date)
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_date ON ccna_study_sessions(user_id, session_date DESC);


-- ============================================================================
-- Views
-- ============================================================================

-- Module-level mastery summary
CREATE OR REPLACE VIEW v_module_mastery AS
SELECT
    s.module_number,
    COUNT(DISTINCT s.section_id) AS total_sections,
    COUNT(DISTINCT CASE WHEN s.level = 2 THEN s.section_id END) AS main_sections,
    COUNT(DISTINCT CASE WHEN s.level = 3 THEN s.section_id END) AS subsections,
    COALESCE(AVG(m.mastery_score), 0) AS avg_mastery,
    COALESCE(SUM(m.atoms_total), 0) AS total_atoms,
    COALESCE(SUM(m.atoms_mastered), 0) AS atoms_mastered,
    COALESCE(SUM(m.atoms_learning), 0) AS atoms_learning,
    COALESCE(SUM(m.atoms_struggling), 0) AS atoms_struggling,
    COALESCE(SUM(m.atoms_new), 0) AS atoms_new,
    COUNT(CASE WHEN m.needs_remediation THEN 1 END) AS sections_needing_remediation,
    COUNT(CASE WHEN m.is_completed THEN 1 END) AS sections_completed,
    CASE
        WHEN COUNT(DISTINCT s.section_id) > 0
        THEN ROUND(
            COUNT(CASE WHEN m.is_completed THEN 1 END)::DECIMAL /
            COUNT(DISTINCT CASE WHEN s.level = 2 THEN s.section_id END) * 100,
            1
        )
        ELSE 0
    END AS completion_percentage
FROM ccna_sections s
LEFT JOIN ccna_section_mastery m ON s.section_id = m.section_id AND m.user_id = 'default'
GROUP BY s.module_number
ORDER BY s.module_number;


-- Sections needing remediation
CREATE OR REPLACE VIEW v_sections_needing_remediation AS
SELECT
    s.module_number,
    s.section_id,
    s.title,
    s.level,
    m.mastery_score,
    m.avg_retrievability,
    m.avg_lapses,
    m.mcq_score,
    m.atoms_struggling,
    m.remediation_reason,
    m.remediation_priority,
    m.last_review_date
FROM ccna_sections s
JOIN ccna_section_mastery m ON s.section_id = m.section_id
WHERE m.needs_remediation = TRUE
ORDER BY m.remediation_priority DESC, m.mastery_score ASC;


-- Daily study queue composition
CREATE OR REPLACE VIEW v_study_queue_summary AS
SELECT
    m.user_id,
    COUNT(CASE WHEN m.atoms_new > 0 THEN 1 END) AS sections_with_new,
    SUM(m.atoms_new) AS total_new_atoms,
    COUNT(CASE WHEN m.needs_remediation THEN 1 END) AS sections_needing_remediation,
    SUM(m.atoms_struggling) AS total_struggling_atoms,
    SUM(m.atoms_learning) AS total_learning_atoms,
    AVG(m.mastery_score) AS overall_mastery
FROM ccna_section_mastery m
GROUP BY m.user_id;


-- ============================================================================
-- Functions
-- ============================================================================

-- Calculate mastery score from atom metrics
CREATE OR REPLACE FUNCTION calculate_mastery_score(
    p_avg_retrievability DECIMAL,
    p_avg_lapses DECIMAL,
    p_mcq_score DECIMAL
) RETURNS DECIMAL AS $$
DECLARE
    v_score DECIMAL;
BEGIN
    -- Weighted formula: 40% retrievability + 25% lapse rate + 25% MCQ + 10% buffer
    -- Lapse rate converted: (1 - min(avg_lapses/5, 1)) * 100
    v_score := (
        COALESCE(p_avg_retrievability, 0.5) * 100 * 0.40 +
        (1 - LEAST(COALESCE(p_avg_lapses, 0) / 5.0, 1)) * 100 * 0.25 +
        COALESCE(p_mcq_score, 50) * 0.25 +
        10  -- Base buffer
    );

    RETURN LEAST(GREATEST(v_score, 0), 100);
END;
$$ LANGUAGE plpgsql IMMUTABLE;


-- Determine if section needs remediation
CREATE OR REPLACE FUNCTION check_remediation_needed(
    p_avg_retrievability DECIMAL,
    p_avg_lapses DECIMAL,
    p_mcq_score DECIMAL,
    OUT needs_remediation BOOLEAN,
    OUT reason TEXT,
    OUT priority INTEGER
) AS $$
BEGIN
    needs_remediation := FALSE;
    reason := NULL;
    priority := 0;

    -- Check retrievability (threshold: 70%)
    IF COALESCE(p_avg_retrievability, 1) < 0.70 THEN
        needs_remediation := TRUE;
        reason := 'low_retrievability';
        priority := priority + 3;
    END IF;

    -- Check lapses (threshold: 3 average)
    IF COALESCE(p_avg_lapses, 0) > 3 THEN
        needs_remediation := TRUE;
        IF reason IS NOT NULL THEN
            reason := 'combined';
            priority := priority + 3;
        ELSE
            reason := 'high_lapses';
            priority := priority + 2;
        END IF;
    END IF;

    -- Check MCQ score (threshold: 80%)
    IF COALESCE(p_mcq_score, 100) < 80 THEN
        needs_remediation := TRUE;
        IF reason IS NOT NULL THEN
            reason := 'combined';
            priority := priority + 2;
        ELSE
            reason := 'low_mcq';
            priority := priority + 1;
        END IF;
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;


-- Update section mastery from atom stats
CREATE OR REPLACE FUNCTION update_section_mastery(
    p_section_id TEXT,
    p_user_id TEXT DEFAULT 'default'
) RETURNS VOID AS $$
DECLARE
    v_stats RECORD;
    v_remediation RECORD;
    v_mastery_score DECIMAL;
BEGIN
    -- Calculate aggregate stats from atoms
    SELECT
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE retrievability >= 0.90 AND anki_lapses < 2) AS mastered,
        COUNT(*) FILTER (WHERE retrievability >= 0.50 AND retrievability < 0.90) AS learning,
        COUNT(*) FILTER (WHERE retrievability < 0.50 OR anki_lapses >= 3) AS struggling,
        COUNT(*) FILTER (WHERE anki_review_count = 0 OR anki_review_count IS NULL) AS new_atoms,
        AVG(retrievability) AS avg_ret,
        AVG(stability_days) AS avg_stab,
        AVG(anki_lapses) AS avg_lapses,
        SUM(anki_review_count) AS total_reviews,
        MAX(anki_last_review) AS last_review
    INTO v_stats
    FROM clean_atoms
    WHERE ccna_section_id = p_section_id;

    -- Calculate mastery score
    v_mastery_score := calculate_mastery_score(
        v_stats.avg_ret,
        v_stats.avg_lapses,
        NULL  -- MCQ score handled separately
    );

    -- Check remediation status
    SELECT * INTO v_remediation FROM check_remediation_needed(
        v_stats.avg_ret,
        v_stats.avg_lapses,
        NULL
    );

    -- Upsert mastery record
    INSERT INTO ccna_section_mastery (
        section_id, user_id, mastery_score, avg_retrievability, avg_stability_days,
        avg_lapses, atoms_total, atoms_mastered, atoms_learning, atoms_struggling,
        atoms_new, total_reviews, last_review_date, needs_remediation,
        remediation_reason, remediation_priority, is_started, is_completed, updated_at
    ) VALUES (
        p_section_id, p_user_id, v_mastery_score, v_stats.avg_ret, v_stats.avg_stab,
        v_stats.avg_lapses, v_stats.total, v_stats.mastered, v_stats.learning,
        v_stats.struggling, v_stats.new_atoms, v_stats.total_reviews, v_stats.last_review,
        v_remediation.needs_remediation, v_remediation.reason, v_remediation.priority,
        v_stats.total_reviews > 0,
        v_mastery_score >= 90 AND COALESCE(v_stats.avg_lapses, 0) < 2,
        NOW()
    )
    ON CONFLICT (section_id, user_id) DO UPDATE SET
        mastery_score = EXCLUDED.mastery_score,
        avg_retrievability = EXCLUDED.avg_retrievability,
        avg_stability_days = EXCLUDED.avg_stability_days,
        avg_lapses = EXCLUDED.avg_lapses,
        atoms_total = EXCLUDED.atoms_total,
        atoms_mastered = EXCLUDED.atoms_mastered,
        atoms_learning = EXCLUDED.atoms_learning,
        atoms_struggling = EXCLUDED.atoms_struggling,
        atoms_new = EXCLUDED.atoms_new,
        total_reviews = EXCLUDED.total_reviews,
        last_review_date = EXCLUDED.last_review_date,
        needs_remediation = EXCLUDED.needs_remediation,
        remediation_reason = EXCLUDED.remediation_reason,
        remediation_priority = EXCLUDED.remediation_priority,
        is_started = EXCLUDED.is_started,
        is_completed = EXCLUDED.is_completed,
        completed_at = CASE
            WHEN EXCLUDED.is_completed AND NOT ccna_section_mastery.is_completed
            THEN NOW()
            ELSE ccna_section_mastery.completed_at
        END,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;


-- Batch update all section mastery
CREATE OR REPLACE FUNCTION refresh_all_section_mastery(
    p_user_id TEXT DEFAULT 'default'
) RETURNS INTEGER AS $$
DECLARE
    v_section RECORD;
    v_count INTEGER := 0;
BEGIN
    FOR v_section IN SELECT section_id FROM ccna_sections LOOP
        PERFORM update_section_mastery(v_section.section_id, p_user_id);
        v_count := v_count + 1;
    END LOOP;

    RETURN v_count;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- Initial data migration (if ccna_section_status exists)
-- ============================================================================

-- Migrate existing section data if available
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ccna_section_status') THEN
        INSERT INTO ccna_sections (module_number, section_id, title, level, parent_section_id, atom_count, display_order)
        SELECT
            CAST(SPLIT_PART(module_id, '-', 2) AS INTEGER) AS module_number,
            section_id,
            section_title,
            section_level,
            parent_section_id,
            atoms_generated,
            ROW_NUMBER() OVER (ORDER BY module_id, section_id)
        FROM ccna_section_status
        WHERE NOT EXISTS (SELECT 1 FROM ccna_sections WHERE ccna_sections.section_id = ccna_section_status.section_id)
        ON CONFLICT (section_id) DO NOTHING;
    END IF;
END $$;

-- Grant permissions (adjust as needed)
-- GRANT SELECT, INSERT, UPDATE ON ccna_sections TO app_user;
-- GRANT SELECT, INSERT, UPDATE ON ccna_section_mastery TO app_user;
-- GRANT SELECT, INSERT, UPDATE ON ccna_study_sessions TO app_user;
