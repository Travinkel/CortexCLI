-- Migration 016: Quarantine table for broken/invalid atoms
-- Stores atoms that fail data integrity checks for review/recovery

CREATE TABLE IF NOT EXISTS quarantine_atoms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_id UUID NOT NULL,
    card_id TEXT,
    atom_type TEXT,
    front TEXT,
    back TEXT,
    content_json JSONB,
    media_type TEXT,
    media_code TEXT,
    quarantine_reason TEXT NOT NULL,
    quarantined_at TIMESTAMP DEFAULT NOW(),
    original_data JSONB  -- Full row backup for recovery
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_quarantine_reason ON quarantine_atoms(quarantine_reason);
CREATE INDEX IF NOT EXISTS idx_quarantine_date ON quarantine_atoms(quarantined_at);
CREATE INDEX IF NOT EXISTS idx_quarantine_original_id ON quarantine_atoms(original_id);
