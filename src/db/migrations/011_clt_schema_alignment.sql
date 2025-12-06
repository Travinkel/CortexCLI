-- Migration 011: CLT Schema Alignment with Master Prompt
-- Converts CLT from single string to three measurable integers (1-5 scale)
-- Per Master Prompt: CLT is used ONLY for NLS quiz atoms, NOT Anki

-- Add CLT integer columns (replacing single clt_load string)
DO $$
BEGIN
    -- clt_intrinsic: unavoidable domain complexity (1-5)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'clt_intrinsic') THEN
        ALTER TABLE clean_atoms ADD COLUMN clt_intrinsic SMALLINT CHECK (clt_intrinsic BETWEEN 1 AND 5);
    END IF;

    -- clt_extraneous: noise, confusing wording (1-5)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'clt_extraneous') THEN
        ALTER TABLE clean_atoms ADD COLUMN clt_extraneous SMALLINT CHECK (clt_extraneous BETWEEN 1 AND 5);
    END IF;

    -- clt_germane: schema-building, integration (1-5)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'clt_germane') THEN
        ALTER TABLE clean_atoms ADD COLUMN clt_germane SMALLINT CHECK (clt_germane BETWEEN 1 AND 5);
    END IF;

    -- difficulty as integer (1-5) for consistency
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'difficulty') THEN
        ALTER TABLE clean_atoms ADD COLUMN difficulty SMALLINT CHECK (difficulty BETWEEN 1 AND 5);
    END IF;

    -- stability_days for FSRS-aligned tracking
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'stability_days') THEN
        ALTER TABLE clean_atoms ADD COLUMN stability_days DECIMAL(10,2);
    END IF;

    -- prerequisites array (JSON) for graph expansion
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'clean_atoms' AND column_name = 'prerequisites') THEN
        ALTER TABLE clean_atoms ADD COLUMN prerequisites JSONB DEFAULT '[]'::jsonb;
    END IF;
END $$;

-- Migrate existing clt_load string to new integer columns
-- Map: 'intrinsic' -> intrinsic=3, 'extraneous' -> extraneous=3, 'germane' -> germane=3
UPDATE clean_atoms
SET clt_intrinsic = CASE
    WHEN clt_load = 'intrinsic' THEN 3
    WHEN clt_load = 'high' THEN 4
    ELSE 2
END,
clt_extraneous = CASE
    WHEN clt_load = 'extraneous' THEN 3
    WHEN clt_load = 'high' THEN 4
    ELSE 2
END,
clt_germane = CASE
    WHEN clt_load = 'germane' THEN 3
    WHEN clt_load = 'high' THEN 4
    ELSE 3
END
WHERE clt_load IS NOT NULL
  AND clt_intrinsic IS NULL;

-- Set default CLT for quiz atoms that need it
UPDATE clean_atoms
SET clt_intrinsic = 2, clt_extraneous = 2, clt_germane = 3
WHERE atom_type IN ('mcq', 'true_false', 'matching', 'parsons')
  AND clt_intrinsic IS NULL;

-- Indexes for efficient CLT-based queries
CREATE INDEX IF NOT EXISTS idx_atoms_clt_intrinsic ON clean_atoms(clt_intrinsic) WHERE clt_intrinsic IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_atoms_difficulty ON clean_atoms(difficulty) WHERE difficulty IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_atoms_prerequisites ON clean_atoms USING GIN (prerequisites);

-- View: Quiz atoms with full CLT metadata (per Master Prompt)
CREATE OR REPLACE VIEW v_quiz_atoms_clt AS
SELECT
    ca.id,
    ca.card_id,
    ca.front,
    ca.back,
    ca.atom_type,
    ca.concept_id,
    ca.ccna_section_id,
    cs.module_number,
    cs.title as section_title,
    ca.clt_intrinsic,
    ca.clt_extraneous,
    ca.clt_germane,
    ca.difficulty,
    ca.quality_score,
    ca.bloom_level,
    ca.prerequisites,
    -- Composite CLT score for balancing
    (COALESCE(ca.clt_intrinsic, 2) + COALESCE(ca.clt_extraneous, 2) + COALESCE(ca.clt_germane, 2)) / 3.0 as clt_avg
FROM clean_atoms ca
LEFT JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
WHERE ca.atom_type IN ('mcq', 'true_false', 'matching', 'parsons');

COMMENT ON VIEW v_quiz_atoms_clt IS 'Quiz atoms with CLT metadata for NLS session balancing';

-- View: Anki atoms (NO CLT - per Master Prompt rule)
CREATE OR REPLACE VIEW v_anki_atoms AS
SELECT
    ca.id,
    ca.card_id,
    ca.front,
    ca.back,
    ca.atom_type,
    ca.concept_id,
    cc.name as concept_name,
    ca.ccna_section_id,
    cs.module_number,
    cs.title as section_title,
    ca.source,
    ca.bloom_level,
    ca.quality_score,
    ca.difficulty,
    ca.prerequisites,
    ca.anki_note_id,
    ca.anki_stability,
    ca.anki_difficulty as anki_difficulty_factor,
    ca.anki_lapses
FROM clean_atoms ca
LEFT JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
LEFT JOIN clean_concepts cc ON ca.concept_id = cc.id
WHERE ca.atom_type IN ('flashcard', 'cloze');

COMMENT ON VIEW v_anki_atoms IS 'Anki atoms without CLT (CLT not used for FSRS per Master Prompt)';

-- Function: Get activity path for module(s) with prerequisite ordering
CREATE OR REPLACE FUNCTION get_module_activity_path(
    target_modules INT[],
    max_depth INT DEFAULT 3
)
RETURNS TABLE (
    atom_id UUID,
    card_id VARCHAR,
    front TEXT,
    back TEXT,
    atom_type VARCHAR,
    concept_id UUID,
    module_number INT,
    section_id VARCHAR,
    depth INT,
    direction VARCHAR,
    destination VARCHAR,  -- 'anki' or 'nls'
    clt_intrinsic SMALLINT,
    clt_extraneous SMALLINT,
    clt_germane SMALLINT,
    difficulty SMALLINT,
    sort_order INT
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE concept_chain AS (
        -- Base: concepts in target modules (depth 0)
        SELECT DISTINCT
            ca.concept_id,
            0 as depth,
            'origin'::VARCHAR as direction
        FROM clean_atoms ca
        JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
        WHERE cs.module_number = ANY(target_modules)
          AND ca.concept_id IS NOT NULL

        UNION

        -- Upstream: prerequisites
        SELECT DISTINCT
            ep.target_concept_id,
            cc.depth + 1,
            'upstream'::VARCHAR
        FROM explicit_prerequisites ep
        JOIN concept_chain cc ON ep.source_concept_id = cc.concept_id
        WHERE cc.depth < max_depth

        UNION

        -- Downstream: dependents
        SELECT DISTINCT
            ep.source_concept_id,
            cc.depth + 1,
            'downstream'::VARCHAR
        FROM explicit_prerequisites ep
        JOIN concept_chain cc ON ep.target_concept_id = cc.concept_id
        WHERE cc.depth < max_depth
    )
    SELECT
        ca.id as atom_id,
        ca.card_id,
        ca.front,
        ca.back,
        ca.atom_type,
        ca.concept_id,
        cs.module_number,
        cs.section_id,
        cc_chain.depth,
        cc_chain.direction,
        CASE
            WHEN ca.atom_type IN ('flashcard', 'cloze') THEN 'anki'
            ELSE 'nls'
        END as destination,
        ca.clt_intrinsic,
        ca.clt_extraneous,
        ca.clt_germane,
        ca.difficulty,
        -- Sort: prerequisites first (by depth DESC), then by module, then by difficulty
        (cc_chain.depth * 1000) + (cs.module_number * 10) + COALESCE(ca.difficulty, 3) as sort_order
    FROM concept_chain cc_chain
    JOIN clean_atoms ca ON ca.concept_id = cc_chain.concept_id
    JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
    WHERE ca.front IS NOT NULL AND ca.front != ''
    ORDER BY sort_order DESC, cs.module_number, ca.atom_type;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_module_activity_path IS 'Returns learning path for module(s) with prerequisite-ordered activities';
