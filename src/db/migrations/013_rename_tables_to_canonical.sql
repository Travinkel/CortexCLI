-- Migration 013: Rename tables to canonical model names
--
-- This migration aligns the database table names with the SQLAlchemy model definitions.
-- The naming convention shifts from "clean_*" prefix to more semantic names.
--
-- Changes:
--   clean_concept_clusters -> concept_clusters
--   clean_concepts -> concepts
--   clean_modules -> learning_modules
--   clean_atoms -> learning_atoms

-- ========================================
-- STEP 1: Rename Tables
-- ========================================

-- Rename clean_concept_clusters -> concept_clusters
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'clean_concept_clusters')
       AND NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'concept_clusters') THEN
        ALTER TABLE clean_concept_clusters RENAME TO concept_clusters;
        RAISE NOTICE 'Renamed clean_concept_clusters to concept_clusters';
    END IF;
END $$;

-- Rename clean_concepts -> concepts
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'clean_concepts')
       AND NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'concepts') THEN
        ALTER TABLE clean_concepts RENAME TO concepts;
        RAISE NOTICE 'Renamed clean_concepts to concepts';
    END IF;
END $$;

-- Rename clean_modules -> learning_modules
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'clean_modules')
       AND NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'learning_modules') THEN
        ALTER TABLE clean_modules RENAME TO learning_modules;
        RAISE NOTICE 'Renamed clean_modules to learning_modules';
    END IF;
END $$;

-- Rename clean_atoms -> learning_atoms
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'clean_atoms')
       AND NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'learning_atoms') THEN
        ALTER TABLE clean_atoms RENAME TO learning_atoms;
        RAISE NOTICE 'Renamed clean_atoms to learning_atoms';
    END IF;
END $$;

-- ========================================
-- STEP 2: Update Foreign Key References
-- ========================================

-- Update FKs referencing clean_concept_clusters -> concept_clusters
-- (concepts.cluster_id already points to concept_clusters after rename)

-- Update FKs referencing clean_concepts -> concepts
-- These are auto-renamed with the table, but we need to update constraints on other tables

-- Update FKs referencing clean_modules -> learning_modules
-- (learning_atoms.module_id already points to learning_modules after rename)

-- Update FKs referencing clean_atoms -> learning_atoms
-- Other tables like review_queue, cleaning_log, semantic_duplicates need FK updates

-- Drop and recreate FK on review_queue.original_atom_id
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.table_constraints
               WHERE constraint_name = 'review_queue_original_atom_id_fkey'
               AND table_name = 'review_queue') THEN
        ALTER TABLE review_queue DROP CONSTRAINT review_queue_original_atom_id_fkey;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'review_queue')
       AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'review_queue' AND column_name = 'original_atom_id')
       AND EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'learning_atoms') THEN
        ALTER TABLE review_queue
            ADD CONSTRAINT review_queue_original_atom_id_fkey
            FOREIGN KEY (original_atom_id) REFERENCES learning_atoms(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Drop and recreate FK on review_queue.approved_atom_id
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.table_constraints
               WHERE constraint_name = 'review_queue_approved_atom_id_fkey'
               AND table_name = 'review_queue') THEN
        ALTER TABLE review_queue DROP CONSTRAINT review_queue_approved_atom_id_fkey;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'review_queue')
       AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'review_queue' AND column_name = 'approved_atom_id')
       AND EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'learning_atoms') THEN
        ALTER TABLE review_queue
            ADD CONSTRAINT review_queue_approved_atom_id_fkey
            FOREIGN KEY (approved_atom_id) REFERENCES learning_atoms(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Drop and recreate FK on cleaning_log.atom_id
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.table_constraints
               WHERE constraint_name = 'cleaning_log_atom_id_fkey'
               AND table_name = 'cleaning_log') THEN
        ALTER TABLE cleaning_log DROP CONSTRAINT cleaning_log_atom_id_fkey;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'cleaning_log')
       AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'cleaning_log' AND column_name = 'atom_id')
       AND EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'learning_atoms') THEN
        ALTER TABLE cleaning_log
            ADD CONSTRAINT cleaning_log_atom_id_fkey
            FOREIGN KEY (atom_id) REFERENCES learning_atoms(id) ON DELETE CASCADE;
    END IF;
END $$;

-- ========================================
-- STEP 3: Rename Indexes
-- ========================================

-- Rename indexes on concept_clusters (formerly clean_concept_clusters)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_clean_concept_clusters_area') THEN
        ALTER INDEX idx_clean_concept_clusters_area RENAME TO idx_concept_clusters_area;
    END IF;
END $$;

-- Rename indexes on concepts (formerly clean_concepts)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_clean_concepts_cluster') THEN
        ALTER INDEX idx_clean_concepts_cluster RENAME TO idx_concepts_cluster;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_clean_concepts_status') THEN
        ALTER INDEX idx_clean_concepts_status RENAME TO idx_concepts_status;
    END IF;
END $$;

-- Rename indexes on learning_modules (formerly clean_modules)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_clean_modules_track') THEN
        ALTER INDEX idx_clean_modules_track RENAME TO idx_learning_modules_track;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_clean_modules_week') THEN
        ALTER INDEX idx_clean_modules_week RENAME TO idx_learning_modules_week;
    END IF;
END $$;

-- Rename indexes on learning_atoms (formerly clean_atoms)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_clean_atoms_notion') THEN
        ALTER INDEX idx_clean_atoms_notion RENAME TO idx_learning_atoms_notion;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_clean_atoms_concept') THEN
        ALTER INDEX idx_clean_atoms_concept RENAME TO idx_learning_atoms_concept;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_clean_atoms_module') THEN
        ALTER INDEX idx_clean_atoms_module RENAME TO idx_learning_atoms_module;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_clean_atoms_needs_review') THEN
        ALTER INDEX idx_clean_atoms_needs_review RENAME TO idx_learning_atoms_needs_review;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_clean_atoms_anki') THEN
        ALTER INDEX idx_clean_atoms_anki RENAME TO idx_learning_atoms_anki;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_clean_atoms_due') THEN
        ALTER INDEX idx_clean_atoms_due RENAME TO idx_learning_atoms_due;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_clean_atoms_source') THEN
        ALTER INDEX idx_clean_atoms_source RENAME TO idx_learning_atoms_source;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_clean_atoms_embedding_hnsw') THEN
        ALTER INDEX idx_clean_atoms_embedding_hnsw RENAME TO idx_learning_atoms_embedding_hnsw;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_clean_atoms_no_embedding') THEN
        ALTER INDEX idx_clean_atoms_no_embedding RENAME TO idx_learning_atoms_no_embedding;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_clean_atoms_quiz') THEN
        ALTER INDEX idx_clean_atoms_quiz RENAME TO idx_learning_atoms_quiz;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_atoms_is_hydrated') THEN
        -- Already uses non-prefixed name, skip
        NULL;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_atoms_fidelity_type') THEN
        -- Already uses non-prefixed name, skip
        NULL;
    END IF;
END $$;

-- ========================================
-- STEP 4: Update Views that reference old table names
-- ========================================

-- Recreate v_due_atoms view
DROP VIEW IF EXISTS v_due_atoms;
CREATE OR REPLACE VIEW v_due_atoms AS
SELECT
    a.*,
    c.name as concept_name,
    m.name as module_name,
    cl.name as cluster_name,
    ca.name as area_name
FROM learning_atoms a
LEFT JOIN concepts c ON a.concept_id = c.id
LEFT JOIN learning_modules m ON a.module_id = m.id
LEFT JOIN concept_clusters cl ON c.cluster_id = cl.id
LEFT JOIN clean_concept_areas ca ON cl.concept_area_id = ca.id
WHERE a.anki_due_date <= CURRENT_DATE
  AND a.is_atomic = true
  AND a.needs_review = false;

-- Recreate v_concept_atom_stats view
DROP VIEW IF EXISTS v_concept_atom_stats;
CREATE OR REPLACE VIEW v_concept_atom_stats AS
SELECT
    c.id as concept_id,
    c.name as concept_name,
    c.status,
    COUNT(a.id) as total_atoms,
    COUNT(a.id) FILTER (WHERE a.is_atomic = true) as atomic_count,
    COUNT(a.id) FILTER (WHERE a.needs_review = true) as needs_review_count,
    COUNT(a.id) FILTER (WHERE a.anki_note_id IS NOT NULL) as in_anki_count,
    AVG(a.anki_ease_factor) as avg_ease,
    AVG(a.anki_interval_days) as avg_interval
FROM concepts c
LEFT JOIN learning_atoms a ON a.concept_id = c.id
GROUP BY c.id, c.name, c.status;

-- ========================================
-- STEP 5: Add comments for documentation
-- ========================================

COMMENT ON TABLE learning_atoms IS 'Clean, validated learning atoms (flashcards, MCQ, cloze, etc.) - renamed from clean_atoms';
COMMENT ON TABLE learning_modules IS 'Week/chapter level curriculum units - renamed from clean_modules';
COMMENT ON TABLE concepts IS 'L2 atomic knowledge units (leaf-level concepts) - renamed from clean_concepts';
COMMENT ON TABLE concept_clusters IS 'L1 thematic groupings under ConceptArea - renamed from clean_concept_clusters';
