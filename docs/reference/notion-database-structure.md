# Notion Database Structure Reference

**Version**: 1.0
**Last Updated**: December 5, 2025

---

## Overview

This reference documents the Notion database structures expected by NLS for content synchronization. Each database maps to a staging table and subsequently to canonical tables.

---

## Database Hierarchy

```
Programs (top-level)
    └── Tracks (course groupings)
        └── Modules (weekly/unit content)
            └── Concepts (semantic groupings)
                └── Flashcards (learning atoms)
```

---

## Flashcards Database

**Staging Table**: `stg_flashcards`
**Canonical Table**: `learning_atoms`

### Required Properties

| Property | Notion Type | Maps To | Description |
|----------|-------------|---------|-------------|
| `Name` | Title | `card_id` | Unique identifier |
| `Front` | Rich Text | `front` | Question/prompt |
| `Back` | Rich Text | `back` | Answer/explanation |
| `Type` | Select | `atom_type` | Card type |

### Type Options

```
flashcard    → Anki (basic Q&A)
cloze        → Anki (fill-in-blank)
mcq          → NLS CLI (multiple choice)
true_false   → NLS CLI (binary)
parsons      → NLS CLI (code ordering)
matching     → NLS CLI (pair matching)
```

### Optional Properties

| Property | Notion Type | Maps To | Description |
|----------|-------------|---------|-------------|
| `Concept` | Relation | `concept_id` | Link to concept |
| `Module` | Relation | `module_id` | Link to module |
| `Tags` | Multi-select | (parsed) | Topic categorization |
| `Difficulty` | Number | `difficulty` | 0.0-1.0 scale |
| `Quality` | Select | `quality_grade` | A/B/C/D/F |
| `Status` | Select | `status` | draft/review/approved |
| `Source` | Select | `source` | notion/ai_batch/manual |

### Example JSONB (Staging)

```json
{
  "Name": {"title": [{"text": {"content": "TCP-001"}}]},
  "Front": {"rich_text": [{"text": {"content": "What does TCP stand for?"}}]},
  "Back": {"rich_text": [{"text": {"content": "Transmission Control Protocol"}}]},
  "Type": {"select": {"name": "flashcard"}},
  "Concept": {"relation": [{"id": "abc123"}]},
  "Difficulty": {"number": 0.3}
}
```

---

## Concepts Database

**Staging Table**: `stg_concepts`
**Canonical Table**: `concepts`

### Required Properties

| Property | Notion Type | Maps To | Description |
|----------|-------------|---------|-------------|
| `Name` | Title | `name` | Concept name |

### Optional Properties

| Property | Notion Type | Maps To | Description |
|----------|-------------|---------|-------------|
| `Description` | Rich Text | `description` | Explanation |
| `Module` | Relation | `module_id` | Parent module |
| `Cluster` | Relation | `cluster_id` | Concept grouping |
| `Prerequisites` | Relation | (explicit_prerequisites) | Required concepts |
| `Knowledge Type` | Select | `knowledge_type` | DEC/PROC/APP |

### Knowledge Type Options

```
declarative   → Facts, definitions (DEC)
procedural    → Steps, processes (PROC)
application   → Applied scenarios (APP)
```

---

## Modules Database

**Staging Table**: `stg_modules`
**Canonical Table**: `learning_modules`

### Required Properties

| Property | Notion Type | Maps To | Description |
|----------|-------------|---------|-------------|
| `Name` | Title | `name` | Module name |
| `Number` | Number | `week_order` | Sequence |

### Optional Properties

| Property | Notion Type | Maps To | Description |
|----------|-------------|---------|-------------|
| `Track` | Relation | `track_id` | Parent track |
| `Description` | Rich Text | `description` | Overview |
| `Status` | Select | `status` | Progress state |

---

## Tracks Database

**Staging Table**: `stg_tracks`
**Canonical Table**: `clean_tracks`

### Properties

| Property | Notion Type | Maps To | Description |
|----------|-------------|---------|-------------|
| `Name` | Title | `name` | Track name |
| `Program` | Relation | `program_id` | Parent program |
| `Description` | Rich Text | `description` | Overview |

---

## Programs Database

**Staging Table**: `stg_programs`
**Canonical Table**: `clean_programs`

### Properties

| Property | Notion Type | Maps To | Description |
|----------|-------------|---------|-------------|
| `Name` | Title | `name` | Program name |
| `Description` | Rich Text | `description` | Overview |

---

## Property Type Mappings

| Notion Type | Python Type | SQL Type |
|-------------|-------------|----------|
| Title | `str` | `TEXT` |
| Rich Text | `str` | `TEXT` |
| Number | `float` | `NUMERIC` |
| Select | `str` | `TEXT` |
| Multi-select | `List[str]` | `TEXT[]` |
| Relation | `List[UUID]` | `UUID[]` |
| Checkbox | `bool` | `BOOLEAN` |
| Date | `datetime` | `TIMESTAMP` |
| URL | `str` | `TEXT` |

---

## Sync Behavior

### Create

New Notion pages create new staging records with:
- `notion_id`: Page ID from Notion
- `properties`: Full JSONB of properties
- `synced_at`: Current timestamp

### Update

Modified pages update staging records:
- `properties`: Overwritten with new JSONB
- `synced_at`: Updated timestamp

### Delete

Deleted pages:
- Staging record marked `is_deleted = true`
- Canonical record soft-deleted
- Anki note optionally suspended

---

## Validation Rules

### Front (Question)

- Minimum 20 characters
- Maximum 200 characters (recommended)
- No leading/trailing whitespace
- Must end with `?` for questions (optional)

### Back (Answer)

- Minimum 5 characters
- Maximum 500 characters (recommended)
- No leading/trailing whitespace

### Cloze Format

```
Text with {{c1::hidden}} and {{c2::another}} deletion.
```

- Maximum 5 deletions per card
- Each deletion should be a single concept
- `c1`, `c2`, `c3`... in logical sequence

---

## Related Documentation

- [Notion Setup Guide](../getting-started/notion-setup.md)
- [Database Schema](../architecture/database-schema.md)
- [Cleaning Pipeline](../architecture/cleaning-pipeline.md)
