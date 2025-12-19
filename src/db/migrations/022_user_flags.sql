-- Migration 022: User Flags
-- Allows users to flag problematic questions during study sessions

CREATE TABLE IF NOT EXISTS user_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    atom_id UUID REFERENCES learning_atoms(id) ON DELETE CASCADE,
    user_id TEXT,  -- Future: actual user system
    flag_type TEXT NOT NULL,  -- 'wrong_answer', 'ambiguous', 'typo', 'outdated', 'too_easy', 'too_hard'
    flag_reason TEXT,  -- Optional user-provided reason
    session_id UUID,  -- Optional: link to session when flagged
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    resolved_by TEXT
);

-- Index for finding unresolved flags
CREATE INDEX IF NOT EXISTS idx_user_flags_unresolved
    ON user_flags(resolved_at) WHERE resolved_at IS NULL;

-- Index for finding flags by atom
CREATE INDEX IF NOT EXISTS idx_user_flags_atom ON user_flags(atom_id);

-- Index for finding flags by type
CREATE INDEX IF NOT EXISTS idx_user_flags_type ON user_flags(flag_type);

-- View: Atoms with multiple flags (high priority for review)
CREATE OR REPLACE VIEW v_flagged_atoms AS
SELECT
    la.id as atom_id,
    la.card_id,
    la.atom_type,
    la.front,
    COUNT(uf.id) as flag_count,
    ARRAY_AGG(DISTINCT uf.flag_type) as flag_types,
    MIN(uf.created_at) as first_flagged,
    MAX(uf.created_at) as last_flagged
FROM learning_atoms la
JOIN user_flags uf ON la.id = uf.atom_id
WHERE uf.resolved_at IS NULL
GROUP BY la.id, la.card_id, la.atom_type, la.front
ORDER BY flag_count DESC;

COMMENT ON TABLE user_flags IS 'User-reported issues with learning atoms';
COMMENT ON COLUMN user_flags.flag_type IS 'Type of issue: wrong_answer, ambiguous, typo, outdated, too_easy, too_hard';
