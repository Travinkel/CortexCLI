-- Migration 012: War Mode Schema - Fidelity Tracking & Extended Question Types
--
-- Adds support for:
-- 1. Fidelity Tracking (is_hydrated, fidelity_type, source_fact_basis) for atom provenance
-- 2. Extended question types: 'numeric' (Binary/Hex/Subnetting) and 'parsons' (CLI ordering)
-- 3. War Mode Sessions for intensive study tracking
--
-- Rationale:
-- - Fidelity tracking distinguishes AI-generated scenarios from verbatim source extracts
-- - Numeric atoms are critical for CCNA Modules 5, 10, 11 (subnetting, binary math)
-- - Parsons problems test procedural knowledge of CLI command sequences

-- =============================================================================
-- PART 1: FIDELITY TRACKING FOR clean_atoms
-- =============================================================================

-- Add fidelity tracking columns to clean_atoms
DO $$
BEGIN
    -- is_hydrated: True if the atom uses an AI-generated scenario not in source text
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'is_hydrated') THEN
        ALTER TABLE clean_atoms ADD COLUMN is_hydrated BOOLEAN DEFAULT FALSE;
        COMMENT ON COLUMN clean_atoms.is_hydrated IS
            'True if atom uses AI-generated scenario not strictly in source text';
    END IF;

    -- fidelity_type: Classification of content origin
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'fidelity_type') THEN
        ALTER TABLE clean_atoms ADD COLUMN fidelity_type TEXT DEFAULT 'verbatim_extract';
        -- Add check constraint for valid fidelity types
        ALTER TABLE clean_atoms ADD CONSTRAINT check_fidelity_type
            CHECK (fidelity_type IN ('verbatim_extract', 'rephrased_fact', 'ai_scenario_enrichment'));
        COMMENT ON COLUMN clean_atoms.fidelity_type IS
            'Content origin: verbatim_extract | rephrased_fact | ai_scenario_enrichment';
    END IF;

    -- source_fact_basis: The raw fact from source text used as anchor for AI scenarios
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'source_fact_basis') THEN
        ALTER TABLE clean_atoms ADD COLUMN source_fact_basis TEXT;
        COMMENT ON COLUMN clean_atoms.source_fact_basis IS
            'The exact raw fact from source text used as anchor for hydrated content (max 300 chars)';
    END IF;
END $$;

-- Index for fidelity-based queries (auditing hydrated content)
CREATE INDEX IF NOT EXISTS idx_atoms_is_hydrated ON clean_atoms(is_hydrated) WHERE is_hydrated = TRUE;
CREATE INDEX IF NOT EXISTS idx_atoms_fidelity_type ON clean_atoms(fidelity_type);


-- =============================================================================
-- PART 2: EXTEND quiz_questions CHECK CONSTRAINT FOR NEW TYPES
-- =============================================================================

-- First, drop the old constraint if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.constraint_column_usage
               WHERE table_name = 'quiz_questions' AND constraint_name = 'check_question_type') THEN
        ALTER TABLE quiz_questions DROP CONSTRAINT check_question_type;
    END IF;
END $$;

-- Add expanded constraint including 'numeric' and 'parsons'
-- Note: We check if any constraint exists to avoid errors
DO $$
BEGIN
    -- Only add if not already present
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                   WHERE table_name = 'quiz_questions'
                   AND constraint_name = 'check_question_type_extended') THEN
        ALTER TABLE quiz_questions ADD CONSTRAINT check_question_type_extended
            CHECK (question_type IN (
                'mcq',
                'true_false',
                'short_answer',
                'matching',
                'ranking',
                'passage_based',
                'numeric',     -- NEW: Binary/Hex/Subnetting calculations
                'parsons'      -- NEW: CLI command ordering
            ));
    END IF;
END $$;

COMMENT ON COLUMN quiz_questions.question_type IS
    'Question type: mcq, true_false, short_answer, matching, ranking, passage_based, numeric, parsons';


-- =============================================================================
-- PART 3: WAR MODE SESSIONS TABLE
-- =============================================================================

-- Create war_mode_sessions table for intensive study tracking
CREATE TABLE IF NOT EXISTS war_mode_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Session identification
    session_name TEXT NOT NULL,
    user_id TEXT,  -- Optional: for multi-user scenarios

    -- Target scope
    target_modules INTEGER[] NOT NULL,  -- Array of module numbers to focus on
    target_concepts UUID[],             -- Optional: specific concept IDs

    -- Session timing
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    planned_duration_minutes INTEGER,
    actual_duration_minutes INTEGER,

    -- Goals and thresholds
    target_accuracy DECIMAL(3, 2) DEFAULT 0.85,  -- 85% target accuracy
    minimum_atoms INTEGER DEFAULT 50,            -- Minimum atoms to review

    -- Progress tracking
    atoms_reviewed INTEGER DEFAULT 0,
    atoms_correct INTEGER DEFAULT 0,
    atoms_incorrect INTEGER DEFAULT 0,
    current_accuracy DECIMAL(5, 4) DEFAULT 0.0,

    -- Fatigue detection
    fatigue_detected BOOLEAN DEFAULT FALSE,
    fatigue_detection_time TIMESTAMP WITH TIME ZONE,
    fatigue_signal TEXT,  -- 'accuracy_drop', 'response_time_increase', 'streak'

    -- Session state
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed', 'abandoned')),

    -- Module progress (JSONB for flexibility)
    module_progress JSONB DEFAULT '{}'::JSONB,
    -- Example: {"5": {"reviewed": 30, "correct": 25}, "10": {"reviewed": 20, "correct": 18}}

    -- Atom type breakdown
    type_breakdown JSONB DEFAULT '{}'::JSONB,
    -- Example: {"flashcard": 25, "mcq": 15, "numeric": 10, "parsons": 5}

    -- Session notes
    notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for efficient war mode queries
CREATE INDEX IF NOT EXISTS idx_war_sessions_status ON war_mode_sessions(status);
CREATE INDEX IF NOT EXISTS idx_war_sessions_started ON war_mode_sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_war_sessions_modules ON war_mode_sessions USING GIN(target_modules);

COMMENT ON TABLE war_mode_sessions IS
    'Intensive study sessions tracking progress, fatigue, and module-specific performance';


-- =============================================================================
-- PART 4: WAR MODE SESSION ATOMS (Junction Table)
-- =============================================================================

-- Track which atoms were reviewed in each war mode session
CREATE TABLE IF NOT EXISTS war_mode_session_atoms (
    session_id UUID NOT NULL REFERENCES war_mode_sessions(id) ON DELETE CASCADE,
    atom_id UUID NOT NULL REFERENCES clean_atoms(id) ON DELETE CASCADE,

    -- Review data
    reviewed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    grade INTEGER CHECK (grade BETWEEN 0 AND 5),  -- SM-2 grade
    response_ms INTEGER,                           -- Response time in milliseconds
    is_correct BOOLEAN,

    -- Optional confidence
    self_confidence INTEGER CHECK (self_confidence BETWEEN 1 AND 5),

    -- Intervention tracking
    socratic_triggered BOOLEAN DEFAULT FALSE,
    socratic_response TEXT,

    PRIMARY KEY (session_id, atom_id, reviewed_at)
);

CREATE INDEX IF NOT EXISTS idx_war_session_atoms_session ON war_mode_session_atoms(session_id);
CREATE INDEX IF NOT EXISTS idx_war_session_atoms_atom ON war_mode_session_atoms(atom_id);

COMMENT ON TABLE war_mode_session_atoms IS
    'Junction table tracking atom reviews within war mode sessions';


-- =============================================================================
-- PART 5: VIEW FOR QUIZ ATOMS WITH FIDELITY
-- =============================================================================

-- View for quiz-compatible atoms with fidelity tracking
-- Note: Uses only columns that exist in clean_atoms schema
CREATE OR REPLACE VIEW v_quiz_atoms_fidelity AS
SELECT
    ca.id,
    ca.card_id,
    ca.front,
    ca.back,
    ca.atom_type,
    ca.concept_id,
    ca.ccna_section_id,
    ca.quality_score,
    -- Fidelity tracking
    ca.is_hydrated,
    ca.fidelity_type,
    ca.source_fact_basis,
    -- Review status
    ca.needs_review,
    ca.is_atomic
FROM clean_atoms ca
WHERE ca.atom_type IN ('mcq', 'true_false', 'matching', 'parsons', 'numeric', 'ranking', 'short_answer')
  AND ca.front IS NOT NULL;

COMMENT ON VIEW v_quiz_atoms_fidelity IS 'Quiz atoms (including numeric & parsons) with fidelity tracking';


-- =============================================================================
-- PART 6: HELPER FUNCTIONS
-- =============================================================================

-- Function: Get fidelity audit for a module
CREATE OR REPLACE FUNCTION audit_fidelity_by_module(target_module INT)
RETURNS TABLE (
    fidelity_type TEXT,
    atom_count BIGINT,
    percentage DECIMAL(5, 2)
) AS $$
BEGIN
    RETURN QUERY
    WITH module_atoms AS (
        SELECT ca.fidelity_type
        FROM clean_atoms ca
        JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
        WHERE cs.module_number = target_module
    ),
    total AS (
        SELECT COUNT(*) as total_count FROM module_atoms
    )
    SELECT
        COALESCE(ma.fidelity_type, 'unknown') as fidelity_type,
        COUNT(*) as atom_count,
        ROUND(COUNT(*) * 100.0 / NULLIF((SELECT total_count FROM total), 0), 2) as percentage
    FROM module_atoms ma
    GROUP BY ma.fidelity_type
    ORDER BY atom_count DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION audit_fidelity_by_module IS
    'Audit fidelity type distribution for a specific module';


-- Function: Get war mode session summary
CREATE OR REPLACE FUNCTION get_war_session_summary(session_uuid UUID)
RETURNS TABLE (
    session_name TEXT,
    status TEXT,
    duration_minutes INTEGER,
    atoms_reviewed INTEGER,
    accuracy DECIMAL(5, 4),
    fatigue_detected BOOLEAN,
    by_module JSONB,
    by_type JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        wms.session_name,
        wms.status,
        COALESCE(wms.actual_duration_minutes,
                 EXTRACT(EPOCH FROM (COALESCE(wms.ended_at, NOW()) - wms.started_at))::INTEGER / 60),
        wms.atoms_reviewed,
        wms.current_accuracy,
        wms.fatigue_detected,
        wms.module_progress,
        wms.type_breakdown
    FROM war_mode_sessions wms
    WHERE wms.id = session_uuid;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_war_session_summary IS
    'Get summary statistics for a war mode session';
