# How To: Generate Learning Atoms

Create learning atoms (flashcards, MCQs, cloze deletions, numeric drills) from source content.

---

## Atom Types

| Type | Description | Effect Size | Study Location |
|------|-------------|-------------|----------------|
| `flashcard` | Question/answer pairs | d=0.7 | Anki / CLI |
| `cloze` | Fill-in-the-blank | d=0.7 | Anki |
| `mcq` | Multiple choice | d=0.6 | CLI |
| `true_false` | True/false statements | d=0.5 | CLI |
| `matching` | Match pairs | d=0.6 | CLI |
| `parsons` | Code block ordering | d=0.6 | CLI |
| `numeric` | Calculation drills (subnetting, binary) | d=0.7 | CLI |
| `compare` | Concept comparison | d=0.6 | CLI |

### Current Atom Distribution (CCNA)

| Module | Atom Count | Primary Types | Notes |
|--------|------------|---------------|-------|
| Module 5 | 118 atoms | MATCHING, FLASHCARD, MCQ | Ethernet/Switching |
| Module 8 | 89 atoms | NUMERIC | Subnetting calculations |
| Total | 241 atoms | Mixed | Weak area targeting |

---

## Method 1: Sync from Notion

The primary method for importing flashcards.

### Required Notion Properties

| Property | Type | Required |
|----------|------|----------|
| Question | Title | Yes |
| Answer | Rich Text | Yes |
| CardID | Text | No |
| Concept | Relation | No |
| Module | Relation | No |

### Run Sync

```bash
# Full sync
nls sync notion

# Incremental sync
nls sync notion --incremental
```

### Verify Import

```bash
psql -d notion_learning_sync -c "SELECT COUNT(*), atom_type FROM clean_atoms GROUP BY atom_type;"
```

---

## Method 2: Import from Anki

Import existing Anki decks:

```bash
# Import configured deck
nls anki import

# Import specific deck
nls anki import --deck "CCNA Study"

# Preview
nls anki import --dry-run
```

---

## Method 3: AI Generation

Generate atoms from source documents.

### Prerequisites

Configure AI provider in `.env`:
```bash
GEMINI_API_KEY=your_api_key
AI_MODEL=gemini-2.0-flash
```

### Generate from Text

```bash
python scripts/generate_atoms.py --module 1 --batch-size 10
```

---

## Method 4: Advanced Hydration

Generate complex, interactive atoms for the Adaptive Tutor.

### Math Pass (Calculation Drills)

Generates `numeric` atoms for Subnetting, IPv6, and Binary:

```bash
python scripts/force_hydrate.py
```

**Output**: 89 NUMERIC atoms for Module 8 (subnetting calculations)

### Procedural Pass (CLI Ordering)

Generates `parsons` problems for router/switch configuration:

```bash
python scripts/slow_hydrate.py
```

### Visual Hydration (Diagrams)

Converts topology descriptions to Mermaid.js diagrams:

```bash
python scripts/hydrate_visuals.py
```

### Sync to CLI Deck

Export database content to JSON for CLI study:

```bash
python scripts/db_to_deck.py
```

---

## Method 5: Struggle-Targeted Generation

Generate atoms specifically for weak areas defined in `struggles.yaml`.

### Generate for Weak Modules

```bash
# Generate for all critical-severity modules
python scripts/generate_struggle_package.py --severity critical

# Generate for specific module
python scripts/generate_struggle_package.py --module 5
```

### Atom Type Selection by Failure Mode

The generator selects atom types based on the failure modes in `struggles.yaml`:

| Failure Mode | Generated Atom Types |
|--------------|----------------------|
| `DISCRIMINATION` | MCQ, MATCHING |
| `INTEGRATION` | FLASHCARD, COMPARE |
| `ENCODING` | FLASHCARD, CLOZE |
| `SUBNETTING_CALCULATION` | NUMERIC |
| `CLI_MODE_MAPPING` | PARSONS |
| `PACKET_WALKTHROUGH` | MATCHING, FLASHCARD |

### Example: Module 5 Generation

For Module 5 (Ethernet/Switching) with failure modes `["DISCRIMINATION", "INTEGRATION"]`:

```bash
# Generated: 118 atoms
# - 45 MATCHING atoms (MAC address table operations)
# - 38 FLASHCARD atoms (frame fields, switching methods)
# - 35 MCQ atoms (duplex, switching logic)
```

---

## Atom Type Guidelines

### Flashcards

Best for declarative knowledge (facts, definitions).

**Rule**: 8-25 words question, 10-20 words answer, single concept.

**Fidelity Tracking**: Each flashcard tracks:
- `is_hydrated`: True if scenario details added beyond source text
- `fidelity_type`: `verbatim_extract`, `rephrased_fact`, or `ai_scenario_enrichment`
- `source_fact_basis`: Exact phrase from source content

### Parsons Problems

Best for CLI syntax and configuration order.

**Example**: "Order the commands to configure SSH."

**Lab Skills Chain**: `struggles.yaml` defines procedural skills for Packet Tracer:
- Initial router configuration sequence
- SSH configuration sequence
- Interface IPv4/IPv6 configuration

### Numeric Atoms

Best for calculation speed (Subnetting, Binary, Hexadecimal).

**Content Structure**:
```json
{
  "question": "Given IP 192.168.10.50/26, what is the network address?",
  "answer": "192.168.10.0",
  "answer_type": "ip_address",
  "steps": "/26 = 255.255.255.192 mask. 50 AND 192 = 0. Network: 192.168.10.0",
  "difficulty": 2
}
```

**Difficulty Levels**:
| Level | Description | Example |
|-------|-------------|---------|
| 1 | Single conversion | Convert 192 to binary |
| 2 | Multi-step calculation | Find network address for IP/mask |
| 3 | Full subnet design | Design VLSM scheme for requirements |

### Matching Atoms

Best for discrimination training between similar concepts.

**Maximum**: 6 pairs (working memory limit)

**Example Use Cases**:
- MAC address table operations
- Frame field purposes
- Switching method characteristics

### Mermaid Diagrams

Best for topologies and processes. Stored in `media_code` column.

---

## Quality Thresholds

| Grade | Criteria | Action |
|-------|----------|--------|
| **A** | Perfect atomicity, clear context | Auto-Approve |
| **B** | Good, minor phrasing issues | Auto-Approve |
| **C** | Verbose or slightly ambiguous | Review |
| **D** | Multiple concepts or confusing | Rewrite |
| **F** | Hallucination or broken format | Reject |

---

## Troubleshooting

### "No JSON files found" in CLI

**Cause**: Generated to database but not exported.
**Fix**: Run `python scripts/db_to_deck.py`.

### "429 Resource Exhausted"

**Cause**: API rate limit.
**Fix**: Use `scripts/slow_hydrate.py` with `concurrency=1`.

### "No Diagram Generated"

**Cause**: Insufficient visual context.
**Fix**: Add `[VISUAL: description]` to the atom and re-run `hydrate_visuals.py`.

---

## See Also

- [Run Quality Audit](run-quality-audit.md)
- [Configuration Reference](../reference/configuration.md)
- [Struggle-Aware System](../explanation/struggle-aware-system.md) - How struggles drive atom generation
- [Database Schema](../reference/database-schema.md) - Atom storage and tracking
