-- Migration 026: Learner Error Log
--
-- Comprehensive error tracking for cognitive diagnosis and adaptive remediation.
-- This table captures every learner error with rich diagnostic metadata to enable:
--   1. Error classification (syntax, semantic, logical, conceptual)
--   2. Misconception detection from free-response answers
--   3. Confidence-accuracy mismatch tracking (hypercorrection opportunities)
--   4. Automated remediation atom generation
--   5. Longitudinal error pattern analysis
--
-- Key Features:
--   - Links errors to specific misconceptions when detected
--   - Tracks attempt sequences and retry patterns
--   - Captures confidence ratings for calibration analysis
--   - Stores remediation atoms recommended/completed
--   - Enables error clustering and pattern detection

-- ========================================
-- LEARNER ERROR LOG
-- Diagnostic tracking of all learner errors
-- ========================================

CREATE TABLE IF NOT EXISTS learner_error_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Who and what
    learner_id UUID NOT NULL,                   -- Foreign key to learner (if auth system exists)
    atom_id UUID NOT NULL REFERENCES learning_atoms(id) ON DELETE CASCADE,
    session_id UUID,                            -- Links to study session for context

    -- Error details
    submitted_answer TEXT,                      -- What the learner actually answered
    correct_answer TEXT,                        -- What the correct answer was

    -- Error classification
    error_type VARCHAR(50),                     -- syntax, semantic, logical, conceptual, slip, missing_prerequisite
    error_class VARCHAR(50),                    -- misconception, slip, missing_prerequisite, execution_failure
    misconception_triggered UUID REFERENCES misconception_library(id) ON DELETE SET NULL,

    -- Attempt context
    attempt_number INTEGER DEFAULT 1,           -- Which attempt (1, 2, 3...)
    time_on_task_ms INTEGER,                    -- How long learner spent before answering

    -- Meta-cognitive data
    confidence_rating INTEGER CHECK (confidence_rating BETWEEN 1 AND 5),
    perceived_difficulty INTEGER CHECK (perceived_difficulty BETWEEN 1 AND 5),

    -- Outcome
    was_corrected BOOLEAN DEFAULT FALSE,        -- Did learner eventually get it right?
    correction_attempt INTEGER,                 -- On which attempt did they succeed?

    -- Remediation
    remediation_atoms UUID[],                   -- Array of atom IDs recommended for remediation
    remediation_completed BOOLEAN DEFAULT FALSE,

    -- Cognitive signals (computed from latency + correctness)
    cognitive_signal VARCHAR(30),               -- fast_correct, fast_wrong, slow_correct, slow_wrong

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT now(),

    -- Constraints
    CONSTRAINT valid_confidence CHECK (confidence_rating IS NULL OR confidence_rating BETWEEN 1 AND 5),
    CONSTRAINT valid_difficulty CHECK (perceived_difficulty IS NULL OR perceived_difficulty BETWEEN 1 AND 5)
);

-- Indexes for analytics queries
CREATE INDEX IF NOT EXISTS idx_error_log_learner ON learner_error_log(learner_id);
CREATE INDEX IF NOT EXISTS idx_error_log_atom ON learner_error_log(atom_id);
CREATE INDEX IF NOT EXISTS idx_error_log_misconception ON learner_error_log(misconception_triggered) WHERE misconception_triggered IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_error_log_session ON learner_error_log(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_error_log_created ON learner_error_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_error_log_error_type ON learner_error_log(error_type);

-- View: High-confidence errors (hypercorrection opportunities)
CREATE OR REPLACE VIEW hypercorrection_opportunities AS
SELECT
    lel.id,
    lel.learner_id,
    lel.atom_id,
    lel.submitted_answer,
    lel.correct_answer,
    lel.confidence_rating,
    lel.misconception_triggered,
    ml.name AS misconception_name,
    ml.remediation_strategy,
    la.front AS atom_question,
    lel.created_at
FROM learner_error_log lel
LEFT JOIN misconception_library ml ON lel.misconception_triggered = ml.id
LEFT JOIN learning_atoms la ON lel.atom_id = la.id
WHERE lel.confidence_rating >= 4  -- High confidence
  AND lel.was_corrected = FALSE;   -- Still wrong

-- View: Error patterns by misconception
CREATE OR REPLACE VIEW misconception_prevalence AS
SELECT
    ml.misconception_code,
    ml.name AS misconception_name,
    ml.domain,
    ml.severity,
    COUNT(DISTINCT lel.learner_id) AS learners_affected,
    COUNT(lel.id) AS total_occurrences,
    AVG(lel.confidence_rating) AS avg_confidence_when_wrong,
    AVG(lel.time_on_task_ms) / 1000.0 AS avg_time_on_task_sec,
    SUM(CASE WHEN lel.was_corrected THEN 1 ELSE 0 END)::NUMERIC / COUNT(lel.id) AS correction_rate
FROM misconception_library ml
LEFT JOIN learner_error_log lel ON ml.id = lel.misconception_triggered
WHERE lel.id IS NOT NULL
GROUP BY ml.id, ml.misconception_code, ml.name, ml.domain, ml.severity
ORDER BY learners_affected DESC;

-- View: Learner struggle zones
CREATE OR REPLACE VIEW learner_struggle_zones AS
SELECT
    lel.learner_id,
    la.module_id,
    ml.domain,
    ml.misconception_code,
    COUNT(lel.id) AS error_count,
    AVG(lel.attempt_number) AS avg_attempts,
    SUM(CASE WHEN lel.was_corrected = FALSE THEN 1 ELSE 0 END) AS unresolved_errors,
    MAX(lel.created_at) AS last_error_at
FROM learner_error_log lel
LEFT JOIN learning_atoms la ON lel.atom_id = la.id
LEFT JOIN misconception_library ml ON lel.misconception_triggered = ml.id
GROUP BY lel.learner_id, la.module_id, ml.domain, ml.misconception_code
HAVING COUNT(lel.id) >= 2  -- At least 2 errors in this pattern
ORDER BY error_count DESC;

-- Comments for documentation
COMMENT ON TABLE learner_error_log IS 'Comprehensive error tracking for cognitive diagnosis and adaptive remediation';
COMMENT ON COLUMN learner_error_log.error_type IS 'Technical classification: syntax, semantic, logical, conceptual, slip, missing_prerequisite';
COMMENT ON COLUMN learner_error_log.error_class IS 'Cognitive classification: misconception (fundamental), slip (minor), missing_prerequisite, execution_failure';
COMMENT ON COLUMN learner_error_log.cognitive_signal IS 'Latency + correctness pattern: fast_correct, fast_wrong (guessing), slow_correct (effortful), slow_wrong (overload)';
COMMENT ON COLUMN learner_error_log.misconception_triggered IS 'Links to the specific misconception this error revealed (if identifiable)';
COMMENT ON COLUMN learner_error_log.remediation_atoms IS 'Array of atom IDs recommended to address this error';
