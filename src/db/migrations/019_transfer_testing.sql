-- Migration 019: Transfer Testing for Memorization Detection
--
-- Adds schema support for detecting rote memorization vs genuine understanding
-- by tracking performance across different question formats for the same concept.

-- Track which formats user has seen for each atom
ALTER TABLE learning_atoms
ADD COLUMN IF NOT EXISTS format_seen JSONB DEFAULT '{}';

-- Queue atoms for transfer testing in next session
-- Format: ["atom_id:target_type", ...]
ALTER TABLE learning_atoms
ADD COLUMN IF NOT EXISTS transfer_queue TEXT[];

-- Track per-format accuracy for memorization detection
-- Format: {"true_false": {"correct": 5, "total": 6}, "parsons": {"correct": 1, "total": 4}}
ALTER TABLE learning_atoms
ADD COLUMN IF NOT EXISTS accuracy_by_type JSONB DEFAULT '{}';

-- Add transfer score column (0.0-1.0)
-- High score = consistent across formats (genuine understanding)
-- Low score = high variance across formats (memorization suspect)
ALTER TABLE learning_atoms
ADD COLUMN IF NOT EXISTS transfer_score FLOAT DEFAULT NULL;

-- Track if atom is flagged as memorization suspect
ALTER TABLE learning_atoms
ADD COLUMN IF NOT EXISTS memorization_suspect BOOLEAN DEFAULT FALSE;

-- Create index for querying transfer queue
CREATE INDEX IF NOT EXISTS idx_learning_atoms_transfer_queue
ON learning_atoms USING GIN (transfer_queue);

-- Create index for memorization suspects
CREATE INDEX IF NOT EXISTS idx_learning_atoms_memorization_suspect
ON learning_atoms (memorization_suspect) WHERE memorization_suspect = TRUE;

-- Add view for section-level memorization analysis
CREATE OR REPLACE VIEW v_section_transfer_analysis AS
SELECT
    ccna_section_id,
    COUNT(*) as total_atoms,
    COUNT(*) FILTER (WHERE memorization_suspect = TRUE) as suspect_atoms,
    ROUND(AVG(transfer_score)::numeric, 2) as avg_transfer_score,
    -- Calculate per-type accuracy aggregates
    ROUND(AVG(
        CASE WHEN (accuracy_by_type->>'true_false')::jsonb->>'total' IS NOT NULL
             AND ((accuracy_by_type->>'true_false')::jsonb->>'total')::int > 0
        THEN ((accuracy_by_type->>'true_false')::jsonb->>'correct')::float /
             ((accuracy_by_type->>'true_false')::jsonb->>'total')::float
        END
    )::numeric, 2) as avg_tf_accuracy,
    ROUND(AVG(
        CASE WHEN (accuracy_by_type->>'parsons')::jsonb->>'total' IS NOT NULL
             AND ((accuracy_by_type->>'parsons')::jsonb->>'total')::int > 0
        THEN ((accuracy_by_type->>'parsons')::jsonb->>'correct')::float /
             ((accuracy_by_type->>'parsons')::jsonb->>'total')::float
        END
    )::numeric, 2) as avg_parsons_accuracy,
    ROUND(AVG(
        CASE WHEN (accuracy_by_type->>'mcq')::jsonb->>'total' IS NOT NULL
             AND ((accuracy_by_type->>'mcq')::jsonb->>'total')::int > 0
        THEN ((accuracy_by_type->>'mcq')::jsonb->>'correct')::float /
             ((accuracy_by_type->>'mcq')::jsonb->>'total')::float
        END
    )::numeric, 2) as avg_mcq_accuracy
FROM learning_atoms
WHERE ccna_section_id IS NOT NULL
GROUP BY ccna_section_id;

COMMENT ON COLUMN learning_atoms.format_seen IS 'Tracks which question formats have been presented for this atom';
COMMENT ON COLUMN learning_atoms.transfer_queue IS 'Queue of target formats to test in next session';
COMMENT ON COLUMN learning_atoms.accuracy_by_type IS 'Per-format accuracy stats for memorization detection';
COMMENT ON COLUMN learning_atoms.transfer_score IS 'Consistency score across formats (0-1, higher = genuine understanding)';
COMMENT ON COLUMN learning_atoms.memorization_suspect IS 'Flagged when T/F accuracy >> procedural accuracy';
