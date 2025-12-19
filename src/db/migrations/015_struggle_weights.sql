-- Migration 015: Struggle Weights Table
-- Stores user-declared struggle areas for priority weighting

-- Drop existing objects if they exist
DROP VIEW IF EXISTS v_struggle_priority CASCADE;
DROP TABLE IF EXISTS struggle_weights CASCADE;

-- Create struggle_weights table
CREATE TABLE struggle_weights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_number INTEGER NOT NULL,
    section_id TEXT,                      -- NULL means entire module
    severity TEXT NOT NULL DEFAULT 'medium',  -- critical, high, medium, low
    weight DECIMAL(3,2) NOT NULL DEFAULT 0.5, -- 0.0-1.0
    failure_modes TEXT[],                 -- ['FM1', 'FM3'] etc
    notes TEXT,

    -- NCDE dynamic adjustments
    ncde_weight DECIMAL(3,2),            -- Computed from real-time diagnosis
    last_diagnosis_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure unique combinations
    UNIQUE(module_number, section_id)
);

-- Create severity weight mapping function
CREATE OR REPLACE FUNCTION get_severity_weight(sev TEXT) RETURNS DECIMAL(3,2) AS $$
BEGIN
    RETURN CASE sev
        WHEN 'critical' THEN 1.0
        WHEN 'high' THEN 0.75
        WHEN 'medium' THEN 0.5
        WHEN 'low' THEN 0.25
        ELSE 0.5
    END;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Create priority view joining atoms with struggle weights
CREATE VIEW v_struggle_priority AS
SELECT
    la.id as atom_id,
    la.card_id,
    la.front,
    la.back,
    la.atom_type,
    cs.module_number,
    cs.section_id,
    cs.title as section_title,
    COALESCE(sw.weight, 0.3) as struggle_weight,
    COALESCE(sw.ncde_weight, 0.0) as ncde_weight,
    sw.failure_modes,
    sw.severity,
    COALESCE(la.anki_difficulty, 0.5) as difficulty,
    COALESCE(la.anki_stability, 0) as stability,
    -- Priority formula: struggle * 3 + ncde * 2 + (1-retrievability)
    (
        COALESCE(sw.weight, 0.3) * 3.0 +
        COALESCE(sw.ncde_weight, 0.0) * 2.0 +
        (1 - COALESCE(la.retrievability, 0.5)) * 1.0
    ) as priority_score
FROM learning_atoms la
JOIN ccna_sections cs ON la.ccna_section_id = cs.section_id
LEFT JOIN struggle_weights sw ON
    sw.module_number = cs.module_number AND
    (sw.section_id IS NULL OR sw.section_id = cs.section_id)
ORDER BY priority_score DESC;

-- Add indexes for performance
CREATE INDEX idx_struggle_weights_module ON struggle_weights(module_number);
CREATE INDEX idx_struggle_weights_section ON struggle_weights(section_id);
CREATE INDEX idx_struggle_weights_severity ON struggle_weights(severity);

-- Add updated_at trigger
CREATE OR REPLACE FUNCTION update_struggle_weights_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_struggle_weights_updated
    BEFORE UPDATE ON struggle_weights
    FOR EACH ROW
    EXECUTE FUNCTION update_struggle_weights_timestamp();

-- Insert some default struggle weights based on common CCNA weak areas
-- These can be customized via the CLI: nls cortex struggle --import
INSERT INTO struggle_weights (module_number, section_id, severity, weight, failure_modes, notes)
VALUES
    -- Module 5: Number Systems (FM3 - Calculation)
    (5, NULL, 'critical', 1.0, ARRAY['FM3'], 'Binary/Decimal/Hex conversions'),

    -- Module 11: IPv4 Subnetting (FM3 - Calculation)
    (11, NULL, 'critical', 1.0, ARRAY['FM3', 'FM4'], 'Subnetting, VLSM calculations'),

    -- Module 12: IPv6 (FM1 - Confusion, FM3 - Calculation)
    (12, NULL, 'critical', 1.0, ARRAY['FM1', 'FM3'], 'IPv6 addressing, EUI-64'),

    -- Module 3: OSI/TCP-IP (FM1 - Confusion)
    (3, NULL, 'high', 0.75, ARRAY['FM1', 'FM6'], 'OSI vs TCP-IP mapping, PDU names')
ON CONFLICT (module_number, section_id) DO NOTHING;

COMMENT ON TABLE struggle_weights IS 'User-declared struggle areas for study prioritization';
COMMENT ON VIEW v_struggle_priority IS 'Priority-ranked atoms based on struggle weights and NCDE diagnosis';
