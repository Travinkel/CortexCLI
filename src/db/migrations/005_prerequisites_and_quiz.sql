-- Migration 005: Prerequisites (Soft/Hard Gating) and Quiz Quality Assurance (Phase 3)
--
-- Implements:
--   1. Explicit prerequisite relationships with soft/hard gating
--   2. Prerequisite waivers for exceptional cases
--   3. Quiz question management with type-specific content
--   4. Quiz definitions at concept/cluster level
--   5. Quiz passages for passage-based questions
--
-- Gating Types:
--   - soft: Warning shown but access allowed
--   - hard: Access blocked until mastery threshold met
--
-- Mastery Thresholds (from right-learning research):
--   - foundation: 0.40 (basic exposure sufficient)
--   - integration: 0.65 (solid understanding required) - DEFAULT
--   - mastery: 0.85 (expert level required)
--
-- Prerequisite Origins:
--   - explicit: Manually defined by instructor/admin
--   - tag: Parsed from Anki tag (tag:prereq:domain:topic:subtopic)
--   - inferred: AI-suggested and accepted (upgraded from inferred_prerequisites)
--   - imported: From external source (Notion, CSV)

-- ========================================
-- TABLE: Explicit Prerequisites
-- Prerequisite relationships with soft/hard gating
-- ========================================

CREATE TABLE IF NOT EXISTS explicit_prerequisites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source: The concept/atom that requires the prerequisite
    -- Can be at concept level or atom level
    source_concept_id UUID REFERENCES clean_concepts(id) ON DELETE CASCADE,
    source_atom_id UUID REFERENCES clean_atoms(id) ON DELETE CASCADE,

    -- Target: The prerequisite concept that must be mastered
    target_concept_id UUID NOT NULL REFERENCES clean_concepts(id) ON DELETE CASCADE,

    -- Gating configuration
    gating_type TEXT NOT NULL CHECK (gating_type IN ('soft', 'hard')),
    -- soft: Warning shown but access allowed
    -- hard: Access blocked until mastery threshold met

    -- Mastery requirements
    mastery_threshold DECIMAL(3,2) DEFAULT 0.65 CHECK (mastery_threshold BETWEEN 0 AND 1),
    mastery_type TEXT DEFAULT 'integration' CHECK (mastery_type IN ('foundation', 'integration', 'mastery')),
    -- foundation: 0.40, integration: 0.65, mastery: 0.85

    -- Origin tracking
    origin TEXT DEFAULT 'explicit' CHECK (origin IN ('explicit', 'tag', 'inferred', 'imported')),
    -- explicit: Manually defined
    -- tag: Parsed from tag:prereq:domain:topic:subtopic
    -- inferred: AI-suggested and accepted
    -- imported: From external source (Anki, Notion, CSV)

    -- For Anki sync - stores the tag format
    anki_tag TEXT,  -- e.g., "tag:prereq:networking:tcp:handshake"

    -- Review workflow
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'pending_review')),
    created_by TEXT,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    notes TEXT,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- Constraints
    -- Either source_concept_id or source_atom_id must be set
    CONSTRAINT chk_source_set CHECK (
        (source_concept_id IS NOT NULL AND source_atom_id IS NULL) OR
        (source_concept_id IS NULL AND source_atom_id IS NOT NULL)
    ),

    -- Unique constraint for concept-level prerequisites
    CONSTRAINT uq_concept_prereq UNIQUE (source_concept_id, target_concept_id),

    -- Unique constraint for atom-level prerequisites
    CONSTRAINT uq_atom_prereq UNIQUE (source_atom_id, target_concept_id)
);

-- Indexes for explicit_prerequisites
CREATE INDEX IF NOT EXISTS idx_explicit_prereq_source_concept ON explicit_prerequisites(source_concept_id) WHERE source_concept_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_explicit_prereq_source_atom ON explicit_prerequisites(source_atom_id) WHERE source_atom_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_explicit_prereq_target ON explicit_prerequisites(target_concept_id);
CREATE INDEX IF NOT EXISTS idx_explicit_prereq_gating ON explicit_prerequisites(gating_type);
CREATE INDEX IF NOT EXISTS idx_explicit_prereq_status ON explicit_prerequisites(status);
CREATE INDEX IF NOT EXISTS idx_explicit_prereq_active ON explicit_prerequisites(id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_explicit_prereq_origin ON explicit_prerequisites(origin);
CREATE INDEX IF NOT EXISTS idx_explicit_prereq_anki_tag ON explicit_prerequisites(anki_tag) WHERE anki_tag IS NOT NULL;

-- ========================================
-- TABLE: Prerequisite Waivers
-- Bypass records for exceptional cases
-- ========================================

CREATE TABLE IF NOT EXISTS prerequisite_waivers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prerequisite_id UUID NOT NULL REFERENCES explicit_prerequisites(id) ON DELETE CASCADE,

    -- Waiver type
    waiver_type TEXT NOT NULL CHECK (waiver_type IN ('instructor', 'challenge', 'external', 'accelerated')),
    -- instructor: Granted by instructor based on prior knowledge
    -- challenge: Passed challenge assessment
    -- external: Verified external credential (certificate, transfer credit)
    -- accelerated: Auto-granted for high performers (>95% on all prerequisites)

    -- Evidence supporting the waiver
    evidence_type TEXT,  -- 'quiz_score', 'certificate', 'assessment', 'transfer_credit'
    evidence_details JSONB,  -- {"score": 95, "date": "2025-01-01", "source": "coursera"}

    -- Audit trail
    granted_by TEXT,
    granted_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ,  -- Optional expiration

    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for prerequisite_waivers
CREATE INDEX IF NOT EXISTS idx_prereq_waiver_prereq ON prerequisite_waivers(prerequisite_id);
CREATE INDEX IF NOT EXISTS idx_prereq_waiver_type ON prerequisite_waivers(waiver_type);
CREATE INDEX IF NOT EXISTS idx_prereq_waiver_expires ON prerequisite_waivers(expires_at) WHERE expires_at IS NOT NULL;

-- ========================================
-- TABLE: Quiz Questions
-- Quiz question content and quality metadata
-- ========================================

CREATE TABLE IF NOT EXISTS quiz_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    atom_id UUID NOT NULL REFERENCES clean_atoms(id) ON DELETE CASCADE,

    -- Question type
    question_type TEXT NOT NULL CHECK (question_type IN (
        'mcq',           -- Multiple choice question
        'true_false',    -- True/False
        'short_answer',  -- Fill in blank, short answer
        'matching',      -- Match pairs (max 6 pairs)
        'ranking',       -- Order items
        'passage_based'  -- Question about a passage
    )),

    -- Content structure (JSONB for flexibility per type)
    question_content JSONB NOT NULL,
    -- MCQ: {"options": ["A", "B", "C", "D"], "correct_index": 0, "explanations": {"0": "Correct because...", "1": "Wrong because..."}}
    -- True/False: {"correct": true, "explanation": "..."}
    -- Short Answer: {"correct_answers": ["answer1", "answer 1"], "case_sensitive": false, "partial_match": false}
    -- Matching: {"pairs": [{"left": "Term A", "right": "Definition A"}, ...], "shuffle_right": true}
    -- Ranking: {"items": ["First", "Second", "Third"], "correct_order": [0, 1, 2]}
    -- Passage: {"passage_id": "uuid", "question": "According to the passage..."}

    -- Difficulty and cognitive load (from right-learning research)
    difficulty DECIMAL(3,2) DEFAULT 0.5 CHECK (difficulty BETWEEN 0 AND 1),
    intrinsic_load INT CHECK (intrinsic_load BETWEEN 1 AND 5),  -- Cognitive load 1-5
    knowledge_type TEXT CHECK (knowledge_type IN ('factual', 'conceptual', 'procedural', 'metacognitive')),
    -- factual: Recall facts (passing 70%)
    -- conceptual: Understand relationships (passing 80%)
    -- procedural: Execute steps (passing 85%)
    -- metacognitive: Self-regulation strategies

    -- Scoring configuration
    points INT DEFAULT 1,
    partial_credit BOOLEAN DEFAULT false,  -- Allow partial points (e.g., 3/4 matching pairs)

    -- Quality metrics (extends CardQualityAnalyzer)
    distractor_quality_score DECIMAL(3,2) CHECK (distractor_quality_score BETWEEN 0 AND 1),  -- For MCQ: how plausible are wrong options
    answer_clarity_score DECIMAL(3,2) CHECK (answer_clarity_score BETWEEN 0 AND 1),
    quality_issues TEXT[],  -- Array of detected issues

    -- Pool membership for randomization
    pool_id UUID,  -- Questions in same pool can be swapped
    is_active BOOLEAN DEFAULT true,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for quiz_questions
CREATE INDEX IF NOT EXISTS idx_quiz_questions_atom ON quiz_questions(atom_id);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_type ON quiz_questions(question_type);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_pool ON quiz_questions(pool_id) WHERE pool_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_quiz_questions_active ON quiz_questions(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_quiz_questions_difficulty ON quiz_questions(difficulty);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_knowledge_type ON quiz_questions(knowledge_type);

-- ========================================
-- TABLE: Quiz Definitions
-- Quiz configuration at concept/cluster level
-- ========================================

CREATE TABLE IF NOT EXISTS quiz_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Scope: Can be at concept cluster level or concept level
    concept_cluster_id UUID REFERENCES clean_concept_clusters(id) ON DELETE SET NULL,
    concept_id UUID REFERENCES clean_concepts(id) ON DELETE SET NULL,

    name TEXT NOT NULL,
    description TEXT,

    -- Question selection
    question_count INT DEFAULT 10,
    time_limit_minutes INT,  -- NULL = unlimited

    -- Passing thresholds (from right-learning research)
    passing_threshold DECIMAL(3,2) DEFAULT 0.70 CHECK (passing_threshold BETWEEN 0 AND 1),
    -- Varies by knowledge type: factual 70%, conceptual 80%, procedural 85%

    -- Mastery weights (from right-learning: 37.5% quiz + 62.5% review)
    quiz_mastery_weight DECIMAL(3,2) DEFAULT 0.375 CHECK (quiz_mastery_weight BETWEEN 0 AND 1),
    review_mastery_weight DECIMAL(3,2) DEFAULT 0.625 CHECK (review_mastery_weight BETWEEN 0 AND 1),

    -- Attempt configuration
    max_attempts INT,  -- NULL = unlimited
    allow_resume BOOLEAN DEFAULT true,  -- Can pause and continue later
    randomize_questions BOOLEAN DEFAULT true,
    randomize_options BOOLEAN DEFAULT true,  -- For MCQ: shuffle answer options
    show_immediate_feedback BOOLEAN DEFAULT true,

    -- Adaptive mode
    adaptive_difficulty BOOLEAN DEFAULT false,  -- Adjust difficulty based on performance

    -- Pool configuration
    question_pool_ids UUID[],  -- Array of pool IDs to draw questions from

    -- Prerequisites
    requires_prerequisites BOOLEAN DEFAULT true,

    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- Ensure weights sum to 1
    CONSTRAINT chk_mastery_weights CHECK (quiz_mastery_weight + review_mastery_weight = 1.0)
);

-- Indexes for quiz_definitions
CREATE INDEX IF NOT EXISTS idx_quiz_def_cluster ON quiz_definitions(concept_cluster_id) WHERE concept_cluster_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_quiz_def_concept ON quiz_definitions(concept_id) WHERE concept_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_quiz_def_active ON quiz_definitions(is_active) WHERE is_active = true;

-- ========================================
-- TABLE: Quiz Passages
-- Passages for passage-based questions
-- ========================================

CREATE TABLE IF NOT EXISTS quiz_passages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_definition_id UUID REFERENCES quiz_definitions(id) ON DELETE CASCADE,

    title TEXT,
    content TEXT NOT NULL,
    source_reference TEXT,  -- Citation or source
    word_count INT,

    -- For quality tracking
    readability_score DECIMAL(4,2),  -- Flesch-Kincaid or similar

    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for quiz_passages
CREATE INDEX IF NOT EXISTS idx_quiz_passages_quiz ON quiz_passages(quiz_definition_id);

-- ========================================
-- TABLE: Question Pools
-- Named pools for question grouping and selection
-- ========================================

CREATE TABLE IF NOT EXISTS question_pools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name TEXT NOT NULL,
    description TEXT,

    -- Scope
    concept_id UUID REFERENCES clean_concepts(id) ON DELETE SET NULL,
    concept_cluster_id UUID REFERENCES clean_concept_clusters(id) ON DELETE SET NULL,

    -- Pool metadata
    target_difficulty DECIMAL(3,2) CHECK (target_difficulty BETWEEN 0 AND 1),
    min_questions INT DEFAULT 5,  -- Minimum questions needed for quiz generation

    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for question_pools
CREATE INDEX IF NOT EXISTS idx_question_pools_concept ON question_pools(concept_id) WHERE concept_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_question_pools_cluster ON question_pools(concept_cluster_id) WHERE concept_cluster_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_question_pools_active ON question_pools(is_active) WHERE is_active = true;

-- ========================================
-- ALTER TABLE: Add quiz fields to clean_atoms
-- ========================================

ALTER TABLE clean_atoms
ADD COLUMN IF NOT EXISTS is_quiz_question BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS quiz_question_type TEXT,
ADD COLUMN IF NOT EXISTS quiz_question_metadata JSONB;

-- Index for quiz questions in clean_atoms
CREATE INDEX IF NOT EXISTS idx_clean_atoms_quiz ON clean_atoms(is_quiz_question) WHERE is_quiz_question = true;

-- ========================================
-- ALTER TABLE: Add prerequisite export tracking to clean_atoms
-- ========================================

ALTER TABLE clean_atoms
ADD COLUMN IF NOT EXISTS prerequisite_tags_exported TEXT[],
ADD COLUMN IF NOT EXISTS prerequisite_export_at TIMESTAMPTZ;

-- ========================================
-- VIEW: Prerequisite Chain (for circular detection)
-- Recursive CTE to build prerequisite chains
-- ========================================

CREATE OR REPLACE VIEW v_prerequisite_chains AS
WITH RECURSIVE prereq_chain AS (
    -- Base case: direct prerequisites
    SELECT
        ep.source_concept_id,
        ep.target_concept_id,
        ARRAY[ep.source_concept_id] as chain,
        1 as depth,
        ep.gating_type,
        ep.mastery_threshold
    FROM explicit_prerequisites ep
    WHERE ep.status = 'active'
      AND ep.source_concept_id IS NOT NULL

    UNION ALL

    -- Recursive case: follow the chain
    SELECT
        pc.source_concept_id,
        ep.target_concept_id,
        pc.chain || ep.source_concept_id,
        pc.depth + 1,
        ep.gating_type,
        ep.mastery_threshold
    FROM prereq_chain pc
    JOIN explicit_prerequisites ep ON ep.source_concept_id = pc.target_concept_id
    WHERE NOT ep.source_concept_id = ANY(pc.chain)  -- Prevent cycles
      AND pc.depth < 10  -- Limit depth
      AND ep.status = 'active'
)
SELECT * FROM prereq_chain;

-- ========================================
-- VIEW: Active Prerequisites with Details
-- ========================================

CREATE OR REPLACE VIEW v_active_prerequisites AS
SELECT
    ep.id,
    ep.source_concept_id,
    ep.source_atom_id,
    ep.target_concept_id,
    ep.gating_type,
    ep.mastery_threshold,
    ep.mastery_type,
    ep.origin,
    ep.anki_tag,
    sc.name as source_concept_name,
    tc.name as target_concept_name,
    a.card_id as source_atom_card_id,
    a.front as source_atom_front
FROM explicit_prerequisites ep
LEFT JOIN clean_concepts sc ON ep.source_concept_id = sc.id
JOIN clean_concepts tc ON ep.target_concept_id = tc.id
LEFT JOIN clean_atoms a ON ep.source_atom_id = a.id
WHERE ep.status = 'active';

-- ========================================
-- VIEW: Quiz Question Quality Summary
-- ========================================

CREATE OR REPLACE VIEW v_quiz_question_quality AS
SELECT
    qq.id as question_id,
    qq.question_type,
    qq.difficulty,
    qq.knowledge_type,
    qq.distractor_quality_score,
    qq.answer_clarity_score,
    qq.quality_issues,
    a.quality_score as atom_quality_score,
    a.front,
    a.back,
    c.name as concept_name
FROM quiz_questions qq
JOIN clean_atoms a ON qq.atom_id = a.id
LEFT JOIN clean_concepts c ON a.concept_id = c.id
WHERE qq.is_active = true;

-- ========================================
-- VIEW: Question Pool Statistics
-- ========================================

CREATE OR REPLACE VIEW v_question_pool_stats AS
SELECT
    qp.id as pool_id,
    qp.name as pool_name,
    qp.target_difficulty,
    COUNT(qq.id) as question_count,
    AVG(qq.difficulty) as avg_difficulty,
    COUNT(DISTINCT qq.question_type) as type_count,
    COUNT(qq.id) FILTER (WHERE qq.distractor_quality_score >= 0.6) as high_quality_count,
    CASE
        WHEN COUNT(qq.id) >= qp.min_questions THEN 'sufficient'
        ELSE 'needs_more'
    END as pool_status
FROM question_pools qp
LEFT JOIN quiz_questions qq ON qq.pool_id = qp.id AND qq.is_active = true
WHERE qp.is_active = true
GROUP BY qp.id, qp.name, qp.target_difficulty, qp.min_questions;

-- ========================================
-- FUNCTION: Check for circular prerequisites
-- Returns true if adding this prerequisite would create a cycle
-- ========================================

CREATE OR REPLACE FUNCTION check_circular_prerequisite(
    p_source_concept_id UUID,
    p_target_concept_id UUID
) RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_cycle_exists BOOLEAN;
BEGIN
    -- Check if target already depends on source (directly or transitively)
    WITH RECURSIVE prereq_check AS (
        -- Start from target concept
        SELECT target_concept_id as concept_id, 1 as depth
        FROM explicit_prerequisites
        WHERE source_concept_id = p_target_concept_id
          AND status = 'active'

        UNION ALL

        -- Follow the chain
        SELECT ep.target_concept_id, pc.depth + 1
        FROM prereq_check pc
        JOIN explicit_prerequisites ep ON ep.source_concept_id = pc.concept_id
        WHERE ep.status = 'active'
          AND pc.depth < 10
    )
    SELECT EXISTS (
        SELECT 1 FROM prereq_check WHERE concept_id = p_source_concept_id
    ) INTO v_cycle_exists;

    RETURN v_cycle_exists;
END;
$$;

-- ========================================
-- FUNCTION: Get mastery threshold by type
-- Returns the appropriate threshold based on mastery_type
-- ========================================

CREATE OR REPLACE FUNCTION get_mastery_threshold(p_mastery_type TEXT)
RETURNS DECIMAL(3,2)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN CASE p_mastery_type
        WHEN 'foundation' THEN 0.40
        WHEN 'integration' THEN 0.65
        WHEN 'mastery' THEN 0.85
        ELSE 0.65  -- Default to integration
    END;
END;
$$;

-- ========================================
-- TRIGGER: Auto-update timestamp
-- ========================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- Apply to new tables
DROP TRIGGER IF EXISTS trg_explicit_prereq_updated_at ON explicit_prerequisites;
CREATE TRIGGER trg_explicit_prereq_updated_at
    BEFORE UPDATE ON explicit_prerequisites
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_quiz_questions_updated_at ON quiz_questions;
CREATE TRIGGER trg_quiz_questions_updated_at
    BEFORE UPDATE ON quiz_questions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_quiz_definitions_updated_at ON quiz_definitions;
CREATE TRIGGER trg_quiz_definitions_updated_at
    BEFORE UPDATE ON quiz_definitions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_question_pools_updated_at ON question_pools;
CREATE TRIGGER trg_question_pools_updated_at
    BEFORE UPDATE ON question_pools
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- COMMENTS
-- ========================================

COMMENT ON TABLE explicit_prerequisites IS 'Prerequisite relationships with soft/hard gating. Soft = warning, Hard = blocked.';
COMMENT ON COLUMN explicit_prerequisites.gating_type IS 'soft: Access allowed with warning. hard: Access blocked until mastery met.';
COMMENT ON COLUMN explicit_prerequisites.mastery_type IS 'foundation (0.40), integration (0.65 default), mastery (0.85)';
COMMENT ON COLUMN explicit_prerequisites.origin IS 'explicit: Manual, tag: From Anki tag, inferred: AI-suggested, imported: External';
COMMENT ON COLUMN explicit_prerequisites.anki_tag IS 'Anki tag format: tag:prereq:domain:topic:subtopic';

COMMENT ON TABLE prerequisite_waivers IS 'Bypass records for exceptional learners or external credentials';
COMMENT ON COLUMN prerequisite_waivers.waiver_type IS 'instructor: Manual, challenge: Passed test, external: Credential, accelerated: High performer';

COMMENT ON TABLE quiz_questions IS 'Quiz question content with type-specific JSONB structure and quality metrics';
COMMENT ON COLUMN quiz_questions.question_content IS 'JSONB structure varies by question_type. See migration comments for schema.';
COMMENT ON COLUMN quiz_questions.distractor_quality_score IS 'For MCQ: measures how plausible wrong answers are (0-1)';

COMMENT ON TABLE quiz_definitions IS 'Quiz configuration including mastery weights from right-learning research';
COMMENT ON COLUMN quiz_definitions.quiz_mastery_weight IS '37.5% default - quiz contribution to overall mastery';
COMMENT ON COLUMN quiz_definitions.review_mastery_weight IS '62.5% default - spaced repetition contribution to mastery';

COMMENT ON TABLE question_pools IS 'Named pools for question grouping and randomized selection';

COMMENT ON FUNCTION check_circular_prerequisite IS 'Returns true if adding prerequisite would create a cycle';
COMMENT ON FUNCTION get_mastery_threshold IS 'Returns threshold: foundation=0.40, integration=0.65, mastery=0.85';
