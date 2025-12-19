-- Migration 023: Source File Tracking
-- Adds source_file column to learning_atoms for filtering by content source
-- Enables filtering sessions by: CCNAModule*.txt, ITN*.txt files

-- Add source_file column if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'learning_atoms' AND column_name = 'source_file'
    ) THEN
        ALTER TABLE learning_atoms ADD COLUMN source_file TEXT;
    END IF;
END $$;

-- Index for filtering by source file
CREATE INDEX IF NOT EXISTS idx_learning_atoms_source_file
    ON learning_atoms(source_file) WHERE source_file IS NOT NULL;

-- Backfill source_file based on card_id patterns
-- CCNAModule*.txt files have card_ids like: NET-M{module}-{type}-{num}
UPDATE learning_atoms
SET source_file = CASE
    WHEN card_id LIKE 'NET-M1-%' OR card_id LIKE 'NET-M2-%' OR card_id LIKE 'NET-M3-%'
        THEN 'CCNAModule1-3.txt'
    WHEN card_id LIKE 'NET-M4-%' OR card_id LIKE 'NET-M5-%' OR card_id LIKE 'NET-M6-%' OR card_id LIKE 'NET-M7-%'
        THEN 'CCNAModule4-7.txt'
    WHEN card_id LIKE 'NET-M8-%' OR card_id LIKE 'NET-M9-%' OR card_id LIKE 'NET-M10-%'
        THEN 'CCNAModule8-10.txt'
    WHEN card_id LIKE 'NET-M11-%' OR card_id LIKE 'NET-M12-%' OR card_id LIKE 'NET-M13-%'
        THEN 'CCNAModule11-13.txt'
    WHEN card_id LIKE 'NET-M14-%' OR card_id LIKE 'NET-M15-%'
        THEN 'CCNAModule14-15.txt'
    WHEN card_id LIKE 'NET-M16-%' OR card_id LIKE 'NET-M17-%'
        THEN 'CCNAModule16-17.txt'
    ELSE source_file
END
WHERE source_file IS NULL
  AND card_id LIKE 'NET-M%';

-- Backfill ITN source files based on card_id patterns
UPDATE learning_atoms
SET source_file = CASE
    WHEN card_id LIKE 'ITN-FINAL-%' THEN 'ITNFinalPacketTracer.txt'
    WHEN card_id LIKE 'ITN-PRAC-%' THEN 'ITNPracticeFinalExam.txt'
    WHEN card_id LIKE 'ITN-PTEST-%' OR card_id LIKE 'ITN-TEST-%' THEN 'ITNPracticeTest.txt'
    WHEN card_id LIKE 'ITN-SKILL-%' THEN 'ITNSkillsAssessment.txt'
    ELSE source_file
END
WHERE source_file IS NULL
  AND card_id LIKE 'ITN-%';

-- Also backfill based on CPE prefix (older format)
UPDATE learning_atoms
SET source_file = CASE
    WHEN card_id LIKE 'CPE-M1-%' OR card_id LIKE 'CPE-M2-%' OR card_id LIKE 'CPE-M3-%'
        THEN 'CCNAModule1-3.txt'
    WHEN card_id LIKE 'CPE-M4-%' OR card_id LIKE 'CPE-M5-%' OR card_id LIKE 'CPE-M6-%' OR card_id LIKE 'CPE-M7-%'
        THEN 'CCNAModule4-7.txt'
    WHEN card_id LIKE 'CPE-M8-%' OR card_id LIKE 'CPE-M9-%' OR card_id LIKE 'CPE-M10-%'
        THEN 'CCNAModule8-10.txt'
    WHEN card_id LIKE 'CPE-M11-%' OR card_id LIKE 'CPE-M12-%' OR card_id LIKE 'CPE-M13-%'
        THEN 'CCNAModule11-13.txt'
    WHEN card_id LIKE 'CPE-M14-%' OR card_id LIKE 'CPE-M15-%'
        THEN 'CCNAModule14-15.txt'
    WHEN card_id LIKE 'CPE-M16-%' OR card_id LIKE 'CPE-M17-%'
        THEN 'CCNAModule16-17.txt'
    ELSE source_file
END
WHERE source_file IS NULL
  AND card_id LIKE 'CPE-M%';

-- View: Atom counts by source file
CREATE OR REPLACE VIEW v_atoms_by_source AS
SELECT
    source_file,
    COUNT(*) as atom_count,
    COUNT(*) FILTER (WHERE atom_type = 'mcq') as mcq_count,
    COUNT(*) FILTER (WHERE atom_type = 'true_false') as tf_count,
    COUNT(*) FILTER (WHERE atom_type = 'flashcard') as flashcard_count,
    COUNT(*) FILTER (WHERE atom_type = 'cloze') as cloze_count,
    COUNT(*) FILTER (WHERE atom_type = 'parsons') as parsons_count,
    COUNT(*) FILTER (WHERE atom_type = 'matching') as matching_count,
    COUNT(*) FILTER (WHERE atom_type = 'numeric') as numeric_count
FROM learning_atoms
WHERE source_file IS NOT NULL
GROUP BY source_file
ORDER BY source_file;

COMMENT ON COLUMN learning_atoms.source_file IS 'Source content file (e.g., CCNAModule1-3.txt, ITNFinalPacketTracer.txt)';
