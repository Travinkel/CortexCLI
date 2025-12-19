-- Migration: 014_neuromorphic_cortex.sql
-- Description: Cortex 2.0 Neuromorphic Architecture Schema
-- Version: 2.0.0
-- Date: 2025-12-06
--
-- This migration adds support for:
-- 1. Enhanced learner profiles with P-FIT and hippocampal indices
-- 2. Learning atoms with ps_index (Pattern Separation Index)
-- 3. Cognitive diagnosis tracking
-- 4. PLM (Perceptual Learning Module) sessions
-- 5. HRL scheduler state

-- ============================================================================
-- LEARNER PROFILES (Enhanced)
-- ============================================================================

-- Add new columns to existing learner_profiles if they exist,
-- otherwise create the full table
DO $$
BEGIN
    -- Check if table exists
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'learner_profiles') THEN
        -- Add new columns if they don't exist
        IF NOT EXISTS (SELECT FROM information_schema.columns
                       WHERE table_name = 'learner_profiles' AND column_name = 'processing_speed') THEN
            ALTER TABLE learner_profiles
            ADD COLUMN processing_speed VARCHAR(32) DEFAULT 'moderate',
            ADD COLUMN attention_span_minutes INTEGER DEFAULT 25,
            ADD COLUMN chronotype VARCHAR(32) DEFAULT 'neutral',
            ADD COLUMN low_energy_hours INTEGER[] DEFAULT '{14,15,16}',
            ADD COLUMN strength_strategic DECIMAL(4,3) DEFAULT 0.5,
            ADD COLUMN current_velocity DECIMAL(6,2) DEFAULT 0.0,
            ADD COLUMN velocity_trend VARCHAR(16) DEFAULT 'stable',
            ADD COLUMN acceleration_rate DECIMAL(6,2) DEFAULT 0.0,
            ADD COLUMN pfit_efficiency DECIMAL(4,3) DEFAULT 0.5,
            ADD COLUMN hippocampal_efficiency DECIMAL(4,3) DEFAULT 0.5,
            ADD COLUMN interference_patterns JSONB DEFAULT '[]'::jsonb,
            ADD COLUMN conceptual_weaknesses JSONB DEFAULT '[]'::jsonb,
            ADD COLUMN preferred_modality VARCHAR(32) DEFAULT 'mixed';
        END IF;
    ELSE
        -- Create the full table
        CREATE TABLE learner_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id VARCHAR(255) UNIQUE NOT NULL,

            -- Processing characteristics
            processing_speed VARCHAR(32) DEFAULT 'moderate',
            attention_span_minutes INTEGER DEFAULT 25,
            preferred_session_duration_min INTEGER DEFAULT 25,

            -- Chronotype
            chronotype VARCHAR(32) DEFAULT 'neutral',
            optimal_study_hour INTEGER DEFAULT 10,
            low_energy_hours INTEGER[] DEFAULT '{14,15,16}',

            -- Knowledge type strengths (0-1)
            strength_factual DECIMAL(4,3) DEFAULT 0.5,
            strength_conceptual DECIMAL(4,3) DEFAULT 0.5,
            strength_procedural DECIMAL(4,3) DEFAULT 0.5,
            strength_strategic DECIMAL(4,3) DEFAULT 0.5,

            -- Mechanism effectiveness (0-1)
            effectiveness_retrieval DECIMAL(4,3) DEFAULT 0.5,
            effectiveness_generation DECIMAL(4,3) DEFAULT 0.5,
            effectiveness_elaboration DECIMAL(4,3) DEFAULT 0.5,
            effectiveness_application DECIMAL(4,3) DEFAULT 0.5,
            effectiveness_discrimination DECIMAL(4,3) DEFAULT 0.5,

            -- Calibration (0.5 = perfect)
            calibration_score DECIMAL(4,3) DEFAULT 0.5,

            -- Velocity and acceleration
            current_velocity DECIMAL(6,2) DEFAULT 0.0,
            velocity_trend VARCHAR(16) DEFAULT 'stable',
            acceleration_rate DECIMAL(6,2) DEFAULT 0.0,

            -- Neuromorphic indices
            pfit_efficiency DECIMAL(4,3) DEFAULT 0.5,
            hippocampal_efficiency DECIMAL(4,3) DEFAULT 0.5,

            -- Patterns
            interference_patterns JSONB DEFAULT '[]'::jsonb,
            conceptual_weaknesses JSONB DEFAULT '[]'::jsonb,
            preferred_modality VARCHAR(32) DEFAULT 'mixed',

            -- Cumulative stats
            total_study_hours DECIMAL(8,2) DEFAULT 0.0,
            total_atoms_seen INTEGER DEFAULT 0,
            total_atoms_mastered INTEGER DEFAULT 0,
            current_streak_days INTEGER DEFAULT 0,
            longest_streak_days INTEGER DEFAULT 0,

            -- Timestamps
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            last_session_at TIMESTAMPTZ
        );

        CREATE INDEX idx_learner_profiles_user_id ON learner_profiles(user_id);
    END IF;
END $$;


-- ============================================================================
-- LEARNING ATOMS (Enhanced with ps_index)
-- ============================================================================

-- Add neuromorphic columns to atoms table
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'atoms') THEN
        IF NOT EXISTS (SELECT FROM information_schema.columns
                       WHERE table_name = 'atoms' AND column_name = 'ps_index') THEN
            ALTER TABLE atoms
            ADD COLUMN ps_index DECIMAL(4,3) DEFAULT 0.5,
            ADD COLUMN pfit_index DECIMAL(4,3) DEFAULT 0.5,
            ADD COLUMN hippocampal_index DECIMAL(4,3) DEFAULT 0.5,
            ADD COLUMN intrinsic_load DECIMAL(4,3) DEFAULT 0.5,
            ADD COLUMN cognitive_modality VARCHAR(32) DEFAULT 'symbolic',
            ADD COLUMN adversarial_lures UUID[],
            ADD COLUMN embedding_vector FLOAT8[];
        END IF;
    END IF;
END $$;


-- ============================================================================
-- COGNITIVE DIAGNOSIS EVENTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS cognitive_diagnoses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    atom_id UUID,

    -- Diagnosis classification
    fail_mode VARCHAR(32),  -- encoding, retrieval, discrimination, integration, executive, fatigue
    success_mode VARCHAR(32),  -- recall, recognition, inference, fluency
    cognitive_state VARCHAR(32),  -- flow, anxiety, boredom, fatigue, distracted

    -- Metrics
    confidence DECIMAL(4,3),
    response_time_ms INTEGER,
    is_correct BOOLEAN,

    -- Neuromorphic indices at diagnosis time
    ps_index DECIMAL(4,3),
    pfit_index DECIMAL(4,3),
    hippocampal_index DECIMAL(4,3),

    -- Remediation
    remediation_type VARCHAR(32),
    remediation_target VARCHAR(255),
    remediation_completed BOOLEAN DEFAULT FALSE,

    -- Evidence
    evidence JSONB DEFAULT '[]'::jsonb,

    -- Timestamps
    diagnosed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cognitive_diagnoses_user ON cognitive_diagnoses(user_id);
CREATE INDEX idx_cognitive_diagnoses_atom ON cognitive_diagnoses(atom_id);
CREATE INDEX idx_cognitive_diagnoses_fail_mode ON cognitive_diagnoses(fail_mode);
CREATE INDEX idx_cognitive_diagnoses_time ON cognitive_diagnoses(diagnosed_at DESC);


-- ============================================================================
-- PLM (Perceptual Learning Module) SESSIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS plm_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,

    -- Session metadata
    target_categories TEXT[],
    task_type VARCHAR(32),  -- classification, discrimination, completion, ordering
    difficulty VARCHAR(16),  -- easy, medium, hard, adaptive

    -- Session stats
    total_trials INTEGER DEFAULT 0,
    correct_trials INTEGER DEFAULT 0,
    avg_response_ms DECIMAL(8,2) DEFAULT 0,
    fast_rate DECIMAL(4,3) DEFAULT 0,  -- % under target time
    fluency_achieved BOOLEAN DEFAULT FALSE,

    -- Timestamps
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_plm_sessions_user ON plm_sessions(user_id);


-- ============================================================================
-- PLM TRIALS
-- ============================================================================

CREATE TABLE IF NOT EXISTS plm_trials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES plm_sessions(id) ON DELETE CASCADE,

    -- Trial data
    stimulus_id VARCHAR(255),
    stimulus_category VARCHAR(255),
    options TEXT[],
    correct_response VARCHAR(255),

    -- Response
    user_response VARCHAR(255),
    response_time_ms INTEGER,
    is_correct BOOLEAN,
    is_fast BOOLEAN,  -- Under target time
    is_automatic BOOLEAN,  -- <500ms and correct

    -- Timestamps
    presented_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_plm_trials_session ON plm_trials(session_id);


-- ============================================================================
-- CATEGORY FLUENCY TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS category_fluency (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    category VARCHAR(255) NOT NULL,

    -- Metrics
    total_trials INTEGER DEFAULT 0,
    correct_trials INTEGER DEFAULT 0,
    accuracy DECIMAL(4,3) DEFAULT 0,
    avg_response_ms DECIMAL(8,2) DEFAULT 0,
    fast_rate DECIMAL(4,3) DEFAULT 0,
    fluency_level VARCHAR(16) DEFAULT 'effortful',  -- automatic, fluent, developing, effortful, struggling

    -- Confusion tracking
    confused_with JSONB DEFAULT '{}'::jsonb,  -- {category: count}

    -- Timestamps
    last_trained_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, category)
);

CREATE INDEX idx_category_fluency_user ON category_fluency(user_id);
CREATE INDEX idx_category_fluency_level ON category_fluency(fluency_level);


-- ============================================================================
-- SCHEDULER STATE (HRL)
-- ============================================================================

CREATE TABLE IF NOT EXISTS scheduler_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,

    -- Session context
    available_minutes INTEGER,
    is_peak_hour BOOLEAN,

    -- Goals (JSON array of LearningGoal objects)
    active_goals JSONB DEFAULT '[]'::jsonb,
    completed_goals JSONB DEFAULT '[]'::jsonb,

    -- Session state
    atoms_seen INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    fatigue_level DECIMAL(4,3) DEFAULT 0,
    cognitive_load DECIMAL(4,3) DEFAULT 0,
    error_streak INTEGER DEFAULT 0,

    -- Rewards
    total_reward DECIMAL(8,4) DEFAULT 0,
    reward_history JSONB DEFAULT '[]'::jsonb,

    -- Timestamps
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

CREATE INDEX idx_scheduler_sessions_user ON scheduler_sessions(user_id);


-- ============================================================================
-- FORCE Z BACKTRACK EVENTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS force_z_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    session_id UUID REFERENCES scheduler_sessions(id),

    -- The attempted atom/concept
    target_atom_id UUID,
    target_concept_id UUID,
    target_concept_name VARCHAR(255),

    -- The prerequisite that was missing
    prerequisite_atom_id UUID,
    prerequisite_concept_id UUID,
    prerequisite_concept_name VARCHAR(255),
    prerequisite_mastery DECIMAL(4,3),

    -- Outcome
    backtrack_completed BOOLEAN DEFAULT FALSE,
    post_backtrack_mastery DECIMAL(4,3),

    -- Timestamps
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_force_z_user ON force_z_events(user_id);
CREATE INDEX idx_force_z_session ON force_z_events(session_id);


-- ============================================================================
-- ATOM CONNECTIONS (Knowledge Graph Edges)
-- ============================================================================

CREATE TABLE IF NOT EXISTS atom_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_atom_id UUID NOT NULL,
    target_atom_id UUID NOT NULL,

    -- Connection type
    connection_type VARCHAR(32) NOT NULL,  -- prerequisite, supports, contrasts, generalizes, etc.
    strength DECIMAL(4,3) DEFAULT 0.5,
    is_inferred BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(source_atom_id, target_atom_id, connection_type)
);

CREATE INDEX idx_atom_connections_source ON atom_connections(source_atom_id);
CREATE INDEX idx_atom_connections_target ON atom_connections(target_atom_id);
CREATE INDEX idx_atom_connections_type ON atom_connections(connection_type);


-- ============================================================================
-- TUTOR SESSIONS (Vertex AI)
-- ============================================================================

CREATE TABLE IF NOT EXISTS tutor_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    atom_id UUID,

    -- Diagnosis that triggered tutoring
    diagnosis_id UUID REFERENCES cognitive_diagnoses(id),

    -- Session data
    hint_depth INTEGER DEFAULT 0,
    scaffold_level VARCHAR(16),  -- none, minimal, moderate, heavy, full
    conversation_history JSONB DEFAULT '[]'::jsonb,

    -- Outcome
    resolved BOOLEAN DEFAULT FALSE,
    resolution_type VARCHAR(32),  -- self_solved, hint_solved, gave_up, answer_shown
    offloading_penalty DECIMAL(4,3) DEFAULT 0,

    -- Timestamps
    started_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_tutor_sessions_user ON tutor_sessions(user_id);
CREATE INDEX idx_tutor_sessions_atom ON tutor_sessions(atom_id);


-- ============================================================================
-- CALENDAR SYNC STATE
-- ============================================================================

CREATE TABLE IF NOT EXISTS calendar_sync (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) UNIQUE NOT NULL,

    -- Webhook channel
    channel_id VARCHAR(255),
    resource_id VARCHAR(255),
    channel_token VARCHAR(64),
    channel_expiration TIMESTAMPTZ,

    -- Last sync
    last_sync_at TIMESTAMPTZ,
    sync_token VARCHAR(255),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function to update learner persona after session
CREATE OR REPLACE FUNCTION update_persona_from_session(
    p_user_id VARCHAR(255),
    p_correct_by_type JSONB,
    p_incorrect_by_type JSONB,
    p_avg_response_ms INTEGER,
    p_session_duration_min INTEGER
)
RETURNS VOID AS $$
DECLARE
    alpha DECIMAL(4,3) := 0.1;
    ktype TEXT;
    correct_count INTEGER;
    incorrect_count INTEGER;
    total_count INTEGER;
    session_accuracy DECIMAL(4,3);
    current_strength DECIMAL(4,3);
    new_strength DECIMAL(4,3);
BEGIN
    -- Update each knowledge type strength
    FOR ktype IN SELECT * FROM jsonb_object_keys(p_correct_by_type) LOOP
        correct_count := (p_correct_by_type->>ktype)::INTEGER;
        incorrect_count := COALESCE((p_incorrect_by_type->>ktype)::INTEGER, 0);
        total_count := correct_count + incorrect_count;

        IF total_count > 0 THEN
            session_accuracy := correct_count::DECIMAL / total_count;

            EXECUTE format(
                'UPDATE learner_profiles SET strength_%s = strength_%s * (1 - $1) + $2 * $1, updated_at = NOW() WHERE user_id = $3',
                ktype, ktype
            ) USING alpha, session_accuracy, p_user_id;
        END IF;
    END LOOP;

    -- Update session duration
    UPDATE learner_profiles
    SET total_study_hours = total_study_hours + (p_session_duration_min::DECIMAL / 60),
        last_session_at = NOW(),
        updated_at = NOW()
    WHERE user_id = p_user_id;
END;
$$ LANGUAGE plpgsql;


-- Function to record cognitive diagnosis
CREATE OR REPLACE FUNCTION record_diagnosis(
    p_user_id VARCHAR(255),
    p_atom_id UUID,
    p_fail_mode VARCHAR(32),
    p_success_mode VARCHAR(32),
    p_cognitive_state VARCHAR(32),
    p_confidence DECIMAL(4,3),
    p_response_time_ms INTEGER,
    p_is_correct BOOLEAN,
    p_remediation_type VARCHAR(32),
    p_evidence JSONB
)
RETURNS UUID AS $$
DECLARE
    diagnosis_id UUID;
BEGIN
    INSERT INTO cognitive_diagnoses (
        user_id, atom_id, fail_mode, success_mode, cognitive_state,
        confidence, response_time_ms, is_correct, remediation_type, evidence
    ) VALUES (
        p_user_id, p_atom_id, p_fail_mode, p_success_mode, p_cognitive_state,
        p_confidence, p_response_time_ms, p_is_correct, p_remediation_type, p_evidence
    ) RETURNING id INTO diagnosis_id;

    RETURN diagnosis_id;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE learner_profiles IS 'Dynamic cognitive profiles that evolve with each learning interaction';
COMMENT ON COLUMN learner_profiles.ps_index IS 'Pattern Separation Index - hippocampal efficiency (0-1)';
COMMENT ON COLUMN learner_profiles.pfit_efficiency IS 'P-FIT Integration efficiency - reasoning ability (0-1)';
COMMENT ON COLUMN learner_profiles.calibration_score IS 'Metacognitive calibration: <0.5 underconfident, >0.5 overconfident';

COMMENT ON TABLE cognitive_diagnoses IS 'Records of cognitive diagnosis events during learning';
COMMENT ON COLUMN cognitive_diagnoses.fail_mode IS 'Type of failure: encoding, retrieval, discrimination, integration, executive, fatigue';
COMMENT ON COLUMN cognitive_diagnoses.success_mode IS 'Type of success: recall, recognition, inference, fluency';

COMMENT ON TABLE plm_sessions IS 'Perceptual Learning Module sessions for rapid pattern recognition training';
COMMENT ON COLUMN plm_sessions.fluency_achieved IS 'True if >90% accuracy with <1000ms avg response time';

COMMENT ON TABLE force_z_events IS 'Records of prerequisite backtracking (Force Z algorithm)';
COMMENT ON COLUMN force_z_events.prerequisite_mastery IS 'Mastery level of prerequisite when backtrack was triggered';

COMMENT ON TABLE atom_connections IS 'Knowledge graph edges connecting learning atoms';
COMMENT ON COLUMN atom_connections.connection_type IS 'prerequisite, supports, contrasts, generalizes, specializes, proves, applies, adversarial';
