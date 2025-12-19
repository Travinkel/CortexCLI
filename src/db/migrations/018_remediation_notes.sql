-- Migration 018: Remediation Notes System
-- Supports LLM-generated study notes with quality tracking

-- Remediation notes table
CREATE TABLE IF NOT EXISTS remediation_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id VARCHAR(20) NOT NULL,
    module_number INTEGER NOT NULL,

    -- Content
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,  -- Markdown
    source_hash VARCHAR(64),  -- SHA256 of source material used

    -- Quality metrics
    read_count INTEGER DEFAULT 0,
    user_rating INTEGER CHECK (user_rating BETWEEN 1 AND 5),
    pre_error_rate FLOAT,  -- Error rate before reading
    post_error_rate FLOAT,  -- Error rate after reading
    effectiveness FLOAT GENERATED ALWAYS AS (
        CASE WHEN pre_error_rate IS NOT NULL AND post_error_rate IS NOT NULL
        THEN pre_error_rate - post_error_rate
        ELSE NULL END
    ) STORED,

    -- Gating
    qualified BOOLEAN DEFAULT TRUE,
    is_stale BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    last_read_at TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '30 days'),

    -- Constraints
    UNIQUE(section_id)
);

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_remediation_notes_section ON remediation_notes(section_id);
CREATE INDEX IF NOT EXISTS idx_remediation_notes_qualified ON remediation_notes(qualified, is_stale);
CREATE INDEX IF NOT EXISTS idx_remediation_notes_module ON remediation_notes(module_number);

-- Note read history (for tracking effectiveness)
CREATE TABLE IF NOT EXISTS note_read_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id UUID REFERENCES remediation_notes(id) ON DELETE CASCADE,
    user_id VARCHAR(100) DEFAULT 'default',
    read_at TIMESTAMP DEFAULT NOW(),
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),

    -- Error rates at time of reading
    section_error_rate_before FLOAT,
    section_error_rate_after FLOAT  -- Updated after next session
);

CREATE INDEX IF NOT EXISTS idx_note_read_history_note ON note_read_history(note_id);
CREATE INDEX IF NOT EXISTS idx_note_read_history_user ON note_read_history(user_id);

-- Track "I don't know" responses separately from wrong answers
ALTER TABLE learning_atoms
ADD COLUMN IF NOT EXISTS dont_know_count INTEGER DEFAULT 0;

-- Add response_type to track different answer types
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'response_type') THEN
        CREATE TYPE response_type AS ENUM ('correct', 'incorrect', 'dont_know', 'skipped', 'timeout');
    END IF;
END$$;

-- View for sections needing remediation notes
CREATE OR REPLACE VIEW v_sections_needing_notes AS
SELECT
    la.ccna_section_id as section_id,
    cs.module_number,
    cs.title as section_title,
    COUNT(*) as total_atoms,
    COUNT(*) FILTER (WHERE la.anki_lapses > 0 OR la.dont_know_count > 0) as struggling_atoms,
    AVG(la.anki_lapses) as avg_lapses,
    SUM(la.dont_know_count) as total_dont_knows,
    rn.id as existing_note_id,
    rn.qualified as note_qualified,
    rn.is_stale as note_stale,
    rn.last_read_at
FROM learning_atoms la
JOIN ccna_sections cs ON la.ccna_section_id = cs.section_id
LEFT JOIN remediation_notes rn ON la.ccna_section_id = rn.section_id
WHERE la.ccna_section_id IS NOT NULL
GROUP BY la.ccna_section_id, cs.module_number, cs.title, rn.id, rn.qualified, rn.is_stale, rn.last_read_at
HAVING COUNT(*) FILTER (WHERE la.anki_lapses > 0 OR la.dont_know_count > 0) > 0
   OR SUM(la.dont_know_count) > 0
ORDER BY SUM(la.dont_know_count) DESC, AVG(la.anki_lapses) DESC;

COMMENT ON TABLE remediation_notes IS 'LLM-generated study notes for weak sections';
COMMENT ON TABLE note_read_history IS 'Tracks when notes were read and their effectiveness';
COMMENT ON VIEW v_sections_needing_notes IS 'Sections with struggles that may need remediation notes';
