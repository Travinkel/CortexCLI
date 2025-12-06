# Struggle-Focused Learning Path Schema

## Overview

This schema defines the format for specifying areas where you struggle, enabling the NLS CLI to generate targeted learning paths.

## Input Schema (JSON)

```json
{
  "struggles": [
    {
      "type": "module",
      "id": 7,
      "name": "DHCPv4",
      "severity": "high",
      "notes": "Can't remember the DORA process"
    },
    {
      "type": "concept",
      "name": "Subnetting",
      "severity": "critical",
      "notes": "VLSM calculations confuse me"
    },
    {
      "type": "section",
      "module": 11,
      "section": "11.4.2",
      "name": "IPv4 ACL Configuration",
      "severity": "medium"
    },
    {
      "type": "topic",
      "keywords": ["STP", "spanning tree", "BPDU"],
      "severity": "high",
      "notes": "Root bridge election process"
    }
  ],
  "preferences": {
    "focus_mode": "weakest_first",
    "max_atoms_per_session": 50,
    "include_prerequisites": true,
    "prerequisite_depth": 2
  }
}
```

## Field Definitions

### Struggle Entry

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | enum | Yes | One of: `module`, `concept`, `section`, `topic` |
| `id` | int | No | Module number (for type=module) |
| `name` | string | Yes | Human-readable name |
| `severity` | enum | Yes | `critical`, `high`, `medium`, `low` |
| `notes` | string | No | Personal notes about the struggle |
| `module` | int | No | Module number (for type=section) |
| `section` | string | No | Section ID like "11.4.2" (for type=section) |
| `keywords` | array | No | Search keywords (for type=topic) |

### Severity Levels

| Level | Meaning | Priority Weight |
|-------|---------|-----------------|
| `critical` | Cannot proceed without mastering | 4x |
| `high` | Major gaps affecting progress | 3x |
| `medium` | Needs improvement | 2x |
| `low` | Minor weakness | 1x |

### Preferences

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `focus_mode` | enum | `weakest_first` | `weakest_first`, `prerequisite_order`, `interleaved` |
| `max_atoms_per_session` | int | 50 | Limit atoms per study session |
| `include_prerequisites` | bool | true | Include prerequisite concepts |
| `prerequisite_depth` | int | 2 | Max prerequisite chain depth |

## CLI Usage

### Option 1: Inline JSON
```bash
nls struggle --json '{"struggles": [{"type": "module", "id": 7, "name": "DHCPv4", "severity": "high"}]}'
```

### Option 2: JSON File
```bash
nls struggle --file my-struggles.json
```

### Option 3: Interactive Builder
```bash
nls struggle --interactive
> Add struggle type: module
> Module number: 7
> Severity (critical/high/medium/low): high
> Notes (optional): DORA process
> Add another? (y/n): n
```

### Option 4: Quick Add (simple format)
```bash
nls struggle --add "module:7:high" --add "concept:Subnetting:critical"
```

## Output

The CLI generates a prioritized learning path:

```
╔══════════════════════════════════════════════════════════════╗
║              STRUGGLE-FOCUSED LEARNING PATH                  ║
╠══════════════════════════════════════════════════════════════╣
║ Priority 1: Subnetting (CRITICAL)                            ║
║   → 47 atoms (23 flashcard, 15 MCQ, 9 T/F)                   ║
║   → Prerequisites: Binary Math (12 atoms)                    ║
║                                                              ║
║ Priority 2: DHCPv4 - Module 7 (HIGH)                         ║
║   → 89 atoms (45 flashcard, 22 MCQ, 22 T/F)                  ║
║   → Prerequisites: IP Addressing (34 atoms)                  ║
║                                                              ║
║ Priority 3: IPv4 ACL Configuration (MEDIUM)                  ║
║   → 31 atoms (18 flashcard, 8 MCQ, 5 T/F)                    ║
╠══════════════════════════════════════════════════════════════╣
║ TOTAL: 213 atoms | Est. time: 3.5 hours                      ║
╚══════════════════════════════════════════════════════════════╝

Start studying? (y/n):
```

## Example Files

### `ccna-struggles.json`
```json
{
  "struggles": [
    {"type": "module", "id": 7, "name": "DHCPv4", "severity": "high", "notes": "DORA process"},
    {"type": "module", "id": 8, "name": "SLAAC/DHCPv6", "severity": "high"},
    {"type": "module", "id": 9, "name": "FHRP", "severity": "medium"},
    {"type": "concept", "name": "Subnetting", "severity": "critical"},
    {"type": "concept", "name": "VLSM", "severity": "critical"},
    {"type": "topic", "keywords": ["STP", "spanning tree"], "severity": "high"},
    {"type": "section", "module": 11, "section": "11.4", "name": "ACLs", "severity": "medium"}
  ],
  "preferences": {
    "focus_mode": "weakest_first",
    "max_atoms_per_session": 75,
    "include_prerequisites": true,
    "prerequisite_depth": 3
  }
}
```

## Integration with Anki

When a struggle path is generated, the system can:

1. **Tag Anki cards** with `struggle::high`, `struggle::critical`, etc.
2. **Create filtered deck** `CCNA::Struggles` with prioritized cards
3. **Adjust intervals** - struggling concepts get shorter intervals
4. **Sync mastery back** - Anki review data updates PostgreSQL mastery scores

## Database Query Strategy

For each struggle type:

```sql
-- Module struggles
SELECT * FROM clean_atoms ca
JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
WHERE cs.module_number = :module_id;

-- Concept struggles
SELECT * FROM clean_atoms ca
JOIN clean_concepts cc ON ca.concept_id = cc.id
WHERE cc.name ILIKE :concept_name;

-- Topic struggles (keyword search)
SELECT * FROM clean_atoms ca
WHERE ca.front ILIKE ANY(:keywords)
   OR ca.back ILIKE ANY(:keywords);

-- Section struggles
SELECT * FROM clean_atoms ca
JOIN ccna_sections cs ON ca.ccna_section_id = cs.section_id
WHERE cs.module_number = :module
  AND cs.section_number LIKE :section || '%';
```
