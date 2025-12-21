-- Migration 030: Skill Graph Foundation
-- Creates skill taxonomy and atom-skill linking infrastructure for mastery tracking

-- ============================================================
-- Table: skills
-- Purpose: Hierarchical skill taxonomy with Bloom's levels
-- ============================================================

CREATE TABLE IF NOT EXISTS skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_code VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    domain VARCHAR(50) NOT NULL,  -- 'networking', 'programming', 'systems', etc.
    cognitive_level VARCHAR(50) NOT NULL,  -- 'remember', 'understand', 'apply', 'analyze', 'evaluate', 'create'
    parent_skill_id UUID REFERENCES skills(id) ON DELETE SET NULL,  -- For hierarchical skills
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_skills_domain ON skills(domain);
CREATE INDEX idx_skills_cognitive_level ON skills(cognitive_level);
CREATE INDEX idx_skills_parent ON skills(parent_skill_id);
CREATE INDEX idx_skills_active ON skills(is_active);

COMMENT ON TABLE skills IS 'Skill taxonomy with hierarchical support and Bloom''s cognitive levels';
COMMENT ON COLUMN skills.skill_code IS 'Unique identifier like NET_OSI_LAYERS or PROG_DEBUGGING';
COMMENT ON COLUMN skills.cognitive_level IS 'Bloom''s taxonomy: remember, understand, apply, analyze, evaluate, create';
COMMENT ON COLUMN skills.parent_skill_id IS 'Parent skill for hierarchical relationships (NULL for root skills)';

-- ============================================================
-- Table: atom_skill_weights
-- Purpose: Many-to-many mapping between atoms and skills with weights
-- ============================================================

CREATE TABLE IF NOT EXISTS atom_skill_weights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    atom_id UUID NOT NULL REFERENCES learning_atoms(id) ON DELETE CASCADE,
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    weight FLOAT NOT NULL DEFAULT 1.0,  -- How much this atom measures this skill (0.0-1.0)
    is_primary BOOLEAN DEFAULT FALSE,  -- TRUE if this is the main skill being tested
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(atom_id, skill_id)  -- Each atom-skill pair only once
);

CREATE INDEX idx_atom_skill_atom ON atom_skill_weights(atom_id);
CREATE INDEX idx_atom_skill_skill ON atom_skill_weights(skill_id);
CREATE INDEX idx_atom_skill_primary ON atom_skill_weights(is_primary);
CREATE INDEX idx_atom_skill_weight ON atom_skill_weights(weight DESC);

COMMENT ON TABLE atom_skill_weights IS 'Many-to-many atom-skill mapping with weights for multi-skill atoms';
COMMENT ON COLUMN atom_skill_weights.weight IS 'How strongly this atom tests this skill (0.0-1.0, default 1.0)';
COMMENT ON COLUMN atom_skill_weights.is_primary IS 'TRUE if this is the primary skill (atom can test multiple skills)';

-- ============================================================
-- Table: learner_skill_mastery
-- Purpose: Per-learner mastery tracking with FSRS parameters
-- ============================================================

CREATE TABLE IF NOT EXISTS learner_skill_mastery (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    learner_id UUID NOT NULL,  -- Will reference learners table when created
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    mastery_level FLOAT NOT NULL DEFAULT 0.0,  -- Current mastery estimate (0.0-1.0)
    confidence_interval FLOAT NOT NULL DEFAULT 0.5,  -- Uncertainty in mastery estimate
    practice_count INTEGER NOT NULL DEFAULT 0,  -- Number of times practiced
    consecutive_correct INTEGER NOT NULL DEFAULT 0,  -- Streak of correct responses
    last_practiced TIMESTAMP WITH TIME ZONE,
    retrievability FLOAT NOT NULL DEFAULT 1.0,  -- FSRS: Current recall probability
    difficulty FLOAT NOT NULL DEFAULT 0.3,  -- FSRS: Intrinsic difficulty (0.0-1.0)
    stability FLOAT NOT NULL DEFAULT 1.0,  -- FSRS: Memory stability in days
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(learner_id, skill_id)  -- One mastery record per learner-skill pair
);

CREATE INDEX idx_learner_skill_learner ON learner_skill_mastery(learner_id);
CREATE INDEX idx_learner_skill_skill ON learner_skill_mastery(skill_id);
CREATE INDEX idx_learner_skill_mastery ON learner_skill_mastery(mastery_level);
CREATE INDEX idx_learner_skill_retrievability ON learner_skill_mastery(retrievability);
CREATE INDEX idx_learner_skill_last_practiced ON learner_skill_mastery(last_practiced);

COMMENT ON TABLE learner_skill_mastery IS 'Per-learner skill mastery tracking with Bayesian updates and FSRS scheduling';
COMMENT ON COLUMN learner_skill_mastery.mastery_level IS 'Bayesian estimate of mastery (0.0-1.0)';
COMMENT ON COLUMN learner_skill_mastery.confidence_interval IS 'Uncertainty bounds (narrows with more practice)';
COMMENT ON COLUMN learner_skill_mastery.retrievability IS 'FSRS: Current probability of successful recall';
COMMENT ON COLUMN learner_skill_mastery.difficulty IS 'FSRS: Intrinsic difficulty of this skill for this learner';
COMMENT ON COLUMN learner_skill_mastery.stability IS 'FSRS: Memory stability in days (increases with correct answers)';

-- ============================================================
-- View: v_skill_gaps
-- Purpose: Quick view of learner's weakest skills for targeting
-- ============================================================

CREATE OR REPLACE VIEW v_skill_gaps AS
SELECT
    lsm.learner_id,
    s.skill_code,
    s.name AS skill_name,
    s.domain,
    s.cognitive_level,
    lsm.mastery_level,
    lsm.retrievability,
    lsm.practice_count,
    lsm.last_practiced,
    COUNT(DISTINCT asw.atom_id) AS available_atoms
FROM learner_skill_mastery lsm
JOIN skills s ON lsm.skill_id = s.id
LEFT JOIN atom_skill_weights asw ON s.id = asw.skill_id AND asw.is_primary = TRUE
WHERE s.is_active = TRUE
GROUP BY
    lsm.learner_id,
    s.skill_code,
    s.name,
    s.domain,
    s.cognitive_level,
    lsm.mastery_level,
    lsm.retrievability,
    lsm.practice_count,
    lsm.last_practiced
ORDER BY
    lsm.mastery_level ASC,  -- Lowest mastery first
    lsm.retrievability ASC;  -- Most forgotten first

COMMENT ON VIEW v_skill_gaps IS 'Learner skill gaps for targeted practice (lowest mastery + retrievability)';

-- Skill taxonomy table
CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_code VARCHAR(50) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    domain VARCHAR(100),              -- networking, programming, systems
    cognitive_level VARCHAR(20),      -- remember, understand, apply, analyze, evaluate, create
    parent_skill_id UUID REFERENCES skills(id),  -- Hierarchy support
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Atom-Skill linking (many-to-many)
CREATE TABLE atom_skill_weights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    atom_id UUID REFERENCES learning_atoms(id) ON DELETE CASCADE,
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    weight NUMERIC(3,2) DEFAULT 1.0,  -- How much this atom measures this skill (0-1)
    is_primary BOOLEAN DEFAULT FALSE, -- Primary skill being tested
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(atom_id, skill_id)
);

-- Learner skill mastery state
CREATE TABLE learner_skill_mastery (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    learner_id UUID NOT NULL,
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    mastery_level NUMERIC(5,4) DEFAULT 0.0000,       -- 0.0000 (no mastery) to 1.0000 (full mastery)
    confidence_interval NUMERIC(5,4) DEFAULT 0.5000, -- Uncertainty in estimate
    last_practiced TIMESTAMPTZ,
    practice_count INTEGER DEFAULT 0,
    consecutive_correct INTEGER DEFAULT 0,
    retrievability NUMERIC(5,4) DEFAULT 1.0000,      -- FSRS retrievability for this skill
    difficulty NUMERIC(5,4) DEFAULT 0.3000,          -- FSRS difficulty for this skill
    stability NUMERIC(5,4) DEFAULT 1.0000,           -- FSRS stability (days until 90% recall)
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(learner_id, skill_id)
);

-- Indexes for fast skill-based atom queries
CREATE INDEX idx_atom_skill_primary ON atom_skill_weights(skill_id, is_primary) WHERE is_primary = TRUE;
CREATE INDEX idx_learner_skill_mastery_level ON learner_skill_mastery(learner_id, mastery_level);
CREATE INDEX idx_learner_skill_retrievability ON learner_skill_mastery(learner_id, retrievability);
CREATE INDEX idx_skills_domain ON skills(domain) WHERE is_active = TRUE;
CREATE INDEX idx_skills_cognitive_level ON skills(cognitive_level) WHERE is_active = TRUE;

-- Comments for documentation
COMMENT ON TABLE skills IS 'Hierarchical skill taxonomy with Bloom''s cognitive levels';
COMMENT ON TABLE atom_skill_weights IS 'Many-to-many linking between atoms and skills with importance weights';
COMMENT ON TABLE learner_skill_mastery IS 'Per-skill mastery state with FSRS scheduling parameters';
COMMENT ON COLUMN atom_skill_weights.weight IS 'How much this atom measures this skill (0.0 to 1.0)';
COMMENT ON COLUMN learner_skill_mastery.retrievability IS 'FSRS retrievability: probability of recall at current time';
COMMENT ON COLUMN learner_skill_mastery.stability IS 'FSRS stability: days until retrievability drops to 90%';
