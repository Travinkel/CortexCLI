-- Migration 024: Misconception Library
--
-- Adds formal misconception tracking to enable DARPA Digital Tutor-class
-- diagnostic feedback. This table stores reusable misconceptions that can be
-- tagged to MCQ distractors and other atom response options.
--
-- Key Features:
--   1. Misconception taxonomy (overgeneralization, surface_feature, etc.)
--   2. Domain-specific categorization (networking, programming, security)
--   3. Prevalence and severity tracking for prioritization
--   4. Remediation strategies linked to each misconception
--   5. Active/inactive flag for content lifecycle management
--
-- Usage:
--   - Link MCQ distractors to misconceptions via atom_response_option.misconception_id
--   - Generate typed diagnostic feedback ("This is misconception X")
--   - Track which misconceptions learners struggle with most
--   - Auto-generate remediation atoms for common misconceptions

-- ========================================
-- MISCONCEPTION LIBRARY
-- Reusable catalog of common errors and mental model bugs
-- ========================================

CREATE TABLE IF NOT EXISTS misconception_library (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identification
    misconception_code VARCHAR(50) UNIQUE NOT NULL,  -- e.g., "NET_COLLISION_DOMAIN_CONFUSION"
    name TEXT NOT NULL,                               -- Human-readable name

    -- Classification
    category VARCHAR(50) NOT NULL,  -- overgeneralization, surface_feature, intuitive_physics,
                                    -- rote_application, feature_confusion, boundary_case, etc.
    domain VARCHAR(100),            -- networking, programming, security, systems, algorithms

    -- Psychometric data
    prevalence_rate NUMERIC(3,2),  -- 0.00-1.00: proportion of learners who fall into this trap
    severity VARCHAR(20) CHECK (severity IN ('low', 'medium', 'high', 'critical')),

    -- Remediation
    correct_mental_model TEXT,      -- What the learner SHOULD understand
    remediation_strategy TEXT,      -- How to fix this misconception
    example_errors TEXT[],          -- Array of typical error manifestations

    -- Metadata
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_misconception_domain ON misconception_library(domain);
CREATE INDEX IF NOT EXISTS idx_misconception_category ON misconception_library(category);
CREATE INDEX IF NOT EXISTS idx_misconception_severity ON misconception_library(severity);
CREATE INDEX IF NOT EXISTS idx_misconception_active ON misconception_library(is_active) WHERE is_active = TRUE;

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_misconception_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_misconception_timestamp
    BEFORE UPDATE ON misconception_library
    FOR EACH ROW
    EXECUTE FUNCTION update_misconception_timestamp();

-- Comments for documentation
COMMENT ON TABLE misconception_library IS 'Catalog of common learning misconceptions for diagnostic feedback';
COMMENT ON COLUMN misconception_library.misconception_code IS 'Unique code for programmatic reference (e.g., NET_COLLISION_DOMAIN_CONFUSION)';
COMMENT ON COLUMN misconception_library.category IS 'Type of misconception (overgeneralization, surface_feature, intuitive_physics, etc.)';
COMMENT ON COLUMN misconception_library.prevalence_rate IS 'Proportion of learners who demonstrate this misconception (0.00-1.00)';
COMMENT ON COLUMN misconception_library.severity IS 'Impact level: low (minor confusion), medium (significant gap), high (blocks progress), critical (fundamental misunderstanding)';
COMMENT ON COLUMN misconception_library.remediation_strategy IS 'Pedagogical approach to address this misconception';
