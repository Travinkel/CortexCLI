-- Migration 025: Atom Response Options with Misconception Tagging
--
-- Extends the atom model to support formal response option tracking with
-- misconception linking. This enables:
--   1. Diagnostic MCQ distractors (each wrong answer reveals a specific misconception)
--   2. Psychometric item analysis (p-value, discrimination index)
--   3. Adaptive distractor selection based on learner history
--   4. Explanations per response option (not just correct/incorrect)
--
-- Key Features:
--   - Links each MCQ option to a misconception (if incorrect)
--   - Tracks selection rates and discrimination power
--   - Stores option-specific explanations for rich feedback
--   - Supports multi-select MCQ with partial credit

-- ========================================
-- ATOM RESPONSE OPTIONS
-- Structured storage for MCQ options and other discrete responses
-- ========================================

CREATE TABLE IF NOT EXISTS atom_response_option (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relationship to atom
    atom_id UUID NOT NULL REFERENCES learning_atoms(id) ON DELETE CASCADE,

    -- Option content
    option_text TEXT NOT NULL,                  -- The actual option text shown to learner
    option_index INTEGER NOT NULL,              -- Position in option list (0-based)
    option_label VARCHAR(10),                   -- Display label (A, B, C, D or 1, 2, 3, 4)

    -- Correctness
    is_correct BOOLEAN DEFAULT FALSE,
    partial_credit_weight NUMERIC(3,2) DEFAULT 0.0,  -- For multi-select: 0.0-1.0

    -- Misconception linkage (KEY FIELD for diagnostic feedback)
    misconception_id UUID REFERENCES misconception_library(id) ON DELETE SET NULL,
    misconception_strength NUMERIC(3,2) DEFAULT 1.0,  -- How strongly this option indicates the misconception (0.0-1.0)

    -- Feedback
    explanation TEXT,                           -- Why this option is correct/incorrect
    hint TEXT,                                  -- Scaffolding hint if learner selects this

    -- Psychometric tracking (updated from learner responses)
    selection_count INTEGER DEFAULT 0,          -- How many times this option was selected
    selection_rate NUMERIC(5,4),                -- p-value: proportion who select this option
    discrimination_index NUMERIC(5,4),          -- Point-biserial correlation with total score

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- Constraints
    CONSTRAINT unique_atom_option_index UNIQUE (atom_id, option_index),
    CONSTRAINT valid_partial_credit CHECK (partial_credit_weight BETWEEN 0.0 AND 1.0),
    CONSTRAINT valid_misconception_strength CHECK (misconception_strength BETWEEN 0.0 AND 1.0)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_response_option_atom ON atom_response_option(atom_id);
CREATE INDEX IF NOT EXISTS idx_response_option_misconception ON atom_response_option(misconception_id) WHERE misconception_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_response_option_correct ON atom_response_option(is_correct);

-- Update timestamp trigger
CREATE TRIGGER trigger_update_response_option_timestamp
    BEFORE UPDATE ON atom_response_option
    FOR EACH ROW
    EXECUTE FUNCTION update_misconception_timestamp();  -- Reuse existing function

-- Computed columns view for item analysis
CREATE OR REPLACE VIEW atom_option_analysis AS
SELECT
    aro.atom_id,
    aro.option_index,
    aro.option_label,
    aro.is_correct,
    aro.selection_count,
    aro.selection_rate,
    aro.discrimination_index,
    ml.misconception_code,
    ml.name AS misconception_name,
    ml.category AS misconception_category,
    ml.severity AS misconception_severity,
    -- Quality flags
    CASE
        WHEN NOT aro.is_correct AND aro.selection_rate < 0.05 THEN 'implausible_distractor'
        WHEN NOT aro.is_correct AND aro.selection_rate > 0.50 THEN 'trick_question'
        WHEN aro.discrimination_index < 0.20 THEN 'low_discrimination'
        ELSE 'acceptable'
    END AS quality_flag
FROM atom_response_option aro
LEFT JOIN misconception_library ml ON aro.misconception_id = ml.id;

-- Comments for documentation
COMMENT ON TABLE atom_response_option IS 'Structured response options for MCQ and other discrete-choice atoms with misconception tagging';
COMMENT ON COLUMN atom_response_option.misconception_id IS 'Links this (incorrect) option to a specific misconception for diagnostic feedback';
COMMENT ON COLUMN atom_response_option.misconception_strength IS 'Confidence that selecting this option indicates the linked misconception (0.0-1.0)';
COMMENT ON COLUMN atom_response_option.discrimination_index IS 'Point-biserial correlation: how well this option differentiates high/low performers';
COMMENT ON COLUMN atom_response_option.selection_rate IS 'Proportion of learners who selected this option (p-value for distractors)';
