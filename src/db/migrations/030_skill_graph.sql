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
