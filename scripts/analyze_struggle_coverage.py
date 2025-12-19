#!/usr/bin/env python
"""Analyze atom coverage for struggle sections and identify gaps."""

from src.db.database import engine
from sqlalchemy import text
from collections import defaultdict

# Failure mode to recommended atom types mapping
FM_ATOM_TYPES = {
    'FM1': ['mcq', 'matching'],           # Confusions -> discrimination tasks
    'FM2': ['parsons', 'flashcard'],      # Process -> ordering tasks
    'FM3': ['numeric', 'flashcard'],      # Calculation -> computation practice
    'FM4': ['mcq'],                        # Application -> scenario-based
    'FM5': ['flashcard', 'cloze'],        # Vocabulary -> retrieval practice
    'FM6': ['matching', 'mcq'],           # Comparison -> discrimination
    'FM7': ['mcq'],                        # Troubleshooting -> diagnostic scenarios
}

# All learning atom types
ALL_TYPES = ['flashcard', 'cloze', 'mcq', 'true_false', 'matching', 'parsons', 'numeric']


def get_coverage():
    """Get atom coverage for struggle sections."""
    query = '''
    WITH expanded_sections AS (
        SELECT DISTINCT
            sw.module_number,
            sw.section_id as pattern,
            sw.severity,
            sw.failure_modes,
            cs.section_id as actual_section
        FROM struggle_weights sw
        JOIN ccna_sections cs ON
            (sw.section_id = cs.section_id) OR
            (sw.section_id LIKE '%%.x' AND cs.section_id LIKE REPLACE(sw.section_id, '.x', '.') || '%%')
    )
    SELECT
        es.module_number,
        es.severity,
        es.failure_modes,
        la.atom_type,
        COUNT(DISTINCT la.id) as atom_count
    FROM expanded_sections es
    LEFT JOIN learning_atoms la ON la.ccna_section_id = es.actual_section
    WHERE la.front IS NOT NULL AND la.front != ''
    GROUP BY es.module_number, es.severity, es.failure_modes, la.atom_type
    ORDER BY
        CASE es.severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 ELSE 3 END,
        es.module_number,
        la.atom_type
    '''

    with engine.connect() as conn:
        result = conn.execute(text(query))
        return result.fetchall()


def analyze_gaps(coverage):
    """Analyze gaps between existing atoms and FM-recommended types."""
    # Group by module
    module_data = defaultdict(lambda: {'severity': None, 'failure_modes': [], 'atoms': defaultdict(int)})

    for row in coverage:
        m = row.module_number
        module_data[m]['severity'] = row.severity
        if row.failure_modes:
            module_data[m]['failure_modes'] = row.failure_modes
        if row.atom_type:
            module_data[m]['atoms'][row.atom_type] = row.atom_count

    gaps = []
    for module, data in sorted(module_data.items()):
        severity = data['severity']
        fms = data['failure_modes'] or []
        existing = data['atoms']

        # Get recommended types from failure modes
        recommended = set()
        for fm in fms:
            recommended.update(FM_ATOM_TYPES.get(fm, []))

        # Find missing types
        for atype in recommended:
            count = existing.get(atype, 0)
            if count < 10:  # Consider < 10 as a gap
                gaps.append({
                    'module': module,
                    'severity': severity,
                    'atom_type': atype,
                    'existing': count,
                    'failure_modes': fms
                })

    return gaps


def main():
    coverage = get_coverage()

    print("=" * 70)
    print("ATOM COVERAGE FOR STRUGGLE SECTIONS")
    print("=" * 70)

    current_module = None
    for row in coverage:
        if row.module_number != current_module:
            current_module = row.module_number
            print(f"\nModule {row.module_number} ({row.severity}) - FM: {row.failure_modes}")
            print("-" * 50)
        if row.atom_type:
            print(f"  {row.atom_type:15} {row.atom_count:4} atoms")

    gaps = analyze_gaps(coverage)

    print("\n" + "=" * 70)
    print("GAPS - ATOM TYPES NEEDED FOR FAILURE MODES")
    print("=" * 70)

    # Group gaps by severity
    critical_gaps = [g for g in gaps if g['severity'] == 'critical']
    high_gaps = [g for g in gaps if g['severity'] == 'high']
    medium_gaps = [g for g in gaps if g['severity'] == 'medium']

    for label, gap_list in [('CRITICAL', critical_gaps), ('HIGH', high_gaps), ('MEDIUM', medium_gaps)]:
        if gap_list:
            print(f"\n{label} PRIORITY:")
            for g in gap_list:
                print(f"  Module {g['module']:2}: needs {g['atom_type']:12} (have {g['existing']:3}, FM: {g['failure_modes']})")

    # Generate commands
    print("\n" + "=" * 70)
    print("GENERATION COMMANDS")
    print("=" * 70)

    # Group gaps by module and type
    gen_cmds = defaultdict(set)
    for g in gaps:
        gen_cmds[g['module']].add(g['atom_type'])

    for module in sorted(gen_cmds.keys()):
        types = ','.join(sorted(gen_cmds[module]))
        print(f"python scripts/atoms/generate_struggle_atoms.py --module {module} --types {types} --save --limit 15")


if __name__ == '__main__':
    main()
