#!/usr/bin/env python
"""Import struggle sections based on cognitive analysis."""

from src.db.database import engine
from sqlalchemy import text

# Your struggle sections with failure mode analysis
struggle_data = [
    # Module 2: Command modes, access methods, passwords (FM2 Process, FM5 Vocab)
    {
        'module': 2,
        'sections': ['2.1.4', '2.1.5', '2.2.1', '2.2.2', '2.2.4', '2.3.1', '2.3.2', '2.3.3', '2.3.5', '2.4.2', '2.4.3', '2.4.5', '2.6.2', '2.7.1', '2.7.4', '2.8.1', '2.8.2'],
        'severity': 'high',
        'failure_modes': ['FM2', 'FM5'],
        'notes': 'Access methods, command modes, password config, interface verification'
    },

    # Module 3: OSI/TCP-IP, encapsulation (FM1 Confusion, FM6 Comparison)
    {
        'module': 3,
        'sections': ['3.1.2', '3.1.3', '3.2.x', '3.3.x'],
        'severity': 'critical',
        'failure_modes': ['FM1', 'FM6'],
        'notes': 'OSI vs TCP/IP mapping, PDU names, encapsulation/decapsulation'
    },

    # Module 4: Physical layer, cable types (FM1 Confusion, FM5 Vocab)
    {
        'module': 4,
        'sections': ['4.1.x', '4.2.1', '4.2.2', '4.2.3', '4.3.x'],
        'severity': 'medium',
        'failure_modes': ['FM1', 'FM5'],
        'notes': 'Cable types, bandwidth vs throughput, encoding'
    },

    # Module 5: Number systems (FM3 Calculation)
    {
        'module': 5,
        'sections': ['5.1.1', '5.1.2', '5.1.4', '5.1.5', '5.2.1', '5.2.2', '5.2.3', '5.3.1', '5.3.2', '5.3.3', '5.4.1', '5.4.2'],
        'severity': 'critical',
        'failure_modes': ['FM3'],
        'notes': 'Binary/decimal/hex conversions, AND operations, positional notation'
    },

    # Module 7: Ethernet switching (FM2 Process, FM1 Confusion)
    {
        'module': 7,
        'sections': ['7.1.2', '7.1.3', '7.1.4', '7.2.1', '7.2.2', '7.2.3', '7.2.4', '7.2.5', '7.2.6'],
        'severity': 'high',
        'failure_modes': ['FM2', 'FM1'],
        'notes': 'CAM table, switch forwarding, frame vs Ethernet frame'
    },

    # Module 8: Network layer (FM1 Confusion, FM4 Application)
    {
        'module': 8,
        'sections': ['8.1.x', '8.2.x', '8.3.x'],
        'severity': 'high',
        'failure_modes': ['FM1', 'FM4'],
        'notes': 'IPv4/IPv6 headers, routing vs switching'
    },

    # Module 9: ARP (FM2 Process, FM4 Application)
    {
        'module': 9,
        'sections': ['9.1.x', '9.2.x', '9.3.x'],
        'severity': 'high',
        'failure_modes': ['FM2', 'FM4'],
        'notes': 'ARP process, ARP table, ND protocol'
    },

    # Module 10: Router config (FM2 Process)
    {
        'module': 10,
        'sections': ['10.1.x', '10.2.x', '10.3.x', '10.4.x'],
        'severity': 'high',
        'failure_modes': ['FM2'],
        'notes': 'Router boot, IOS navigation, interface config'
    },

    # Module 11: IPv4 addressing - FULL module (FM3 Calculation, FM4 Application)
    {
        'module': 11,
        'sections': ['11.x'],
        'severity': 'critical',
        'failure_modes': ['FM3', 'FM4'],
        'notes': 'Subnetting, VLSM, network/broadcast calculations'
    },

    # Module 12: IPv6 - FULL module (FM1 Confusion, FM3 Calculation)
    {
        'module': 12,
        'sections': ['12.x'],
        'severity': 'critical',
        'failure_modes': ['FM1', 'FM3'],
        'notes': 'IPv6 address types, compression, EUI-64'
    },

    # Module 13: ICMP (FM4 Application, FM7 Troubleshooting)
    {
        'module': 13,
        'sections': ['13.1.x', '13.2.x'],
        'severity': 'medium',
        'failure_modes': ['FM4', 'FM7'],
        'notes': 'ICMPv4 vs ICMPv6, ping/traceroute interpretation'
    },

    # Module 14: Transport - FULL module (FM1 Confusion, FM2 Process)
    {
        'module': 14,
        'sections': ['14.x'],
        'severity': 'high',
        'failure_modes': ['FM1', 'FM2'],
        'notes': 'TCP vs UDP, 3-way handshake, port numbers'
    },

    # Module 15: Application layer - FULL module (FM5 Vocab, FM6 Comparison)
    {
        'module': 15,
        'sections': ['15.x'],
        'severity': 'medium',
        'failure_modes': ['FM5', 'FM6'],
        'notes': 'DNS, DHCP, HTTP/HTTPS, protocol operations'
    },

    # Module 16: Security - FULL module (FM1 Confusion, FM7 Troubleshooting)
    {
        'module': 16,
        'sections': ['16.x'],
        'severity': 'medium',
        'failure_modes': ['FM1', 'FM7'],
        'notes': 'Threat types, attack categories, mitigation'
    },

    # Module 17: Small network - FULL module (FM2 Process, FM7 Troubleshooting)
    {
        'module': 17,
        'sections': ['17.x'],
        'severity': 'medium',
        'failure_modes': ['FM2', 'FM7'],
        'notes': 'Network design, troubleshooting methodology'
    },
]

# Severity to weight mapping
SEVERITY_WEIGHT = {'critical': 1.0, 'high': 0.75, 'medium': 0.5, 'low': 0.25}


def import_struggles():
    """Import struggle sections to database."""
    with engine.connect() as conn:
        # Clear existing
        conn.execute(text('DELETE FROM struggle_weights'))

        inserted = 0
        for item in struggle_data:
            module = item['module']
            severity = item['severity']
            weight = SEVERITY_WEIGHT[severity]
            failure_modes = item['failure_modes']
            notes = item['notes']

            for section in item['sections']:
                conn.execute(text('''
                    INSERT INTO struggle_weights (module_number, section_id, severity, weight, failure_modes, notes)
                    VALUES (:module, :section, :severity, :weight, :fm, :notes)
                    ON CONFLICT (module_number, section_id) DO UPDATE SET
                        severity = EXCLUDED.severity,
                        weight = EXCLUDED.weight,
                        failure_modes = EXCLUDED.failure_modes,
                        notes = EXCLUDED.notes
                '''), {
                    'module': module,
                    'section': section,
                    'severity': severity,
                    'weight': weight,
                    'fm': failure_modes,
                    'notes': notes
                })
                inserted += 1

        conn.commit()
        print(f'Imported {inserted} struggle sections')

    # Verify
    with engine.connect() as conn:
        result = conn.execute(text('''
            SELECT severity, COUNT(*) as cnt
            FROM struggle_weights
            GROUP BY severity
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    ELSE 4
                END
        '''))
        print('\nStruggle sections by severity:')
        for row in result:
            print(f'  {row.severity}: {row.cnt}')


if __name__ == '__main__':
    import_struggles()
