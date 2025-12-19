-- Migration 020: Struggle Weight History + Dynamic NCDE Updates
-- Enables real-time struggle tracking as user learns

-- =============================================================================
-- STRUGGLE WEIGHT HISTORY TABLE
-- =============================================================================
-- Records every change to struggle weights for audit trail and analysis

CREATE TABLE IF NOT EXISTS struggle_weight_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_number INTEGER NOT NULL,
    section_id TEXT,

    -- Snapshot of weights at this point
    static_weight DECIMAL(3,2),         -- From YAML import
    ncde_weight DECIMAL(3,2),           -- From real-time diagnosis
    combined_priority DECIMAL(5,3),     -- Calculated priority score

    -- What triggered this update
    trigger_type TEXT NOT NULL,         -- 'ncde_diagnosis', 'yaml_import', 'manual', 'decay'
    failure_mode TEXT,                  -- Which failure mode detected (if ncde_diagnosis)
    atom_id UUID,                       -- Which atom triggered this (if ncde_diagnosis)

    -- Performance snapshot
    session_accuracy DECIMAL(3,2),      -- Accuracy in current session (0-1)
    cumulative_accuracy DECIMAL(3,2),   -- Overall accuracy for this section (0-1)
    error_count INTEGER DEFAULT 0,      -- Errors in this session for this section

    -- Session context
    session_id UUID,                    -- Link to study session if available

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX idx_swh_module ON struggle_weight_history(module_number);
CREATE INDEX idx_swh_section ON struggle_weight_history(section_id);
CREATE INDEX idx_swh_created ON struggle_weight_history(created_at DESC);
CREATE INDEX idx_swh_trigger ON struggle_weight_history(trigger_type);
CREATE INDEX idx_swh_module_time ON struggle_weight_history(module_number, created_at DESC);

-- =============================================================================
-- FAILURE MODE WEIGHT MULTIPLIERS
-- =============================================================================
-- Different failure modes indicate different severity of knowledge gaps

CREATE OR REPLACE FUNCTION get_failure_mode_multiplier(mode TEXT)
RETURNS DECIMAL(3,2) AS $$
BEGIN
    RETURN CASE mode
        -- High impact: fundamental knowledge gap
        WHEN 'encoding' THEN 0.25        -- Never consolidated - serious gap
        WHEN 'integration' THEN 0.20     -- Facts don't connect - needs scaffolding

        -- Medium impact: retrieval issues
        WHEN 'retrieval' THEN 0.15       -- Stored but can't access - needs practice
        WHEN 'discrimination' THEN 0.15  -- Confusing similar concepts - needs contrast

        -- Low impact: temporary issues
        WHEN 'executive' THEN 0.05       -- Careless error - not a knowledge gap
        WHEN 'fatigue' THEN 0.02         -- Cognitive exhaustion - not a knowledge gap

        ELSE 0.10                        -- Unknown failure mode
    END;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =============================================================================
-- MAIN UPDATE FUNCTION: Called by NCDE Pipeline
-- =============================================================================

CREATE OR REPLACE FUNCTION update_struggle_from_ncde(
    p_module INTEGER,
    p_section TEXT,
    p_failure_mode TEXT,
    p_accuracy DECIMAL,
    p_atom_id UUID DEFAULT NULL,
    p_session_id UUID DEFAULT NULL
) RETURNS void AS $$
DECLARE
    v_current_weight DECIMAL(3,2);
    v_current_ncde DECIMAL(3,2);
    v_new_ncde DECIMAL(3,2);
    v_multiplier DECIMAL(3,2);
    v_combined DECIMAL(5,3);
    v_static_weight DECIMAL(3,2);
BEGIN
    -- Get failure mode multiplier
    v_multiplier := get_failure_mode_multiplier(p_failure_mode);

    -- Get current weights
    SELECT weight, COALESCE(ncde_weight, 0.0)
    INTO v_static_weight, v_current_ncde
    FROM struggle_weights
    WHERE module_number = p_module
      AND (section_id = p_section OR (section_id IS NULL AND p_section IS NULL));

    -- If no row exists, create one
    IF NOT FOUND THEN
        INSERT INTO struggle_weights (module_number, section_id, severity, weight, ncde_weight)
        VALUES (p_module, p_section, 'medium', 0.5, 0.0);
        v_static_weight := 0.5;
        v_current_ncde := 0.0;
    END IF;

    -- Calculate new NCDE weight using exponential moving average
    -- Higher weight for errors (low accuracy), lower for correct responses
    IF p_accuracy < 0.5 THEN
        -- Error: increase weight
        v_new_ncde := LEAST(1.0, v_current_ncde + v_multiplier * (1 - p_accuracy));
    ELSE
        -- Correct: decay weight slightly
        v_new_ncde := GREATEST(0.0, v_current_ncde * 0.95);
    END IF;

    -- Calculate combined priority for history
    v_combined := v_static_weight * 3.0 + v_new_ncde * 2.0;

    -- Update struggle_weights
    UPDATE struggle_weights
    SET ncde_weight = v_new_ncde,
        last_diagnosis_at = NOW(),
        updated_at = NOW()
    WHERE module_number = p_module
      AND (section_id = p_section OR (section_id IS NULL AND p_section IS NULL));

    -- Record to history
    INSERT INTO struggle_weight_history (
        module_number,
        section_id,
        static_weight,
        ncde_weight,
        combined_priority,
        trigger_type,
        failure_mode,
        atom_id,
        session_accuracy,
        session_id
    ) VALUES (
        p_module,
        p_section,
        v_static_weight,
        v_new_ncde,
        v_combined,
        'ncde_diagnosis',
        p_failure_mode,
        p_atom_id,
        p_accuracy,
        p_session_id
    );
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- DECAY FUNCTION: Fades old struggles over time
-- =============================================================================
-- Run periodically (e.g., weekly) to prevent stale struggle weights

CREATE OR REPLACE FUNCTION decay_struggle_weights(
    p_decay_rate DECIMAL(3,2) DEFAULT 0.10,  -- 10% decay
    p_min_age_days INTEGER DEFAULT 14         -- Only decay if no activity for 14 days
) RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER := 0;
    v_row RECORD;
BEGIN
    FOR v_row IN
        SELECT id, module_number, section_id, weight, ncde_weight
        FROM struggle_weights
        WHERE ncde_weight > 0.05
          AND (last_diagnosis_at IS NULL OR last_diagnosis_at < NOW() - (p_min_age_days || ' days')::INTERVAL)
    LOOP
        -- Decay the NCDE weight
        UPDATE struggle_weights
        SET ncde_weight = GREATEST(0.0, ncde_weight * (1 - p_decay_rate)),
            updated_at = NOW()
        WHERE id = v_row.id;

        -- Record decay in history
        INSERT INTO struggle_weight_history (
            module_number,
            section_id,
            static_weight,
            ncde_weight,
            combined_priority,
            trigger_type
        ) VALUES (
            v_row.module_number,
            v_row.section_id,
            v_row.weight,
            GREATEST(0.0, v_row.ncde_weight * (1 - p_decay_rate)),
            v_row.weight * 3.0 + GREATEST(0.0, v_row.ncde_weight * (1 - p_decay_rate)) * 2.0,
            'decay'
        );

        v_count := v_count + 1;
    END LOOP;

    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- YAML IMPORT HELPER: Records import events in history
-- =============================================================================

CREATE OR REPLACE FUNCTION record_yaml_import(
    p_module INTEGER,
    p_section TEXT,
    p_severity TEXT,
    p_weight DECIMAL(3,2)
) RETURNS void AS $$
BEGIN
    -- Get current NCDE weight (preserved during import)
    INSERT INTO struggle_weight_history (
        module_number,
        section_id,
        static_weight,
        ncde_weight,
        combined_priority,
        trigger_type
    )
    SELECT
        p_module,
        p_section,
        p_weight,
        COALESCE(ncde_weight, 0.0),
        p_weight * 3.0 + COALESCE(ncde_weight, 0.0) * 2.0,
        'yaml_import'
    FROM struggle_weights
    WHERE module_number = p_module
      AND (section_id = p_section OR (section_id IS NULL AND p_section IS NULL));
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- ANALYTICS VIEW: Struggle Evolution Over Time
-- =============================================================================

CREATE OR REPLACE VIEW v_struggle_evolution AS
SELECT
    module_number,
    section_id,
    DATE_TRUNC('day', created_at) as date,
    AVG(ncde_weight) as avg_ncde_weight,
    AVG(session_accuracy) as avg_accuracy,
    COUNT(*) FILTER (WHERE trigger_type = 'ncde_diagnosis') as diagnosis_count,
    COUNT(*) FILTER (WHERE session_accuracy < 0.5) as error_count,
    COUNT(*) FILTER (WHERE session_accuracy >= 0.5) as correct_count
FROM struggle_weight_history
WHERE trigger_type = 'ncde_diagnosis'
GROUP BY module_number, section_id, DATE_TRUNC('day', created_at)
ORDER BY date DESC, module_number;

-- =============================================================================
-- SUMMARY VIEW: Current Struggle Status with History Stats
-- =============================================================================

CREATE OR REPLACE VIEW v_struggle_summary AS
SELECT
    sw.module_number,
    sw.section_id,
    sw.severity,
    sw.weight as static_weight,
    sw.ncde_weight,
    sw.weight * 3.0 + COALESCE(sw.ncde_weight, 0.0) * 2.0 as priority_score,
    sw.failure_modes,
    sw.notes,
    sw.last_diagnosis_at,
    -- History stats
    COALESCE(h.total_diagnoses, 0) as total_diagnoses,
    COALESCE(h.recent_errors, 0) as recent_errors_7d,
    COALESCE(h.avg_accuracy, 0.5) as avg_accuracy_7d,
    -- Trend indicator
    CASE
        WHEN h.trend_ncde > sw.ncde_weight THEN 'improving'
        WHEN h.trend_ncde < sw.ncde_weight THEN 'declining'
        ELSE 'stable'
    END as trend
FROM struggle_weights sw
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) as total_diagnoses,
        COUNT(*) FILTER (WHERE session_accuracy < 0.5 AND created_at > NOW() - INTERVAL '7 days') as recent_errors,
        AVG(session_accuracy) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as avg_accuracy,
        AVG(ncde_weight) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as trend_ncde
    FROM struggle_weight_history h
    WHERE h.module_number = sw.module_number
      AND (h.section_id = sw.section_id OR (h.section_id IS NULL AND sw.section_id IS NULL))
      AND h.trigger_type = 'ncde_diagnosis'
) h ON true
ORDER BY priority_score DESC;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE struggle_weight_history IS 'Audit trail of all struggle weight changes for analysis';
COMMENT ON FUNCTION update_struggle_from_ncde IS 'Called by NCDE pipeline to update struggle weights based on diagnosis';
COMMENT ON FUNCTION decay_struggle_weights IS 'Periodic function to fade old struggles (run weekly)';
COMMENT ON VIEW v_struggle_evolution IS 'Daily aggregation of struggle metrics over time';
COMMENT ON VIEW v_struggle_summary IS 'Current struggle status with 7-day trend analysis';
