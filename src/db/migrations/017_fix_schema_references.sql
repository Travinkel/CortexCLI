-- Migration 017: Schema Cleanup and Missing FK
--
-- The main FK references were already fixed by migration 013.
-- This migration adds the missing target_cluster_id FK and updates views.

-- ============================================================================
-- STEP 1: Add missing FK for learning_path_sessions.target_cluster_id
-- ============================================================================

DO $$
BEGIN
    -- Add FK for target_cluster_id if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'learning_path_sessions_target_cluster_id_fkey'
        AND table_name = 'learning_path_sessions'
    ) THEN
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'learning_path_sessions')
           AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'learning_path_sessions' AND column_name = 'target_cluster_id')
           AND EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'concept_clusters') THEN
            ALTER TABLE learning_path_sessions
                ADD CONSTRAINT learning_path_sessions_target_cluster_id_fkey
                FOREIGN KEY (target_cluster_id) REFERENCES concept_clusters(id);
            RAISE NOTICE 'Added learning_path_sessions.target_cluster_id FK';
        END IF;
    END IF;
END $$;


-- ============================================================================
-- STEP 2: Ensure views use correct table names
-- ============================================================================

-- Recreate v_learner_progress view if it exists
DROP VIEW IF EXISTS v_learner_progress;
CREATE OR REPLACE VIEW v_learner_progress AS
SELECT
    lms.learner_id,
    cc.name as concept_name,
    cc.id as concept_id,
    ccl.name as cluster_name,
    ccl.id as cluster_id,
    lms.combined_mastery,
    lms.review_mastery,
    lms.quiz_mastery,
    lms.dec_score,
    lms.proc_score,
    lms.app_score,
    lms.is_unlocked,
    lms.unlock_reason,
    lms.review_count,
    lms.quiz_attempt_count,
    CASE
        WHEN lms.combined_mastery >= 0.85 THEN 'mastery'
        WHEN lms.combined_mastery >= 0.65 THEN 'proficient'
        WHEN lms.combined_mastery >= 0.40 THEN 'developing'
        ELSE 'novice'
    END as mastery_level,
    lms.updated_at
FROM learner_mastery_state lms
JOIN concepts cc ON lms.concept_id = cc.id
LEFT JOIN concept_clusters ccl ON cc.cluster_id = ccl.id
ORDER BY lms.learner_id, lms.combined_mastery DESC;


-- Recreate v_suitability_mismatches view
DROP VIEW IF EXISTS v_suitability_mismatches;
CREATE OR REPLACE VIEW v_suitability_mismatches AS
SELECT
    ats.atom_id,
    ca.card_id,
    ca.front,
    ats.current_type,
    ats.recommended_type,
    ats.recommendation_confidence,
    ats.knowledge_signal,
    ats.structure_signal,
    ats.computed_at
FROM atom_type_suitability ats
JOIN learning_atoms ca ON ats.atom_id = ca.id
WHERE ats.type_mismatch = TRUE
AND ats.recommendation_confidence > 0.7
ORDER BY ats.recommendation_confidence DESC;


-- Recreate v_session_analytics view
DROP VIEW IF EXISTS v_session_analytics;
CREATE OR REPLACE VIEW v_session_analytics AS
SELECT
    lps.learner_id,
    lps.mode as session_mode,
    lps.status,
    lps.atoms_presented,
    lps.atoms_correct,
    CASE WHEN lps.atoms_presented > 0
        THEN ROUND((lps.atoms_correct::decimal / lps.atoms_presented * 100), 1)
        ELSE 0
    END as accuracy_percent,
    lps.remediation_count,
    lps.started_at,
    lps.completed_at,
    cc.name as target_concept,
    ccl.name as target_cluster
FROM learning_path_sessions lps
LEFT JOIN concepts cc ON lps.target_concept_id = cc.id
LEFT JOIN concept_clusters ccl ON lps.target_cluster_id = ccl.id;


-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON VIEW v_learner_progress IS 'Learner progress summary with mastery levels';
COMMENT ON VIEW v_suitability_mismatches IS 'Atoms where current type differs from recommended type';
COMMENT ON VIEW v_session_analytics IS 'Session analytics with target concept/cluster names';
