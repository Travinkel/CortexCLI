"""
Centralized SQL Queries for the Application.

This module contains reusable SQL queries used across multiple services.
Centralizing queries improves maintainability and makes it easier to
optimize and audit database access patterns.

Usage:
    from src.db.queries import QUERIES

    result = session.execute(text(QUERIES["struggle_atoms"]), params)
"""

from __future__ import annotations

# =============================================================================
# STRUGGLE & ADAPTIVE SESSION QUERIES
# =============================================================================

# Get struggle-weighted atoms for adaptive learning
GET_STRUGGLE_ATOMS = """
    SELECT
        vsp.atom_id as id,
        vsp.card_id,
        vsp.atom_type,
        vsp.front,
        vsp.back,
        la.concept_id,
        vsp.section_id as ccna_section_id,
        vsp.module_number,
        vsp.section_title,
        cc.name as concept_name,
        vsp.difficulty,
        vsp.stability,
        COALESCE(la.anki_lapses, 0) as lapses,
        COALESCE(la.anki_review_count, 0) as review_count,
        la.anki_due_date,
        'struggle' as source,
        vsp.priority_score
    FROM v_struggle_priority vsp
    JOIN learning_atoms la ON vsp.atom_id = la.id
    LEFT JOIN concepts cc ON la.concept_id = cc.id
    WHERE vsp.atom_type IN ('mcq', 'true_false', 'parsons', 'matching')
      AND vsp.front IS NOT NULL
      AND vsp.front != ''
      AND vsp.struggle_weight >= 0.5
      AND (la.id NOT IN :exclude_ids OR :exclude_ids IS NULL)
      {filter_clause}
    ORDER BY vsp.priority_score DESC
    LIMIT :limit
"""

# Get FSRS due atoms for review
GET_DUE_ATOMS = """
    SELECT
        ca.id,
        ca.card_id,
        ca.atom_type,
        ca.front,
        ca.back,
        ca.concept_id,
        ca.ccna_section_id,
        cs.module_number,
        cs.title as section_title,
        cc.name as concept_name,
        COALESCE(ca.anki_difficulty, 0.5) as difficulty,
        COALESCE(ca.anki_stability, 0) as stability,
        COALESCE(ca.anki_lapses, 0) as lapses,
        COALESCE(ca.anki_review_count, 0) as review_count,
        ca.anki_due_date,
        'due' as source
    FROM learning_atoms ca
    JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
    LEFT JOIN concepts cc ON ca.concept_id = cc.id
    WHERE ca.atom_type IN ('mcq', 'true_false', 'parsons', 'matching')
      AND ca.front IS NOT NULL
      AND ca.front != ''
      AND ca.anki_due_date IS NOT NULL
      AND ca.anki_due_date <= CURRENT_DATE
      AND (ca.id NOT IN :exclude_ids OR :exclude_ids IS NULL)
      {filter_clause}
    ORDER BY ca.anki_due_date ASC, ca.anki_stability ASC
    LIMIT :limit
"""

# Get new (unreviewed) atoms
GET_NEW_ATOMS = """
    SELECT
        ca.id,
        ca.card_id,
        ca.atom_type,
        ca.front,
        ca.back,
        ca.concept_id,
        ca.ccna_section_id,
        cs.module_number,
        cs.title as section_title,
        cc.name as concept_name,
        COALESCE(ca.anki_difficulty, 0.5) as difficulty,
        0 as stability,
        0 as lapses,
        0 as review_count,
        NULL as anki_due_date,
        'new' as source
    FROM learning_atoms ca
    JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
    LEFT JOIN concepts cc ON ca.concept_id = cc.id
    WHERE ca.atom_type IN ('mcq', 'true_false', 'parsons', 'matching')
      AND ca.front IS NOT NULL
      AND ca.front != ''
      AND (ca.anki_review_count IS NULL OR ca.anki_review_count = 0)
      AND (ca.id NOT IN :exclude_ids OR :exclude_ids IS NULL)
      {filter_clause}
    ORDER BY cs.display_order, RANDOM()
    LIMIT :limit
"""

# =============================================================================
# STRUGGLE STATS QUERIES
# =============================================================================

# Get all struggle weights for display
GET_STRUGGLE_WEIGHTS = """
    SELECT
        module_number,
        section_id,
        weight,
        COALESCE(severity, '') as severity,
        COALESCE(notes, '') as notes
    FROM struggle_weights
    ORDER BY module_number, section_id
"""

# Get struggle priority view data
GET_STRUGGLE_PRIORITY = """
    SELECT
        section_id,
        section_title,
        module_number,
        struggle_weight,
        atom_count,
        priority_score
    FROM v_struggle_priority
    WHERE struggle_weight > 0
    ORDER BY priority_score DESC
"""

# =============================================================================
# SECTION QUERIES
# =============================================================================

# Get CCNA sections with atom counts
GET_SECTIONS_WITH_COUNTS = """
    SELECT
        cs.section_id,
        cs.title,
        cs.module_number,
        cs.display_order,
        COUNT(la.id) as atom_count,
        COUNT(la.id) FILTER (WHERE la.atom_type = 'mcq') as mcq_count,
        COUNT(la.id) FILTER (WHERE la.atom_type = 'true_false') as tf_count
    FROM ccna_sections cs
    LEFT JOIN learning_atoms la ON la.ccna_section_id = cs.section_id
    GROUP BY cs.section_id, cs.title, cs.module_number, cs.display_order
    ORDER BY cs.display_order
"""

# Get atoms for a specific section
GET_SECTION_ATOMS = """
    SELECT
        la.id,
        la.card_id,
        la.atom_type,
        la.front,
        la.back,
        la.ccna_section_id,
        cs.module_number,
        cs.title as section_title
    FROM learning_atoms la
    JOIN ccna_sections cs ON la.ccna_section_id = cs.section_id
    WHERE (
        la.ccna_section_id = :section_id
        OR la.ccna_section_id LIKE :section_prefix
    )
      AND la.atom_type = ANY(:atom_types)
      AND la.front IS NOT NULL
      AND la.front != ''
    ORDER BY RANDOM()
    LIMIT :limit
"""

# =============================================================================
# REMEDIATION QUERIES
# =============================================================================

# Get atoms for remediation by concept
GET_REMEDIATION_ATOMS_BY_CONCEPT = """
    SELECT id
    FROM learning_atoms
    WHERE concept_id = :concept_id
    ORDER BY
        CASE knowledge_type
            WHEN 'declarative' THEN 1
            WHEN 'factual' THEN 1
            WHEN 'conceptual' THEN 2
            WHEN 'procedural' THEN 3
            ELSE 4
        END,
        COALESCE(quality_score, 0) DESC,
        created_at
    LIMIT :limit
"""

# Get atoms by section for remediation
GET_REMEDIATION_ATOMS_BY_SECTION = """
    SELECT
        id,
        card_id,
        front,
        atom_type,
        ccna_section_id
    FROM learning_atoms
    WHERE (
        ccna_section_id = :section_id
        OR ccna_section_id LIKE :section_prefix
    )
      AND atom_type = ANY(:atom_types)
      AND front IS NOT NULL
      AND front != ''
      AND id NOT IN (SELECT UNNEST(:exclude_ids))
    ORDER BY RANDOM()
    LIMIT :limit
"""

# =============================================================================
# SOCRATIC DIALOGUE QUERIES
# =============================================================================

# Get high-scaffold dialogues for struggle analysis
GET_HIGH_SCAFFOLD_DIALOGUES = """
    SELECT DISTINCT atom_id
    FROM socratic_dialogues
    WHERE learner_id = :learner_id
      AND scaffold_level_reached >= 2
    ORDER BY scaffold_level_reached DESC
    LIMIT :limit
"""

# =============================================================================
# ANKI SYNC QUERIES
# =============================================================================

# Get atoms needing Anki sync
GET_ATOMS_FOR_ANKI_SYNC = """
    SELECT
        la.id,
        la.card_id,
        la.atom_type,
        la.front,
        la.back,
        la.anki_note_id,
        la.ccna_section_id,
        cs.module_number
    FROM learning_atoms la
    LEFT JOIN ccna_sections cs ON la.ccna_section_id = cs.section_id
    WHERE la.anki_note_id IS NOT NULL
      AND (la.anki_last_synced IS NULL
           OR la.updated_at > la.anki_last_synced)
    ORDER BY la.updated_at DESC
    LIMIT :limit
"""

# =============================================================================
# STATS QUERIES
# =============================================================================

# Get atom type distribution
GET_ATOM_TYPE_DISTRIBUTION = """
    SELECT
        atom_type,
        COUNT(*) as count,
        COUNT(*) FILTER (WHERE anki_note_id IS NOT NULL) as synced_count,
        ROUND(AVG(quality_score)::numeric, 2) as avg_quality
    FROM learning_atoms
    WHERE front IS NOT NULL AND front != ''
    GROUP BY atom_type
    ORDER BY count DESC
"""

# Get module coverage stats
GET_MODULE_COVERAGE = """
    SELECT
        cs.module_number,
        COUNT(DISTINCT cs.section_id) as section_count,
        COUNT(la.id) as atom_count,
        COUNT(la.id) FILTER (WHERE la.anki_review_count > 0) as reviewed_count,
        ROUND(
            COUNT(la.id) FILTER (WHERE la.anki_review_count > 0)::numeric /
            NULLIF(COUNT(la.id), 0) * 100,
            1
        ) as coverage_pct
    FROM ccna_sections cs
    LEFT JOIN learning_atoms la ON la.ccna_section_id = cs.section_id
    GROUP BY cs.module_number
    ORDER BY cs.module_number
"""

# =============================================================================
# QUERY REGISTRY
# =============================================================================

QUERIES = {
    # Adaptive session
    "struggle_atoms": GET_STRUGGLE_ATOMS,
    "due_atoms": GET_DUE_ATOMS,
    "new_atoms": GET_NEW_ATOMS,

    # Struggle stats
    "struggle_weights": GET_STRUGGLE_WEIGHTS,
    "struggle_priority": GET_STRUGGLE_PRIORITY,

    # Sections
    "sections_with_counts": GET_SECTIONS_WITH_COUNTS,
    "section_atoms": GET_SECTION_ATOMS,

    # Remediation
    "remediation_by_concept": GET_REMEDIATION_ATOMS_BY_CONCEPT,
    "remediation_by_section": GET_REMEDIATION_ATOMS_BY_SECTION,

    # Socratic
    "high_scaffold_dialogues": GET_HIGH_SCAFFOLD_DIALOGUES,

    # Anki
    "atoms_for_sync": GET_ATOMS_FOR_ANKI_SYNC,

    # Stats
    "atom_distribution": GET_ATOM_TYPE_DISTRIBUTION,
    "module_coverage": GET_MODULE_COVERAGE,
}
