-- Migration: 018_dynamic_struggle_weights.sql
-- Created: 2025-12-15

-- This migration introduces tables for dynamic, performance-based struggle tracking,
-- moving away from the static struggles.yaml file.

-- =============================================================================
-- 1. struggle_weights: Main table for tracking struggle scores
-- =============================================================================
CREATE TABLE IF NOT EXISTS struggle_weights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL DEFAULT 'default',
    module_number INTEGER NOT NULL,
    section_id VARCHAR(20), -- Null for module-level weights
    weight FLOAT NOT NULL DEFAULT 0.3,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    last_failure_mode VARCHAR(50),
    consecutive_failures INTEGER DEFAULT 0,
    total_interactions INTEGER DEFAULT 0,
    correct_interactions INTEGER DEFAULT 0,

    UNIQUE(user_id, module_number, section_id)
);

COMMENT ON TABLE struggle_weights IS 'Tracks dynamic struggle weights for modules and sections based on user performance.';
COMMENT ON COLUMN struggle_weights.weight IS 'Struggle score (0.0 to 1.0). Higher means more struggle.';
COMMENT ON COLUMN struggle_weights.last_failure_mode IS 'The last diagnosed cognitive failure mode for this area.';
COMMENT ON COLUMN struggle_weights.consecutive_failures IS 'Counter for consecutive incorrect answers in this area.';

-- =============================================================================
-- 2. struggle_weight_history: Log of all changes to struggle weights
-- =============================================================================
CREATE TABLE IF NOT EXISTS struggle_weight_history (
    id BIGSERIAL PRIMARY KEY,
    weight_id UUID REFERENCES struggle_weights(id) ON DELETE CASCADE,
    change_timestamp TIMESTAMPTZ DEFAULT NOW(),
    old_weight FLOAT,
    new_weight FLOAT NOT NULL,
    reason VARCHAR(255), -- e.g., "INCORRECT_ANSWER", "CORRECT_ANSWER", "YAML_IMPORT"
    atom_id UUID,
    session_id UUID
);

COMMENT ON TABLE struggle_weight_history IS 'Logs all changes to struggle weights for analytics and debugging.';

-- =============================================================================
-- 3. PostgreSQL Function to update struggle weights from NCDE
-- =============================================================================
CREATE OR REPLACE FUNCTION update_struggle_from_ncde(
    p_user_id VARCHAR,
    p_module_number INTEGER,
    p_section_id VARCHAR,
    p_failure_mode VARCHAR,
    p_accuracy FLOAT, -- 1.0 for correct, 0.0 for incorrect
    p_atom_id UUID,
    p_session_id UUID
)
RETURNS VOID AS $$
DECLARE
    v_weight_id UUID;
    v_old_weight FLOAT;
    v_new_weight FLOAT;
    v_consecutive_failures INTEGER;
    v_change_reason VARCHAR;
BEGIN
    -- Find or create the struggle weight entry
    SELECT id, weight, consecutive_failures
    INTO v_weight_id, v_old_weight, v_consecutive_failures
    FROM struggle_weights
    WHERE user_id = p_user_id
      AND module_number = p_module_number
      AND (section_id = p_section_id OR (section_id IS NULL AND p_section_id IS NULL));

    IF NOT FOUND THEN
        INSERT INTO struggle_weights (user_id, module_number, section_id)
        VALUES (p_user_id, p_module_number, p_section_id)
        RETURNING id, weight, consecutive_failures INTO v_weight_id, v_old_weight, v_consecutive_failures;
    END IF;

    -- Calculate new weight based on performance
    IF p_accuracy = 1.0 THEN
        -- Correct answer: decrease struggle weight
        v_new_weight := v_old_weight * 0.95;
        v_consecutive_failures := 0;
        v_change_reason := 'CORRECT_ANSWER';
    ELSE
        -- Incorrect answer: increase struggle weight
        -- Increase is larger for consecutive failures
        v_consecutive_failures := v_consecutive_failures + 1;
        v_new_weight := v_old_weight + (0.1 * v_consecutive_failures);
        v_change_reason := 'INCORRECT_ANSWER';
    END IF;

    -- Clamp weight between 0.1 and 1.0
    v_new_weight := LEAST(1.0, GREATEST(0.1, v_new_weight));

    -- Update the struggle_weights table
    UPDATE struggle_weights
    SET
        weight = v_new_weight,
        last_updated = NOW(),
        last_failure_mode = p_failure_mode,
        consecutive_failures = v_consecutive_failures,
        total_interactions = total_interactions + 1,
        correct_interactions = correct_interactions + (CASE WHEN p_accuracy = 1.0 THEN 1 ELSE 0 END)
    WHERE id = v_weight_id;

    -- Log the change in history
    INSERT INTO struggle_weight_history (weight_id, old_weight, new_weight, reason, atom_id, session_id)
    VALUES (v_weight_id, v_old_weight, v_new_weight, v_change_reason, p_atom_id, p_session_id);

END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_struggle_from_ncde IS 'Updates struggle weights based on cognitive diagnosis from a single interaction.';

-- =============================================================================
-- 4. View for prioritizing atoms based on struggle weights
-- =============================================================================
CREATE OR REPLACE VIEW v_struggle_priority AS
SELECT
    la.id as atom_id,
    la.card_id,
    la.atom_type,
    la.front,
    la.back,
    cs.section_id,
    cs.module_number,
    cs.title as section_title,
    sw.weight as struggle_weight,
    la.anki_difficulty as difficulty,
    la.anki_stability as stability,
    -- Priority score: combination of struggle, low stability, and recency
    (sw.weight * 2.0) + (1.0 - LEAST(la.anki_stability / 30.0, 1.0)) + (1.0 / (1 + EXTRACT(EPOCH FROM (NOW() - la.updated_at))/86400)) as priority_score
FROM
    learning_atoms la
JOIN
    ccna_sections cs ON la.ccna_section_id = cs.section_id
JOIN
    struggle_weights sw ON sw.module_number = cs.module_number AND (sw.section_id IS NULL OR sw.section_id = cs.section_id)
WHERE
    sw.user_id = 'default';

COMMENT ON VIEW v_struggle_priority IS 'Provides a prioritized list of atoms for study, weighted by struggle scores.';

-- =============================================================================
-- End of migration
-- =============================================================================
