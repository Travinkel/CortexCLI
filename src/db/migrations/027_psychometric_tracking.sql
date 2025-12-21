-- Migration 027: Psychometric Tracking Fields
--
-- Adds Item Response Theory (IRT) and psychometric analysis fields to the
-- learning_atoms table. This enables:
--   1. Difficulty calibration via IRT (theta parameter estimation)
--   2. Item quality analysis (discrimination, guessing parameter)
--   3. Adaptive difficulty selection
--   4. Detection of problematic items (too easy, too hard, low discrimination)
--   5. A/B testing of item variants
--
-- Key Features:
--   - IRT difficulty parameter (b-parameter, aka theta)
--   - Discrimination index (a-parameter, point-biserial correlation)
--   - Guessing parameter (c-parameter, for MCQ baseline probability)
--   - Response count tracking for statistical confidence
--   - Item quality flags (needs_review, retired, validated)

-- ========================================
-- PSYCHOMETRIC TRACKING
-- Add IRT and item analysis fields to learning_atoms
-- ========================================

-- Add psychometric columns to learning_atoms table
ALTER TABLE learning_atoms
ADD COLUMN IF NOT EXISTS irt_difficulty NUMERIC(5,3),           -- IRT b-parameter (-3.0 to +3.0, 0 = average)
ADD COLUMN IF NOT EXISTS irt_discrimination NUMERIC(5,3),       -- IRT a-parameter (0.0 to 3.0+, >1.0 = good)
ADD COLUMN IF NOT EXISTS irt_guessing NUMERIC(4,3),             -- IRT c-parameter (0.0 to 1.0, baseline prob)
ADD COLUMN IF NOT EXISTS p_value NUMERIC(5,4),                  -- Classical Test Theory difficulty (0.0-1.0, proportion correct)
ADD COLUMN IF NOT EXISTS discrimination_index NUMERIC(5,4),     -- Point-biserial correlation (-1.0 to +1.0)
ADD COLUMN IF NOT EXISTS response_count INTEGER DEFAULT 0,       -- Number of learner responses
ADD COLUMN IF NOT EXISTS correct_count INTEGER DEFAULT 0,        -- Number of correct responses
ADD COLUMN IF NOT EXISTS median_latency_ms INTEGER,             -- Median time-on-task
ADD COLUMN IF NOT EXISTS item_quality_flag VARCHAR(30);         -- needs_review, validated, retired, pilot

-- Add constraints
ALTER TABLE learning_atoms
ADD CONSTRAINT check_irt_difficulty CHECK (irt_difficulty IS NULL OR irt_difficulty BETWEEN -3.0 AND 3.0),
ADD CONSTRAINT check_irt_discrimination CHECK (irt_discrimination IS NULL OR irt_discrimination >= 0.0),
ADD CONSTRAINT check_irt_guessing CHECK (irt_guessing IS NULL OR irt_guessing BETWEEN 0.0 AND 1.0),
ADD CONSTRAINT check_p_value CHECK (p_value IS NULL OR p_value BETWEEN 0.0 AND 1.0),
ADD CONSTRAINT check_discrimination_index CHECK (discrimination_index IS NULL OR discrimination_index BETWEEN -1.0 AND 1.0);

-- Index for difficulty-based selection
CREATE INDEX IF NOT EXISTS idx_atoms_irt_difficulty ON learning_atoms(irt_difficulty) WHERE irt_difficulty IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_atoms_quality_flag ON learning_atoms(item_quality_flag);
CREATE INDEX IF NOT EXISTS idx_atoms_response_count ON learning_atoms(response_count);

-- View: Item quality dashboard
CREATE OR REPLACE VIEW item_quality_dashboard AS
SELECT
    la.id,
    la.atom_type,
    la.module_id,
    la.front,
    la.p_value,
    la.discrimination_index,
    la.irt_difficulty,
    la.irt_discrimination,
    la.response_count,
    la.correct_count,
    la.item_quality_flag,

    -- Quality assessment
    CASE
        WHEN la.response_count < 30 THEN 'insufficient_data'
        WHEN la.p_value IS NOT NULL AND la.p_value < 0.20 THEN 'too_hard'
        WHEN la.p_value IS NOT NULL AND la.p_value > 0.90 THEN 'too_easy'
        WHEN la.discrimination_index IS NOT NULL AND la.discrimination_index < 0.20 THEN 'low_discrimination'
        WHEN la.discrimination_index IS NOT NULL AND la.discrimination_index >= 0.30 AND la.p_value BETWEEN 0.40 AND 0.80 THEN 'excellent'
        WHEN la.discrimination_index IS NOT NULL AND la.discrimination_index >= 0.20 THEN 'acceptable'
        ELSE 'needs_analysis'
    END AS auto_quality_rating,

    -- Recommended action
    CASE
        WHEN la.response_count < 30 THEN 'continue_piloting'
        WHEN la.p_value < 0.20 OR la.p_value > 0.90 THEN 'adjust_difficulty'
        WHEN la.discrimination_index < 0.20 THEN 'revise_or_retire'
        WHEN la.discrimination_index >= 0.30 AND la.p_value BETWEEN 0.40 AND 0.80 THEN 'approve_for_production'
        ELSE 'review_manually'
    END AS recommended_action

FROM learning_atoms la
ORDER BY la.response_count DESC, la.discrimination_index DESC;

-- View: Atoms needing review
CREATE OR REPLACE VIEW atoms_needing_review AS
SELECT
    la.id,
    la.atom_type,
    la.module_id,
    la.front,
    la.p_value,
    la.discrimination_index,
    la.response_count,
    CASE
        WHEN la.response_count < 30 THEN 'Need more pilot data (n=' || la.response_count || ')'
        WHEN la.p_value < 0.20 THEN 'Too difficult (p=' || ROUND(la.p_value::numeric, 2) || ')'
        WHEN la.p_value > 0.90 THEN 'Too easy (p=' || ROUND(la.p_value::numeric, 2) || ')'
        WHEN la.discrimination_index < 0.20 THEN 'Low discrimination (r=' || ROUND(la.discrimination_index::numeric, 2) || ')'
        ELSE 'Unknown issue'
    END AS issue_description
FROM learning_atoms la
WHERE
    la.response_count < 30
    OR la.p_value < 0.20
    OR la.p_value > 0.90
    OR la.discrimination_index < 0.20
ORDER BY
    CASE
        WHEN la.discrimination_index < 0.10 THEN 1  -- Worst first
        WHEN la.p_value < 0.10 OR la.p_value > 0.95 THEN 2
        WHEN la.response_count < 10 THEN 3
        ELSE 4
    END,
    la.response_count ASC;

-- Function: Update p-value and discrimination index from responses
CREATE OR REPLACE FUNCTION update_atom_psychometrics()
RETURNS TRIGGER AS $$
BEGIN
    -- Update p-value (proportion correct)
    UPDATE learning_atoms
    SET
        response_count = (SELECT COUNT(*) FROM learner_error_log WHERE atom_id = NEW.atom_id) +
                         (SELECT COUNT(*) FROM atom_reviews WHERE atom_id = NEW.atom_id),
        correct_count = (SELECT COUNT(*) FROM atom_reviews WHERE atom_id = NEW.atom_id AND rating >= 3),
        p_value = (
            SELECT
                COUNT(CASE WHEN rating >= 3 THEN 1 END)::NUMERIC /
                NULLIF(COUNT(*), 0)
            FROM atom_reviews
            WHERE atom_id = NEW.atom_id
        )
    WHERE id = NEW.atom_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update psychometrics when responses come in
-- Note: This assumes atom_reviews table exists (from earlier migrations)
-- If it doesn't exist yet, this trigger will fail gracefully
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'atom_reviews') THEN
        CREATE TRIGGER trigger_update_atom_psychometrics
            AFTER INSERT OR UPDATE ON atom_reviews
            FOR EACH ROW
            EXECUTE FUNCTION update_atom_psychometrics();
    END IF;
END $$;

-- Comments for documentation
COMMENT ON COLUMN learning_atoms.irt_difficulty IS 'IRT b-parameter: item difficulty on standardized scale (-3 to +3, 0 = average)';
COMMENT ON COLUMN learning_atoms.irt_discrimination IS 'IRT a-parameter: how well item differentiates high/low ability learners (>1.0 = good)';
COMMENT ON COLUMN learning_atoms.irt_guessing IS 'IRT c-parameter: baseline probability of correct answer by guessing (0.0-1.0)';
COMMENT ON COLUMN learning_atoms.p_value IS 'Classical Test Theory difficulty: proportion of learners who answer correctly (0.0-1.0)';
COMMENT ON COLUMN learning_atoms.discrimination_index IS 'Point-biserial correlation between item and total score (-1.0 to +1.0, >0.30 = excellent)';
COMMENT ON COLUMN learning_atoms.response_count IS 'Total number of learner responses to this atom';
COMMENT ON COLUMN learning_atoms.item_quality_flag IS 'Quality status: pilot, validated, needs_review, retired';

-- Initial data: Set all existing atoms to 'needs_review' if they have responses
UPDATE learning_atoms
SET item_quality_flag = 'needs_review'
WHERE response_count > 0 AND item_quality_flag IS NULL;

-- Set atoms with no responses to 'pilot'
UPDATE learning_atoms
SET item_quality_flag = 'pilot'
WHERE response_count = 0 AND item_quality_flag IS NULL;
