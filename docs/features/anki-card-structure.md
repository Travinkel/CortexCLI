# Anki Card Structure Specification

**Version**: 1.1
**Last Updated**: December 5, 2025

---

## Terminology: Notes vs Cards

Understanding the distinction between **notes** and **cards** is essential for working with Anki:

| Term | Definition | Example |
|------|------------|---------|
| **Note** | A container holding related fields (Front, Back, etc.) | A single Q&A pair about TCP |
| **Card** | A reviewable unit generated FROM a note | The "front → back" study card |
| **Note Type** | Template defining fields and card generation rules | "Basic", "Cloze", "Basic (reversed)" |

### Key Insight

- **1 Note can generate MULTIPLE Cards**
  - A "Basic (and reversed)" note creates 2 cards (forward + backward)
  - A Cloze note with 3 deletions `{{c1::}}{{c2::}}{{c3::}}` creates 3 cards

### In Our Codebase

| Code Term | Anki Equivalent | Database Column |
|-----------|-----------------|-----------------|
| `card_id` | Note's custom identifier | `clean_atoms.card_id` (e.g., "NET-M1-015") |
| `anki_note_id` | Anki's internal note ID | `clean_atoms.anki_note_id` (integer from AnkiConnect) |
| `anki_card_id` | Anki's internal card ID | `clean_atoms.anki_card_id` (first card of the note) |

**Note**: `card_id` is a legacy naming convention. It's actually our **sync key** for mapping atoms to Anki notes. We do NOT rename it to avoid breaking existing sync mappings.

---

## Overview

This document specifies the Anki card structures for exporting learning atoms from notion-learning-sync. Two primary note types are supported: **Basic (Flashcard)** and **Cloze**.

---

## Note Type: Basic (Flashcard)

### Required Fields

| Field | Type | Max Length | Source Column | Description |
|-------|------|------------|---------------|-------------|
| `Front` | Text/HTML | 200 chars | `clean_atoms.front` | Question or prompt |
| `Back` | Text/HTML | 500 chars | `clean_atoms.back` | Answer or content |

### Optional Fields

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `CardID` | Text | `clean_atoms.card_id` | Unique identifier (e.g., NET-M1-015-DEC) |
| `Concept` | Text | `clean_concepts.name` | Associated concept name |
| `Module` | Text | `clean_modules.name` | Associated module name |
| `KnowledgeType` | Text | Derived from card_id suffix | DEC, PROC, or APP |
| `Difficulty` | Number | `clean_atoms.difficulty` (future) | 0.0-1.0 difficulty rating |
| `Source` | Text | `clean_atoms.source` | Origin: notion, ai_batch, manual |

### Tag Structure

Tags are auto-generated from atom metadata:

```
concept::TCP_IP
module::M1_Networking_Today
knowledge::declarative
quality::A
source::ai_batch
```

### Export Format

```python
{
    "deckName": "CCNA::Module01",
    "modelName": "Basic",
    "fields": {
        "Front": "What protocol provides reliable, connection-oriented data delivery?",
        "Back": "TCP (Transmission Control Protocol)"
    },
    "tags": [
        "concept::TCP_IP",
        "module::M1",
        "knowledge::declarative",
        "quality::A"
    ],
    "options": {
        "allowDuplicate": false,
        "duplicateScope": "deck"
    }
}
```

---

## Note Type: Cloze

### Required Fields

| Field | Type | Max Length | Source | Description |
|-------|------|------------|--------|-------------|
| `Text` | Text/HTML | 500 chars | `clean_atoms.front` | Statement with cloze deletions |
| `Extra` | Text/HTML | 500 chars | `clean_atoms.back` | Additional context (optional) |

### Cloze Syntax

Anki uses `{{c1::hidden}}` syntax for cloze deletions:

```
TCP provides {{c1::reliable}} data delivery using {{c2::acknowledgments}} and {{c3::retransmissions}}.
```

This creates three cards:
- Card 1: TCP provides [...] data delivery using acknowledgments and retransmissions.
- Card 2: TCP provides reliable data delivery using [...] and retransmissions.
- Card 3: TCP provides reliable data delivery using acknowledgments and [...].

### Cloze Generation Rules

| Rule | Implementation |
|------|----------------|
| Max deletions per card | 5 (cognitive load limit) |
| Deletion scope | Single concept per deletion |
| Context preservation | Surrounding text provides retrieval cues |
| Ordering | c1, c2, c3... in logical sequence |

### Export Format

```python
{
    "deckName": "CCNA::Module01",
    "modelName": "Cloze",
    "fields": {
        "Text": "The OSI model has {{c1::7}} layers, while the TCP/IP model has {{c2::4}} layers.",
        "Extra": "OSI: Physical, Data Link, Network, Transport, Session, Presentation, Application"
    },
    "tags": [
        "concept::OSI_Model",
        "module::M3",
        "knowledge::declarative",
        "type::cloze"
    ]
}
```

---

## Atom Type to Anki Mapping

### Direct Mappings

| Atom Type | Anki Note Type | Transformation |
|-----------|---------------|----------------|
| FLASHCARD | Basic | Direct (front/back) |
| CLOZE | Cloze | Direct (uses cloze syntax) |

### Transformed Mappings

| Atom Type | Anki Note Type | Transformation Required |
|-----------|---------------|------------------------|
| MCQ | Basic | Format options in Back field |
| TRUE_FALSE | Basic | Format as statement + T/F |
| MATCHING | Basic | Format as list in Back field |

### MCQ Transformation

**Original Atom**:
```json
{
    "front": "Which layer of the OSI model handles logical addressing?",
    "back": "Network Layer",
    "options": ["Physical Layer", "Data Link Layer", "Network Layer", "Transport Layer"],
    "correct_index": 2
}
```

**Anki Basic Export**:
```
Front: Which layer of the OSI model handles logical addressing?
       A) Physical Layer
       B) Data Link Layer
       C) Network Layer
       D) Transport Layer

Back:  C) Network Layer

       The Network Layer (Layer 3) handles logical addressing (IP addresses)
       and routing decisions.
```

### TRUE_FALSE Transformation

**Original Atom**:
```json
{
    "front": "TCP is a connectionless protocol.",
    "back": "False",
    "explanation": "TCP is connection-oriented. UDP is connectionless."
}
```

**Anki Basic Export**:
```
Front: True or False: TCP is a connectionless protocol.

Back:  FALSE

       TCP is connection-oriented. UDP is connectionless.
```

### MATCHING Transformation

**Original Atom**:
```json
{
    "front": "Match the protocol to its port number:",
    "pairs": [
        {"left": "HTTP", "right": "80"},
        {"left": "HTTPS", "right": "443"},
        {"left": "FTP", "right": "21"},
        {"left": "SSH", "right": "22"}
    ]
}
```

**Anki Basic Export**:
```
Front: Match the protocol to its port number:
       1. HTTP     A. 21
       2. HTTPS    B. 22
       3. FTP      C. 80
       4. SSH      D. 443

Back:  1-C: HTTP = 80
       2-D: HTTPS = 443
       3-A: FTP = 21
       4-B: SSH = 22
```

---

## Field Formatting Guidelines

### HTML Support

Anki supports HTML in fields. Use sparingly for:
- Code blocks: `<pre><code>...</code></pre>`
- Emphasis: `<b>`, `<i>`
- Lists: `<ul>`, `<ol>`
- Line breaks: `<br>`

### Code Formatting

```html
<pre><code class="language-cisco">
Router(config)# interface GigabitEthernet0/0
Router(config-if)# ip address 192.168.1.1 255.255.255.0
Router(config-if)# no shutdown
</code></pre>
```

### Image References

Images must be stored in Anki's media folder:
```html
<img src="network_topology.png">
```

---

## Deck Structure

### Recommended Hierarchy

```
CCNA/
├── Module01_Networking_Today/
│   ├── Concepts/
│   └── Commands/
├── Module02_Basic_Switch_Config/
│   ├── Concepts/
│   └── Commands/
...
└── Module17_Building_Small_Network/
```

### Deck Naming Convention

```
{Course}::{ModuleNumber}_{ModuleName}::{SubCategory}
```

Example: `CCNA::M07_Ethernet_Switching::MAC_Addresses`

---

## Export Considerations

### Batch Export

```python
def export_to_anki(atoms: List[CleanAtom]) -> List[Dict]:
    """Export clean atoms to Anki note format."""
    notes = []
    for atom in atoms:
        if atom.atom_type == "CLOZE":
            note = create_cloze_note(atom)
        else:
            note = create_basic_note(atom)
        notes.append(note)
    return notes
```

### Duplicate Prevention

- Use `card_id` as unique identifier
- Set `duplicateScope: "deck"` to prevent deck-level duplicates
- Check `anki_note_id IS NULL` before export

### Update Strategy

For existing cards:
1. Find by `card_id` tag
2. Update fields via AnkiConnect `updateNoteFields`
3. Preserve review history

---

## FSRS Integration

### Tracked Metrics

| Metric | Anki Field | Database Column |
|--------|------------|-----------------|
| Ease factor | `factor` | `anki_ease_factor` |
| Interval | `interval` | `anki_interval_days` |
| Reviews | `reps` | `anki_review_count` |
| Lapses | `lapses` | `anki_lapses` |
| Due date | `due` | `anki_due_date` |

### Computed FSRS Metrics

| Metric | Formula | Purpose |
|--------|---------|---------|
| Stability (S) | `interval * ease * (1 - lapse_rate)` | Memory strength in days |
| Retrievability (R) | `0.9 ^ (days_since_review / S)` | Current recall probability |

---

## Quality Thresholds for Export

Only export atoms meeting these criteria:

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Quality score | >= 0.75 (Grade B) | Research-backed minimum |
| Atomicity | `is_atomic = true` | Single concept per card |
| Review status | `needs_review = false` | Human-approved content |
| Front length | <= 200 chars | Readability |
| Back length | <= 500 chars | Cognitive load |

---

## References

- [AnkiConnect API Documentation](https://foosoft.net/projects/anki-connect/)
- [Anki Manual: Note Types](https://docs.ankiweb.net/editing.html#adding-a-note-type)
- [FSRS Algorithm](https://github.com/open-spaced-repetition/fsrs4anki)
- Wozniak, P. "Twenty Rules of Formulating Knowledge"
