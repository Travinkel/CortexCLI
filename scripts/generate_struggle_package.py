#!/usr/bin/env python
"""
Generate complete learning package for struggle areas.

Creates:
1. Anki filtered deck search queries
2. Gap analysis for missing atom types
3. Generation commands for missing atoms
"""

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

# Your struggle data with failure modes
STRUGGLE_MODULES = {
    2: {'severity': 'high', 'fm': ['FM2', 'FM5'], 'notes': 'Command modes, access methods'},
    3: {'severity': 'critical', 'fm': ['FM1', 'FM6'], 'notes': 'OSI/TCP-IP, encapsulation'},
    4: {'severity': 'medium', 'fm': ['FM1', 'FM5'], 'notes': 'Physical layer, cables'},
    5: {'severity': 'critical', 'fm': ['FM3'], 'notes': 'Binary/decimal/hex'},
    7: {'severity': 'high', 'fm': ['FM2', 'FM1'], 'notes': 'Ethernet switching, CAM'},
    8: {'severity': 'high', 'fm': ['FM1', 'FM4'], 'notes': 'Network layer, routing'},
    9: {'severity': 'high', 'fm': ['FM2', 'FM4'], 'notes': 'ARP, ND protocol'},
    10: {'severity': 'high', 'fm': ['FM2'], 'notes': 'Router config'},
    11: {'severity': 'critical', 'fm': ['FM3', 'FM4'], 'notes': 'Subnetting, VLSM'},
    12: {'severity': 'critical', 'fm': ['FM1', 'FM3'], 'notes': 'IPv6 addressing'},
    13: {'severity': 'medium', 'fm': ['FM4', 'FM7'], 'notes': 'ICMP, ping/traceroute'},
    14: {'severity': 'high', 'fm': ['FM1', 'FM2'], 'notes': 'TCP/UDP, ports'},
    15: {'severity': 'medium', 'fm': ['FM5', 'FM6'], 'notes': 'Application protocols'},
    16: {'severity': 'medium', 'fm': ['FM1', 'FM7'], 'notes': 'Security'},
    17: {'severity': 'medium', 'fm': ['FM2', 'FM7'], 'notes': 'Small network design'},
}


def get_coverage():
    """Get actual atom coverage by module and type."""
    query = '''
    SELECT
        CAST(SPLIT_PART(la.ccna_section_id, '.', 1) AS INTEGER) as module_num,
        la.atom_type,
        COUNT(*) as cnt
    FROM learning_atoms la
    WHERE la.ccna_section_id IS NOT NULL
      AND la.ccna_section_id != ''
      AND la.front IS NOT NULL
      AND la.front != ''
    GROUP BY module_num, la.atom_type
    ORDER BY module_num, la.atom_type
    '''

    coverage = defaultdict(lambda: defaultdict(int))
    with engine.connect() as conn:
        result = conn.execute(text(query))
        for row in result:
            coverage[row.module_num][row.atom_type] = row.cnt
    return coverage


def analyze_gaps(coverage):
    """Find gaps between existing atoms and FM-recommended types."""
    gaps = []

    for module, data in STRUGGLE_MODULES.items():
        existing = coverage.get(module, {})
        severity = data['severity']
        fms = data['fm']

        # Get recommended types from failure modes
        recommended = set()
        for fm in fms:
            recommended.update(FM_ATOM_TYPES.get(fm, []))

        # Check each recommended type
        for atype in recommended:
            count = existing.get(atype, 0)
            min_needed = 20 if severity == 'critical' else 15 if severity == 'high' else 10

            if count < min_needed:
                gaps.append({
                    'module': module,
                    'severity': severity,
                    'atom_type': atype,
                    'existing': count,
                    'needed': min_needed,
                    'gap': min_needed - count,
                    'failure_modes': fms,
                    'notes': data['notes']
                })

    return sorted(gaps, key=lambda x: (
        0 if x['severity'] == 'critical' else 1 if x['severity'] == 'high' else 2,
        x['module']
    ))


def generate_anki_queries():
    """Generate Anki filtered deck search queries for struggle areas."""
    queries = {}

    # By severity
    critical_mods = [m for m, d in STRUGGLE_MODULES.items() if d['severity'] == 'critical']
    high_mods = [m for m, d in STRUGGLE_MODULES.items() if d['severity'] == 'high']

    # Critical priority deck
    queries['CCNA-Struggle-Critical'] = ' OR '.join([f'"ccna_section_id:{m}.*"' for m in critical_mods])

    # High priority deck
    queries['CCNA-Struggle-High'] = ' OR '.join([f'"ccna_section_id:{m}.*"' for m in high_mods])

    # By failure mode
    for fm, types in FM_ATOM_TYPES.items():
        fm_mods = [m for m, d in STRUGGLE_MODULES.items() if fm in d['fm']]
        if fm_mods:
            mod_query = ' OR '.join([f'"ccna_section_id:{m}.*"' for m in fm_mods])
            type_query = ' OR '.join([f'atom_type:{t}' for t in types])
            queries[f'CCNA-{fm}'] = f'({mod_query}) ({type_query})'

    # By atom type for Anki (flashcard, cloze only)
    anki_types = ['flashcard', 'cloze']
    for atype in anki_types:
        struggle_mods = list(STRUGGLE_MODULES.keys())
        mod_query = ' OR '.join([f'"ccna_section_id:{m}.*"' for m in struggle_mods])
        queries[f'CCNA-Struggle-{atype.title()}'] = f'({mod_query}) atom_type:{atype}'

    return queries


def main():
    coverage = get_coverage()
    gaps = analyze_gaps(coverage)
    anki_queries = generate_anki_queries()

    print("=" * 70)
    print("COMPLETE STRUGGLE LEARNING PACKAGE")
    print("=" * 70)

    # 1. Current coverage summary
    print("\n" + "=" * 70)
    print("1. CURRENT ATOM COVERAGE FOR STRUGGLE MODULES")
    print("=" * 70)

    for module in sorted(STRUGGLE_MODULES.keys()):
        data = STRUGGLE_MODULES[module]
        mod_coverage = coverage.get(module, {})
        total = sum(mod_coverage.values())

        severity_badge = f"[{data['severity'].upper()}]"
        print(f"\nModule {module:2} {severity_badge:10} - {data['notes']}")
        print(f"  FM: {data['fm']}")
        if mod_coverage:
            for atype, cnt in sorted(mod_coverage.items()):
                print(f"    {atype:15} {cnt:4}")
        else:
            print("    NO ATOMS - needs generation")
        print(f"  Total: {total}")

    # 2. Gap analysis
    print("\n" + "=" * 70)
    print("2. GAPS - ATOM TYPES NEEDED FOR FAILURE MODES")
    print("=" * 70)

    critical_gaps = [g for g in gaps if g['severity'] == 'critical']
    high_gaps = [g for g in gaps if g['severity'] == 'high']
    medium_gaps = [g for g in gaps if g['severity'] == 'medium']

    for label, gap_list in [('CRITICAL', critical_gaps), ('HIGH', high_gaps), ('MEDIUM', medium_gaps)]:
        if gap_list:
            print(f"\n{label} PRIORITY:")
            for g in gap_list:
                print(f"  Module {g['module']:2}: {g['atom_type']:12} (have {g['existing']:3}, need {g['needed']:3}, gap: {g['gap']:3})")

    # 3. Anki filtered deck queries
    print("\n" + "=" * 70)
    print("3. ANKI FILTERED DECK SEARCH QUERIES")
    print("=" * 70)
    print("\nPaste these into Anki's filtered deck search:\n")

    for deck_name, query in anki_queries.items():
        print(f"--- {deck_name} ---")
        print(f"{query}\n")

    # 4. Generation commands
    print("\n" + "=" * 70)
    print("4. ATOM GENERATION COMMANDS")
    print("=" * 70)
    print("\nRun these to fill gaps:\n")

    # Group gaps by module
    gen_cmds = defaultdict(set)
    for g in gaps:
        gen_cmds[g['module']].add(g['atom_type'])

    for module in sorted(gen_cmds.keys()):
        types = ','.join(sorted(gen_cmds[module]))
        severity = STRUGGLE_MODULES[module]['severity']
        limit = 20 if severity == 'critical' else 15 if severity == 'high' else 10
        print(f"# Module {module} ({severity})")
        print(f"python scripts/atoms/generate_struggle_atoms.py --module {module} --types {types} --save --limit {limit}")
        print()

    # 5. Cortex manual mode commands
    print("\n" + "=" * 70)
    print("5. CORTEX MANUAL MODE COMMANDS")
    print("=" * 70)
    print("\nFor interactive CLI study:\n")

    # Critical calculation modules (FM3)
    fm3_mods = [m for m, d in STRUGGLE_MODULES.items() if 'FM3' in d['fm']]
    print(f"# FM3 (Calculation) - Modules {fm3_mods}")
    print(f".\\nls cortex manual -s {','.join(f'{m}.x' for m in fm3_mods)} -t numeric,mcq --limit 20")
    print()

    # Process modules (FM2)
    fm2_mods = [m for m, d in STRUGGLE_MODULES.items() if 'FM2' in d['fm']]
    print(f"# FM2 (Process) - Modules {fm2_mods}")
    print(f".\\nls cortex manual -s {','.join(f'{m}.x' for m in fm2_mods)} -t parsons,mcq --limit 20")
    print()

    # Confusion modules (FM1)
    fm1_mods = [m for m, d in STRUGGLE_MODULES.items() if 'FM1' in d['fm']]
    print(f"# FM1 (Confusion) - Modules {fm1_mods}")
    print(f".\\nls cortex manual -s {','.join(f'{m}.x' for m in fm1_mods)} -t mcq,matching --limit 20")


if __name__ == '__main__':
    main()
