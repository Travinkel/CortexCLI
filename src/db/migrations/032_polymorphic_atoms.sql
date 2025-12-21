-- Migration 032: Polymorphic Atoms with ICAP Framework
--
-- Adds JSONB content/grading_logic columns and ICAP Framework metadata
-- to learning_atoms table. This enables:
--   1. Polymorphic content (atom-type-specific payloads)
--   2. Type-specific grading rules (replaces monolithic evaluator)
--   3. ICAP Framework classification (replaces Bloom's Taxonomy)
--   4. Greenlight ownership for runtime atoms
--
-- Key Features:
--   - content JSONB: Stores prompt, options, code, etc. per atom type
--   - grading_logic JSONB: Stores mode, correct_answer, pattern, etc.
--   - engagement_mode: ICAP mode (passive, active, constructive, interactive)
--   - element_interactivity: Cognitive Load Theory factor (0.0-1.0)
--   - knowledge_dimension: Krathwohl's dimension (factual, conceptual, procedural, metacognitive)
--   - owner: Which system runs the atom (cortex, greenlight)
--
-- Backward Compatibility:
--   - front/back columns retained for legacy atoms
--   - New atoms can use either front/back OR content JSONB
--   - Migration is additive (no data changes)

-- ========================================
-- ADD POLYMORPHIC CONTENT COLUMNS
-- ========================================

-- JSONB content column for atom-type-specific payload
ALTER TABLE learning_atoms
ADD COLUMN IF NOT EXISTS content JSONB;

-- JSONB grading_logic column for grading configuration
ALTER TABLE learning_atoms
ADD COLUMN IF NOT EXISTS grading_logic JSONB;

-- ========================================
-- ADD ICAP FRAMEWORK COLUMNS
-- ========================================

-- Engagement mode (replaces Bloom's taxonomy levels)
ALTER TABLE learning_atoms
ADD COLUMN IF NOT EXISTS engagement_mode TEXT DEFAULT 'active';

-- Element interactivity (Cognitive Load Theory)
ALTER TABLE learning_atoms
ADD COLUMN IF NOT EXISTS element_interactivity NUMERIC(3,2) DEFAULT 0.50;

-- Knowledge dimension (Krathwohl, 2002)
ALTER TABLE learning_atoms
ADD COLUMN IF NOT EXISTS knowledge_dimension TEXT DEFAULT 'factual';

-- Atom ownership (cortex vs greenlight)
ALTER TABLE learning_atoms
ADD COLUMN IF NOT EXISTS owner TEXT DEFAULT 'cortex';

-- ========================================
-- CONSTRAINTS
-- ========================================

-- Validate engagement_mode values
ALTER TABLE learning_atoms
ADD CONSTRAINT valid_engagement_mode
CHECK (engagement_mode IN ('passive', 'active', 'constructive', 'interactive'));

-- Validate knowledge_dimension values
ALTER TABLE learning_atoms
ADD CONSTRAINT valid_knowledge_dimension
CHECK (knowledge_dimension IN ('factual', 'conceptual', 'procedural', 'metacognitive'));

-- Validate owner values
ALTER TABLE learning_atoms
ADD CONSTRAINT valid_owner
CHECK (owner IN ('cortex', 'greenlight'));

-- Validate element_interactivity range
ALTER TABLE learning_atoms
ADD CONSTRAINT valid_element_interactivity
CHECK (element_interactivity BETWEEN 0.00 AND 1.00);

-- ========================================
-- INDEXES
-- ========================================

-- Index for ICAP-based atom selection
CREATE INDEX IF NOT EXISTS idx_atoms_engagement_mode
ON learning_atoms(engagement_mode);

CREATE INDEX IF NOT EXISTS idx_atoms_knowledge_dimension
ON learning_atoms(knowledge_dimension);

CREATE INDEX IF NOT EXISTS idx_atoms_owner
ON learning_atoms(owner);

-- GIN index for JSONB content queries
CREATE INDEX IF NOT EXISTS idx_atoms_content_gin
ON learning_atoms USING GIN (content);

CREATE INDEX IF NOT EXISTS idx_atoms_grading_logic_gin
ON learning_atoms USING GIN (grading_logic);

-- ========================================
-- COMMENTS
-- ========================================

COMMENT ON COLUMN learning_atoms.content IS 'Polymorphic JSONB content payload (prompt, options, code, etc.) - replaces front/back for new atom types';
COMMENT ON COLUMN learning_atoms.grading_logic IS 'Polymorphic JSONB grading configuration (mode, correct_answer, pattern, tolerance, etc.)';
COMMENT ON COLUMN learning_atoms.engagement_mode IS 'ICAP Framework engagement mode: passive (receiving), active (manipulating), constructive (generating), interactive (co-creating)';
COMMENT ON COLUMN learning_atoms.element_interactivity IS 'Cognitive Load Theory factor: 0.0 (low load) to 1.0 (high load)';
COMMENT ON COLUMN learning_atoms.knowledge_dimension IS 'Krathwohl knowledge dimension: factual (terminology), conceptual (principles), procedural (skills), metacognitive (self-awareness)';
COMMENT ON COLUMN learning_atoms.owner IS 'Execution owner: cortex (terminal-based) or greenlight (IDE/runtime)';
