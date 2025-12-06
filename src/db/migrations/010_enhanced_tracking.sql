-- Migration 010: Enhanced Progress Tracking
-- Adds atom_type to atom_responses for per-type quiz analytics

-- Add atom_type column to track which type of quiz was answered
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'atom_responses' AND column_name = 'atom_type') THEN
        ALTER TABLE atom_responses ADD COLUMN atom_type VARCHAR(20);
    END IF;
END $$;

-- Index for efficient type-based queries
CREATE INDEX IF NOT EXISTS idx_atom_responses_atom_type ON atom_responses(atom_type);

-- Add bloom_level and clt_load columns to clean_atoms if not present
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'bloom_level') THEN
        ALTER TABLE clean_atoms ADD COLUMN bloom_level VARCHAR(20);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'clt_load') THEN
        ALTER TABLE clean_atoms ADD COLUMN clt_load VARCHAR(20);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'quality_score') THEN
        ALTER TABLE clean_atoms ADD COLUMN quality_score DECIMAL(5,4) DEFAULT 0;
    END IF;
END $$;

-- View: Quiz responses by type with aggregations
CREATE OR REPLACE VIEW v_quiz_responses_by_type AS
SELECT
    ar.user_id,
    ar.atom_type,
    COUNT(*) as total_responses,
    SUM(CASE WHEN ar.is_correct THEN 1 ELSE 0 END) as correct_count,
    SUM(CASE WHEN NOT ar.is_correct THEN 1 ELSE 0 END) as incorrect_count,
    ROUND(AVG(CASE WHEN ar.is_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as accuracy_percent,
    AVG(ar.response_time_ms) as avg_response_time_ms,
    MAX(ar.responded_at) as last_response_at
FROM atom_responses ar
WHERE ar.atom_type IS NOT NULL
GROUP BY ar.user_id, ar.atom_type;

COMMENT ON VIEW v_quiz_responses_by_type IS 'Aggregated quiz performance by atom type (mcq, true_false, matching, parsons)';

-- View: Session performance breakdown
CREATE OR REPLACE VIEW v_session_performance AS
SELECT
    ps.id as session_id,
    ps.user_id,
    ps.started_at,
    ps.ended_at,
    ps.actual_minutes,
    ps.pomodoros_completed,
    ps.anki_cards_reviewed,
    ps.mcq_answered,
    ps.true_false_answered,
    ps.matching_answered,
    ps.parsons_answered,
    (ps.mcq_answered + ps.true_false_answered + ps.matching_answered + ps.parsons_answered) as total_quiz_answered,
    ps.total_correct,
    ps.total_incorrect,
    CASE
        WHEN (ps.total_correct + ps.total_incorrect) > 0
        THEN ROUND((ps.total_correct::DECIMAL / (ps.total_correct + ps.total_incorrect)) * 100, 1)
        ELSE 0
    END as session_accuracy,
    ps.focus_module,
    ps.focus_section_id
FROM pomodoro_sessions ps
ORDER BY ps.started_at DESC;

COMMENT ON VIEW v_session_performance IS 'Session performance summary with quiz breakdown';
