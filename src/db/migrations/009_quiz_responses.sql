-- Migration 009: Quiz Responses and Pomodoro Sessions
-- Tracks in-app quiz responses for MCQ, True/False, Matching, Parsons
-- These atom types are presented IN NLS, not sent to Anki

-- Table for tracking quiz responses (non-Anki atoms)
CREATE TABLE IF NOT EXISTS atom_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    atom_id UUID NOT NULL,  -- References clean_atoms.id
    user_id VARCHAR(100) NOT NULL DEFAULT 'default',
    is_correct BOOLEAN NOT NULL,
    response_time_ms INTEGER,
    user_answer TEXT,
    responded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Session tracking
    session_id UUID,
    pomodoro_number INTEGER,

    -- FSRS-style metrics for non-Anki atoms
    -- We track these ourselves since these atoms don't go to Anki
    streak_before INTEGER DEFAULT 0,
    streak_after INTEGER DEFAULT 0,

    CONSTRAINT fk_atom FOREIGN KEY (atom_id) REFERENCES clean_atoms(id) ON DELETE CASCADE
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_atom_responses_atom_id ON atom_responses(atom_id);
CREATE INDEX IF NOT EXISTS idx_atom_responses_user_id ON atom_responses(user_id);
CREATE INDEX IF NOT EXISTS idx_atom_responses_session_id ON atom_responses(session_id);
CREATE INDEX IF NOT EXISTS idx_atom_responses_responded_at ON atom_responses(responded_at);

-- Table for Pomodoro study sessions
CREATE TABLE IF NOT EXISTS pomodoro_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100) NOT NULL DEFAULT 'default',

    -- Session timing
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    planned_hours DECIMAL(4,2),
    actual_minutes INTEGER,

    -- Pomodoro tracking
    pomodoros_completed INTEGER DEFAULT 0,
    pomodoros_planned INTEGER DEFAULT 0,

    -- Content breakdown
    anki_cards_reviewed INTEGER DEFAULT 0,
    mcq_answered INTEGER DEFAULT 0,
    true_false_answered INTEGER DEFAULT 0,
    matching_answered INTEGER DEFAULT 0,
    parsons_answered INTEGER DEFAULT 0,

    -- Performance
    total_correct INTEGER DEFAULT 0,
    total_incorrect INTEGER DEFAULT 0,

    -- Focus tracking
    focus_section_id VARCHAR(20),  -- CCNA section being studied
    focus_module INTEGER,

    -- Notes
    session_notes TEXT
);

-- Index for session history
CREATE INDEX IF NOT EXISTS idx_pomodoro_sessions_user_id ON pomodoro_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_pomodoro_sessions_started_at ON pomodoro_sessions(started_at);

-- Add FSRS columns to clean_atoms if not present (for Anki sync)
DO $$
BEGIN
    -- Anki sync columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'anki_note_id') THEN
        ALTER TABLE clean_atoms ADD COLUMN anki_note_id BIGINT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'anki_interval') THEN
        ALTER TABLE clean_atoms ADD COLUMN anki_interval INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'anki_ease_factor') THEN
        ALTER TABLE clean_atoms ADD COLUMN anki_ease_factor DECIMAL(5,3) DEFAULT 2.5;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'anki_review_count') THEN
        ALTER TABLE clean_atoms ADD COLUMN anki_review_count INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'anki_lapses') THEN
        ALTER TABLE clean_atoms ADD COLUMN anki_lapses INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'anki_stability') THEN
        ALTER TABLE clean_atoms ADD COLUMN anki_stability DECIMAL(10,4) DEFAULT 1.0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'anki_difficulty') THEN
        ALTER TABLE clean_atoms ADD COLUMN anki_difficulty DECIMAL(5,4) DEFAULT 0.5;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'anki_queue') THEN
        ALTER TABLE clean_atoms ADD COLUMN anki_queue INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'anki_due_date') THEN
        ALTER TABLE clean_atoms ADD COLUMN anki_due_date DATE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'anki_synced_at') THEN
        ALTER TABLE clean_atoms ADD COLUMN anki_synced_at TIMESTAMP WITH TIME ZONE;
    END IF;

    -- In-app quiz tracking columns (for non-Anki atoms)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'nls_correct_count') THEN
        ALTER TABLE clean_atoms ADD COLUMN nls_correct_count INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'nls_incorrect_count') THEN
        ALTER TABLE clean_atoms ADD COLUMN nls_incorrect_count INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'nls_streak') THEN
        ALTER TABLE clean_atoms ADD COLUMN nls_streak INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'nls_last_response') THEN
        ALTER TABLE clean_atoms ADD COLUMN nls_last_response TIMESTAMP WITH TIME ZONE;
    END IF;
END $$;

-- Function to update atom stats after quiz response
CREATE OR REPLACE FUNCTION update_atom_quiz_stats()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_correct THEN
        UPDATE clean_atoms SET
            nls_correct_count = COALESCE(nls_correct_count, 0) + 1,
            nls_streak = COALESCE(nls_streak, 0) + 1,
            nls_last_response = NEW.responded_at
        WHERE id = NEW.atom_id;
    ELSE
        UPDATE clean_atoms SET
            nls_incorrect_count = COALESCE(nls_incorrect_count, 0) + 1,
            nls_streak = 0,  -- Reset streak on wrong answer
            nls_last_response = NEW.responded_at
        WHERE id = NEW.atom_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update stats
DROP TRIGGER IF EXISTS trg_update_atom_quiz_stats ON atom_responses;
CREATE TRIGGER trg_update_atom_quiz_stats
    AFTER INSERT ON atom_responses
    FOR EACH ROW
    EXECUTE FUNCTION update_atom_quiz_stats();

-- View for atom mastery (combines Anki and NLS data)
CREATE OR REPLACE VIEW v_atom_mastery AS
SELECT
    ca.id,
    ca.card_id,
    ca.atom_type,
    ca.front,
    ca.ccna_section_id,
    cs.module_number,
    cs.title as section_title,

    -- Anki metrics (for flashcard/cloze)
    ca.anki_interval,
    ca.anki_stability,
    ca.anki_difficulty,
    ca.anki_review_count,
    ca.anki_lapses,

    -- NLS metrics (for mcq/true_false/matching/parsons)
    ca.nls_correct_count,
    ca.nls_incorrect_count,
    ca.nls_streak,

    -- Combined mastery score
    CASE
        WHEN ca.atom_type IN ('flashcard', 'cloze') THEN
            -- Use Anki stability for flashcard/cloze
            LEAST(100, ca.anki_stability * 10)
        ELSE
            -- Use correct ratio for quiz types
            CASE
                WHEN COALESCE(ca.nls_correct_count, 0) + COALESCE(ca.nls_incorrect_count, 0) = 0 THEN 0
                ELSE (ca.nls_correct_count::DECIMAL /
                      (ca.nls_correct_count + ca.nls_incorrect_count)) * 100
            END
    END as mastery_score,

    -- Status
    CASE
        WHEN ca.atom_type IN ('flashcard', 'cloze') THEN
            CASE
                WHEN ca.anki_review_count IS NULL OR ca.anki_review_count = 0 THEN 'new'
                WHEN ca.anki_stability >= 30 THEN 'mastered'
                WHEN ca.anki_lapses > 2 THEN 'struggling'
                ELSE 'learning'
            END
        ELSE
            CASE
                WHEN COALESCE(ca.nls_correct_count, 0) + COALESCE(ca.nls_incorrect_count, 0) = 0 THEN 'new'
                WHEN ca.nls_streak >= 3 THEN 'mastered'
                WHEN ca.nls_incorrect_count > ca.nls_correct_count THEN 'struggling'
                ELSE 'learning'
            END
    END as status

FROM clean_atoms ca
LEFT JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id;

COMMENT ON VIEW v_atom_mastery IS 'Combined mastery view for all atom types (Anki and NLS)';
