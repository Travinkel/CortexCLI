-- Migration 007: Adaptive Learning Engine
-- Phase 5: Knewton-style just-in-time remediation with mastery-based gating
-- Created: 2025-12-03

-- ============================================================================
-- Table: learner_mastery_state
-- Tracks current mastery state per learner per concept
-- ============================================================================

CREATE TABLE IF NOT EXISTS learner_mastery_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    learner_id TEXT NOT NULL,  -- User identifier (could be user ID or session ID)
    concept_id UUID NOT NULL REFERENCES clean_concepts(id) ON DELETE CASCADE,

    -- Mastery scores (0-1 scale)
    review_mastery DECIMAL(5,4) DEFAULT 0,      -- From FSRS retrievability
    quiz_mastery DECIMAL(5,4) DEFAULT 0,        -- From quiz performance
    combined_mastery DECIMAL(5,4) DEFAULT 0,    -- 62.5% review + 37.5% quiz

    -- Knowledge type breakdown (0-10 scale, matches clean_concepts)
    dec_score DECIMAL(4,2) DEFAULT 0,   -- Declarative knowledge mastery
    proc_score DECIMAL(4,2) DEFAULT 0,  -- Procedural knowledge mastery
    app_score DECIMAL(4,2) DEFAULT 0,   -- Application knowledge mastery

    -- Activity tracking
    last_review_at TIMESTAMPTZ,
    last_quiz_at TIMESTAMPTZ,
    review_count INT DEFAULT 0,
    quiz_attempt_count INT DEFAULT 0,

    -- Unlock state
    is_unlocked BOOLEAN DEFAULT FALSE,
    unlock_reason TEXT,  -- 'mastery', 'waiver', 'prerequisite_met', 'no_prerequisites'
    unlocked_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(learner_id, concept_id)
);

CREATE INDEX IF NOT EXISTS idx_mastery_state_learner ON learner_mastery_state(learner_id);
CREATE INDEX IF NOT EXISTS idx_mastery_state_concept ON learner_mastery_state(concept_id);
CREATE INDEX IF NOT EXISTS idx_mastery_state_unlocked ON learner_mastery_state(learner_id, is_unlocked);
CREATE INDEX IF NOT EXISTS idx_mastery_state_combined ON learner_mastery_state(combined_mastery);


-- ============================================================================
-- Table: learning_path_sessions
-- Tracks adaptive learning sessions
-- ============================================================================

CREATE TABLE IF NOT EXISTS learning_path_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    learner_id TEXT NOT NULL,

    -- Session scope (one of these should be set)
    target_concept_id UUID REFERENCES clean_concepts(id),
    target_cluster_id UUID REFERENCES clean_concept_clusters(id),
    target_module_id UUID REFERENCES clean_modules(id),

    -- Session configuration
    session_mode TEXT DEFAULT 'adaptive',  -- 'adaptive', 'review', 'quiz', 'remediation'

    -- Session state
    status TEXT DEFAULT 'active',  -- 'active', 'paused', 'completed', 'abandoned'
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    paused_at TIMESTAMPTZ,

    -- Progress tracking
    atoms_presented INT DEFAULT 0,
    atoms_correct INT DEFAULT 0,
    atoms_incorrect INT DEFAULT 0,
    atoms_skipped INT DEFAULT 0,
    remediation_count INT DEFAULT 0,

    -- Time tracking
    total_time_seconds INT DEFAULT 0,
    avg_response_time_ms INT,

    -- Sequencing
    current_atom_id UUID REFERENCES clean_atoms(id),
    atom_sequence UUID[],        -- Ordered list of atoms to present
    completed_atoms UUID[],      -- Atoms already presented

    -- Remediation tracking
    remediation_atoms UUID[],    -- Atoms served as remediation
    gap_concepts UUID[],         -- Concepts where gaps were detected

    -- Mastery progress
    initial_mastery DECIMAL(5,4),
    final_mastery DECIMAL(5,4),
    mastery_gained DECIMAL(5,4),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_path_session_learner ON learning_path_sessions(learner_id);
CREATE INDEX IF NOT EXISTS idx_path_session_status ON learning_path_sessions(status);
CREATE INDEX IF NOT EXISTS idx_path_session_active ON learning_path_sessions(learner_id, status) WHERE status = 'active';


-- ============================================================================
-- Table: session_atom_responses
-- Individual responses within a learning session
-- ============================================================================

CREATE TABLE IF NOT EXISTS session_atom_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES learning_path_sessions(id) ON DELETE CASCADE,
    atom_id UUID NOT NULL REFERENCES clean_atoms(id),

    -- Response details
    is_correct BOOLEAN,
    score DECIMAL(5,4),              -- For partial credit (0-1)
    response_content JSONB,          -- The actual response
    time_spent_ms INT,
    confidence_rating INT,           -- Self-reported 1-5

    -- Context
    was_remediation BOOLEAN DEFAULT FALSE,
    attempt_number INT DEFAULT 1,
    presented_at TIMESTAMPTZ DEFAULT NOW(),
    answered_at TIMESTAMPTZ,

    -- Feedback shown
    feedback_shown BOOLEAN DEFAULT FALSE,
    hint_level_used INT DEFAULT 0,   -- 0=none, 1=hint1, 2=hint2, 3=answer

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_atom_response_session ON session_atom_responses(session_id);
CREATE INDEX IF NOT EXISTS idx_atom_response_atom ON session_atom_responses(atom_id);


-- ============================================================================
-- Table: atom_type_suitability
-- Pre-computed suitability scores for atoms across all types
-- ============================================================================

CREATE TABLE IF NOT EXISTS atom_type_suitability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    atom_id UUID NOT NULL REFERENCES clean_atoms(id) ON DELETE CASCADE,

    -- Suitability scores per type (0-1)
    flashcard_score DECIMAL(4,3),
    cloze_score DECIMAL(4,3),
    mcq_score DECIMAL(4,3),
    true_false_score DECIMAL(4,3),
    matching_score DECIMAL(4,3),
    parsons_score DECIMAL(4,3),
    compare_score DECIMAL(4,3),
    ranking_score DECIMAL(4,3),
    sequence_score DECIMAL(4,3),

    -- Best type recommendation
    recommended_type TEXT,
    current_type TEXT,  -- The type it was actually generated as
    recommendation_confidence DECIMAL(4,3),
    type_mismatch BOOLEAN DEFAULT FALSE,  -- True if current != recommended

    -- Scoring signals (for debugging/transparency)
    knowledge_signal DECIMAL(4,3),    -- Primary: knowledge type alignment
    structure_signal DECIMAL(4,3),    -- Secondary: content structure
    length_signal DECIMAL(4,3),       -- Tertiary: content length

    -- Content features used in scoring
    content_features JSONB,

    -- Computation metadata
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    computation_method TEXT DEFAULT 'rule_based',  -- 'rule_based', 'ai_scored', 'hybrid'

    UNIQUE(atom_id)
);

CREATE INDEX IF NOT EXISTS idx_suitability_atom ON atom_type_suitability(atom_id);
CREATE INDEX IF NOT EXISTS idx_suitability_mismatch ON atom_type_suitability(type_mismatch) WHERE type_mismatch = TRUE;


-- ============================================================================
-- Table: remediation_events
-- Tracks just-in-time remediation events
-- ============================================================================

CREATE TABLE IF NOT EXISTS remediation_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES learning_path_sessions(id) ON DELETE SET NULL,
    learner_id TEXT NOT NULL,

    -- What triggered remediation
    trigger_atom_id UUID REFERENCES clean_atoms(id),
    trigger_concept_id UUID REFERENCES clean_concepts(id),
    trigger_type TEXT NOT NULL,  -- 'incorrect_answer', 'low_confidence', 'prerequisite_gap', 'manual'

    -- Gap detected
    gap_concept_id UUID NOT NULL REFERENCES clean_concepts(id),
    mastery_at_trigger DECIMAL(5,4),
    required_mastery DECIMAL(5,4),
    mastery_gap DECIMAL(5,4),
    gating_type TEXT,  -- 'soft', 'hard'

    -- Remediation provided
    remediation_atoms UUID[],
    remediation_concept_ids UUID[],
    remediation_started_at TIMESTAMPTZ DEFAULT NOW(),
    remediation_completed_at TIMESTAMPTZ,

    -- Outcome
    atoms_completed INT DEFAULT 0,
    atoms_correct INT DEFAULT 0,
    post_remediation_mastery DECIMAL(5,4),
    mastery_improvement DECIMAL(5,4),
    remediation_successful BOOLEAN,  -- Did mastery reach threshold?

    -- User choice
    was_skipped BOOLEAN DEFAULT FALSE,  -- User chose to skip remediation
    skip_reason TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_remediation_learner ON remediation_events(learner_id);
CREATE INDEX IF NOT EXISTS idx_remediation_gap ON remediation_events(gap_concept_id);
CREATE INDEX IF NOT EXISTS idx_remediation_session ON remediation_events(session_id);
CREATE INDEX IF NOT EXISTS idx_remediation_trigger ON remediation_events(trigger_type);


-- ============================================================================
-- Alter existing tables
-- ============================================================================

-- Add adaptive learning fields to clean_atoms
ALTER TABLE clean_atoms
ADD COLUMN IF NOT EXISTS has_prerequisites BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS prerequisite_count INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS best_atom_type TEXT,
ADD COLUMN IF NOT EXISTS suitability_computed_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS complexity_score DECIMAL(4,3),  -- 0-1 scale
ADD COLUMN IF NOT EXISTS intrinsic_difficulty DECIMAL(4,3);  -- IRT-derived difficulty

-- Add computed mastery caching to clean_concepts
ALTER TABLE clean_concepts
ADD COLUMN IF NOT EXISTS avg_learner_mastery DECIMAL(5,4),
ADD COLUMN IF NOT EXISTS difficulty_estimate DECIMAL(3,2),
ADD COLUMN IF NOT EXISTS atom_count INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS mastery_computed_at TIMESTAMPTZ;


-- ============================================================================
-- Views
-- ============================================================================

-- View: Learner progress summary
CREATE OR REPLACE VIEW v_learner_progress AS
SELECT
    lms.learner_id,
    cc.name as concept_name,
    cc.id as concept_id,
    ccl.name as cluster_name,
    ccl.id as cluster_id,
    lms.combined_mastery,
    lms.review_mastery,
    lms.quiz_mastery,
    lms.dec_score,
    lms.proc_score,
    lms.app_score,
    lms.is_unlocked,
    lms.unlock_reason,
    lms.review_count,
    lms.quiz_attempt_count,
    CASE
        WHEN lms.combined_mastery >= 0.85 THEN 'mastery'
        WHEN lms.combined_mastery >= 0.65 THEN 'proficient'
        WHEN lms.combined_mastery >= 0.40 THEN 'developing'
        ELSE 'novice'
    END as mastery_level,
    lms.updated_at
FROM learner_mastery_state lms
JOIN clean_concepts cc ON lms.concept_id = cc.id
LEFT JOIN clean_concept_clusters ccl ON cc.cluster_id = ccl.id
ORDER BY lms.learner_id, lms.combined_mastery DESC;


-- View: Remediation effectiveness analysis
CREATE OR REPLACE VIEW v_remediation_effectiveness AS
SELECT
    re.gap_concept_id,
    cc.name as concept_name,
    re.trigger_type,
    COUNT(*) as total_remediations,
    COUNT(*) FILTER (WHERE re.remediation_successful) as successful,
    COUNT(*) FILTER (WHERE re.was_skipped) as skipped,
    ROUND(AVG(re.post_remediation_mastery - re.mastery_at_trigger)::numeric, 4) as avg_mastery_gain,
    ROUND(AVG(EXTRACT(EPOCH FROM (re.remediation_completed_at - re.remediation_started_at)))::numeric, 1) as avg_duration_seconds,
    ROUND(AVG(re.atoms_completed)::numeric, 1) as avg_atoms_completed
FROM remediation_events re
JOIN clean_concepts cc ON re.gap_concept_id = cc.id
WHERE re.remediation_completed_at IS NOT NULL
GROUP BY re.gap_concept_id, cc.name, re.trigger_type;


-- View: Atom type suitability mismatches (for content improvement)
CREATE OR REPLACE VIEW v_suitability_mismatches AS
SELECT
    ats.atom_id,
    ca.card_id,
    ca.front,
    ats.current_type,
    ats.recommended_type,
    ats.recommendation_confidence,
    ats.knowledge_signal,
    ats.structure_signal,
    ats.computed_at
FROM atom_type_suitability ats
JOIN clean_atoms ca ON ats.atom_id = ca.id
WHERE ats.type_mismatch = TRUE
AND ats.recommendation_confidence > 0.7
ORDER BY ats.recommendation_confidence DESC;


-- View: Session analytics
CREATE OR REPLACE VIEW v_session_analytics AS
SELECT
    lps.learner_id,
    lps.session_mode,
    lps.status,
    lps.atoms_presented,
    lps.atoms_correct,
    CASE WHEN lps.atoms_presented > 0
        THEN ROUND((lps.atoms_correct::decimal / lps.atoms_presented * 100), 1)
        ELSE 0
    END as accuracy_percent,
    lps.remediation_count,
    lps.mastery_gained,
    lps.total_time_seconds,
    lps.started_at,
    lps.completed_at,
    cc.name as target_concept,
    ccl.name as target_cluster
FROM learning_path_sessions lps
LEFT JOIN clean_concepts cc ON lps.target_concept_id = cc.id
LEFT JOIN clean_concept_clusters ccl ON lps.target_cluster_id = ccl.id;


-- ============================================================================
-- Unified Audit Log View (consolidation)
-- ============================================================================

CREATE OR REPLACE VIEW v_unified_audit_log AS
SELECT
    'sync' as log_type,
    id,
    sync_type as operation,
    started_at,
    completed_at,
    status,
    items_processed,
    items_added,
    items_updated,
    items_removed,
    error_message,
    details
FROM sync_log

UNION ALL

SELECT
    'cleaning' as log_type,
    id,
    operation,
    performed_at as started_at,
    performed_at as completed_at,
    'completed' as status,
    1 as items_processed,
    NULL as items_added,
    NULL as items_updated,
    NULL as items_removed,
    NULL as error_message,
    old_value as details
FROM cleaning_log

UNION ALL

SELECT
    'embedding' as log_type,
    id,
    'embedding_generation' as operation,
    started_at,
    completed_at,
    status,
    records_processed as items_processed,
    records_processed - records_skipped - records_failed as items_added,
    NULL as items_updated,
    NULL as items_removed,
    error_message,
    NULL as details
FROM embedding_generation_log;


-- ============================================================================
-- Functions
-- ============================================================================

-- Function: Calculate combined mastery
CREATE OR REPLACE FUNCTION calculate_combined_mastery(
    p_review_mastery DECIMAL,
    p_quiz_mastery DECIMAL
) RETURNS DECIMAL AS $$
BEGIN
    -- Formula: 62.5% review + 37.5% quiz (from right-learning research)
    RETURN COALESCE(p_review_mastery, 0) * 0.625 + COALESCE(p_quiz_mastery, 0) * 0.375;
END;
$$ LANGUAGE plpgsql IMMUTABLE;


-- Function: Update learner mastery state
CREATE OR REPLACE FUNCTION update_learner_mastery(
    p_learner_id TEXT,
    p_concept_id UUID,
    p_review_mastery DECIMAL DEFAULT NULL,
    p_quiz_mastery DECIMAL DEFAULT NULL,
    p_dec_score DECIMAL DEFAULT NULL,
    p_proc_score DECIMAL DEFAULT NULL,
    p_app_score DECIMAL DEFAULT NULL
) RETURNS learner_mastery_state AS $$
DECLARE
    v_state learner_mastery_state;
    v_combined DECIMAL;
BEGIN
    -- Get or create state
    INSERT INTO learner_mastery_state (learner_id, concept_id)
    VALUES (p_learner_id, p_concept_id)
    ON CONFLICT (learner_id, concept_id) DO NOTHING;

    -- Update with provided values
    UPDATE learner_mastery_state
    SET
        review_mastery = COALESCE(p_review_mastery, review_mastery),
        quiz_mastery = COALESCE(p_quiz_mastery, quiz_mastery),
        combined_mastery = calculate_combined_mastery(
            COALESCE(p_review_mastery, review_mastery),
            COALESCE(p_quiz_mastery, quiz_mastery)
        ),
        dec_score = COALESCE(p_dec_score, dec_score),
        proc_score = COALESCE(p_proc_score, proc_score),
        app_score = COALESCE(p_app_score, app_score),
        last_review_at = CASE WHEN p_review_mastery IS NOT NULL THEN NOW() ELSE last_review_at END,
        last_quiz_at = CASE WHEN p_quiz_mastery IS NOT NULL THEN NOW() ELSE last_quiz_at END,
        review_count = CASE WHEN p_review_mastery IS NOT NULL THEN review_count + 1 ELSE review_count END,
        quiz_attempt_count = CASE WHEN p_quiz_mastery IS NOT NULL THEN quiz_attempt_count + 1 ELSE quiz_attempt_count END,
        updated_at = NOW()
    WHERE learner_id = p_learner_id AND concept_id = p_concept_id
    RETURNING * INTO v_state;

    RETURN v_state;
END;
$$ LANGUAGE plpgsql;


-- Function: Check if concept is unlocked for learner
CREATE OR REPLACE FUNCTION check_concept_unlocked(
    p_learner_id TEXT,
    p_concept_id UUID
) RETURNS TABLE (
    is_unlocked BOOLEAN,
    blocking_prerequisites UUID[],
    mastery_gap DECIMAL,
    unlock_reason TEXT
) AS $$
DECLARE
    v_prereqs RECORD;
    v_blocking UUID[];
    v_max_gap DECIMAL := 0;
    v_learner_mastery DECIMAL;
    v_required DECIMAL;
BEGIN
    v_blocking := ARRAY[]::UUID[];

    -- Check each prerequisite
    FOR v_prereqs IN
        SELECT
            ep.target_concept_id,
            ep.mastery_threshold,
            ep.gating_type,
            COALESCE(lms.combined_mastery, 0) as current_mastery
        FROM explicit_prerequisites ep
        LEFT JOIN learner_mastery_state lms
            ON lms.concept_id = ep.target_concept_id
            AND lms.learner_id = p_learner_id
        WHERE ep.source_concept_id = p_concept_id
        AND ep.status = 'active'
        AND ep.gating_type = 'hard'  -- Only hard gates block
    LOOP
        IF v_prereqs.current_mastery < v_prereqs.mastery_threshold THEN
            v_blocking := array_append(v_blocking, v_prereqs.target_concept_id);
            v_max_gap := GREATEST(v_max_gap, v_prereqs.mastery_threshold - v_prereqs.current_mastery);
        END IF;
    END LOOP;

    -- Return results
    IF array_length(v_blocking, 1) IS NULL OR array_length(v_blocking, 1) = 0 THEN
        RETURN QUERY SELECT TRUE, v_blocking, 0::DECIMAL, 'prerequisites_met'::TEXT;
    ELSE
        RETURN QUERY SELECT FALSE, v_blocking, v_max_gap, 'blocked_by_prerequisites'::TEXT;
    END IF;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- Triggers
-- ============================================================================

-- Trigger: Update timestamps on learner_mastery_state
CREATE OR REPLACE FUNCTION trigger_update_mastery_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_mastery_state_updated ON learner_mastery_state;
CREATE TRIGGER trg_mastery_state_updated
    BEFORE UPDATE ON learner_mastery_state
    FOR EACH ROW
    EXECUTE FUNCTION trigger_update_mastery_timestamp();


-- Trigger: Update timestamps on learning_path_sessions
DROP TRIGGER IF EXISTS trg_session_updated ON learning_path_sessions;
CREATE TRIGGER trg_session_updated
    BEFORE UPDATE ON learning_path_sessions
    FOR EACH ROW
    EXECUTE FUNCTION trigger_update_mastery_timestamp();


-- ============================================================================
-- Initial Data Setup
-- ============================================================================

-- Update atom counts on concepts
UPDATE clean_concepts cc
SET atom_count = (
    SELECT COUNT(*)
    FROM clean_atoms ca
    WHERE ca.concept_id = cc.id
);

-- Update has_prerequisites flag on atoms
UPDATE clean_atoms ca
SET
    has_prerequisites = EXISTS (
        SELECT 1 FROM explicit_prerequisites ep
        WHERE ep.source_atom_id = ca.id
    ),
    prerequisite_count = (
        SELECT COUNT(*) FROM explicit_prerequisites ep
        WHERE ep.source_atom_id = ca.id
    );


-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE learner_mastery_state IS 'Tracks per-learner mastery state for each concept';
COMMENT ON TABLE learning_path_sessions IS 'Tracks adaptive learning sessions with sequencing and remediation';
COMMENT ON TABLE session_atom_responses IS 'Individual atom responses within a learning session';
COMMENT ON TABLE atom_type_suitability IS 'Pre-computed suitability scores for atoms across all atom types';
COMMENT ON TABLE remediation_events IS 'Tracks just-in-time remediation events and outcomes';

COMMENT ON VIEW v_learner_progress IS 'Learner progress summary with mastery levels';
COMMENT ON VIEW v_remediation_effectiveness IS 'Analysis of remediation effectiveness by concept';
COMMENT ON VIEW v_suitability_mismatches IS 'Atoms where current type differs from recommended type';
COMMENT ON VIEW v_unified_audit_log IS 'Consolidated view of all audit logs (sync, cleaning, embedding)';

COMMENT ON FUNCTION calculate_combined_mastery IS 'Calculate combined mastery: 62.5% review + 37.5% quiz';
COMMENT ON FUNCTION update_learner_mastery IS 'Update learner mastery state with recalculation';
COMMENT ON FUNCTION check_concept_unlocked IS 'Check if concept is unlocked based on hard prerequisites';
