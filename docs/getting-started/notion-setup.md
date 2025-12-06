# Notion Setup Guide

**Version**: 1.0
**Last Updated**: December 5, 2025

---

## Overview

Notion serves as the **source of truth** for learning content in the NLS (Notion Learning Sync) pipeline. This guide explains how to set up and configure Notion databases for optimal integration.

---

## Architecture

```
Notion Databases (Source of Truth)
         |
         | Notion API
         v
+------------------+
|  Staging Tables  |  <- Raw JSONB from Notion
|  (stg_*)         |
+--------+---------+
         |
         | Cleaning Pipeline
         v
+------------------+
| Canonical Tables |  <- Validated, clean output
| (learning_atoms, |
|  concepts, etc.) |
+--------+---------+
         |
    +----+----+
    |         |
    v         v
  Anki      NLS CLI
```

---

## Required Notion Databases

### 1. Flashcards Database

**Purpose**: Store individual learning atoms (questions/answers)

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `Name` | Title | Yes | Card identifier or short title |
| `Front` | Text | Yes | Question or prompt text |
| `Back` | Text | Yes | Answer or explanation |
| `Type` | Select | Yes | `flashcard`, `cloze`, `mcq`, `true_false`, `parsons` |
| `Concept` | Relation | No | Link to Concepts database |
| `Module` | Relation | No | Link to Modules database |
| `Tags` | Multi-select | No | Topic tags for categorization |
| `Difficulty` | Number | No | 0.0-1.0 difficulty rating |
| `Quality` | Select | No | `A`, `B`, `C`, `D`, `F` quality grade |
| `Status` | Select | No | `draft`, `review`, `approved`, `archived` |

### 2. Concepts Database

**Purpose**: Define semantic concepts that group related atoms

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `Name` | Title | Yes | Concept name (e.g., "TCP/IP Model") |
| `Description` | Text | No | Detailed concept explanation |
| `Module` | Relation | No | Parent module |
| `Cluster` | Relation | No | Concept cluster for grouping |
| `Prerequisites` | Relation | No | Required prerequisite concepts |
| `Knowledge Type` | Select | No | `declarative`, `procedural`, `application` |

### 3. Modules Database

**Purpose**: Organize content into course modules

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `Name` | Title | Yes | Module name |
| `Number` | Number | Yes | Module sequence number |
| `Track` | Relation | No | Parent track/course |
| `Description` | Text | No | Module overview |
| `Status` | Select | No | `not_started`, `in_progress`, `completed` |

### 4. Tracks Database (Optional)

**Purpose**: Group modules into learning tracks/courses

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `Name` | Title | Yes | Track name (e.g., "CCNA ITN") |
| `Program` | Relation | No | Parent certification program |
| `Description` | Text | No | Track overview |

### 5. Programs Database (Optional)

**Purpose**: Top-level certification or curriculum organization

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `Name` | Title | Yes | Program name (e.g., "CCNA") |
| `Description` | Text | No | Program overview |

---

## Notion API Setup

### 1. Create Integration

1. Go to [Notion Developers](https://developers.notion.com/)
2. Click "New integration"
3. Name: `notion-learning-sync`
4. Select your workspace
5. Capabilities: Read content, Read user info
6. Copy the **Internal Integration Token**

### 2. Share Databases

For each database you want to sync:

1. Open the database in Notion
2. Click "Share" in the top right
3. Click "Invite"
4. Search for your integration name
5. Select it and click "Invite"

### 3. Get Database IDs

For each database:

1. Open the database in Notion
2. Copy the URL
3. Extract the ID from the URL:
   ```
   https://notion.so/workspace/DATABASE_ID?v=VIEW_ID
                          ^^^^^^^^^^^
   ```

---

## Environment Configuration

Add to your `.env` file:

```bash
# Notion API Configuration
NOTION_API_KEY=secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Database IDs
NOTION_FLASHCARDS_DB=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
NOTION_CONCEPTS_DB=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
NOTION_MODULES_DB=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
NOTION_TRACKS_DB=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
NOTION_PROGRAMS_DB=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

---

## Sync Workflow

### Initial Sync

```bash
# Sync all databases from Notion
python -m src.cli.main sync --all

# Or sync specific databases
python -m src.cli.main sync --flashcards
python -m src.cli.main sync --concepts
python -m src.cli.main sync --modules
```

### Incremental Sync

The sync engine tracks the last sync timestamp and only fetches updated pages:

```bash
# Sync changes since last sync
python -m src.cli.main sync --incremental
```

### Full Rebuild

To completely rebuild from Notion (discards local changes):

```bash
# Warning: This deletes all staging data
python -m src.cli.main sync --full-rebuild
```

---

## Data Flow

### 1. Staging Tables

Raw Notion data lands in staging tables with JSONB properties:

```sql
SELECT
    notion_id,
    properties->>'Front' as front,
    properties->>'Back' as back,
    properties->>'Type' as atom_type
FROM stg_flashcards
LIMIT 5;
```

### 2. Cleaning Pipeline

The cleaning pipeline transforms staging data:

- **Atomicity check**: Ensures single concept per atom
- **Duplicate detection**: Prevents duplicate content
- **Prefix normalization**: Standardizes formatting
- **Quality scoring**: Applies 11-point rubric

### 3. Canonical Tables

Clean, validated data in `learning_atoms`, `concepts`, `learning_modules`:

```sql
SELECT
    card_id,
    front,
    back,
    atom_type,
    quality_score
FROM learning_atoms
WHERE quality_score >= 0.75
ORDER BY created_at DESC
LIMIT 10;
```

---

## Best Practices

### Content Organization

1. **One concept per card**: Keep atoms atomic
2. **Use relations**: Link cards to concepts and modules
3. **Tag consistently**: Use standard tags across content
4. **Review workflow**: Use Status property for approval flow

### Sync Strategy

1. **Notion is source of truth**: Make edits in Notion, not DB
2. **Regular syncs**: Set up scheduled sync (daily recommended)
3. **Monitor staging**: Check `stg_*` tables for sync issues
4. **Validate cleaning**: Review quality scores after sync

### Avoiding Issues

| Issue | Prevention |
|-------|------------|
| Missing content | Ensure all required properties are filled |
| Broken relations | Verify related pages exist before linking |
| Duplicate cards | Use unique identifiers in card names |
| Sync failures | Check API rate limits, retry with backoff |

---

## Troubleshooting

### "Page not found" Errors

- Ensure database is shared with the integration
- Verify the database ID is correct
- Check if the page was deleted or moved

### Missing Properties

- Some properties may return `None` if empty
- Use default values in cleaning pipeline
- Check Notion property types match expected types

### Rate Limiting

Notion API has rate limits:
- 3 requests per second (average)
- Implement exponential backoff
- Use batch operations where possible

---

## Related Documentation

- [Quickstart Guide](quickstart.md) - Get started quickly
- [Configuration Guide](configuration.md) - All settings
- [Database Schema](../architecture/database-schema.md) - Table structures
- [Cleaning Pipeline](../architecture/cleaning-pipeline.md) - Data transformation
