# Anki Sync Reference

Complete reference for bidirectional Anki synchronization in Cortex.

---

## Overview

Cortex synchronizes with Anki via [AnkiConnect](https://foosoft.net/projects/anki-connect/) for spaced repetition. The sync is bidirectional:

- **Push**: Learning atoms from PostgreSQL to Anki
- **Pull**: FSRS scheduling stats from Anki to PostgreSQL

**Location**: `src/anki/`

---

## Architecture

```
PostgreSQL                         Anki
+------------------+              +------------------+
| learning_atoms   | -- push -->  | CCNA::ITN decks  |
| (front, back,    |              | (cards with      |
|  quality_score)  |              |  tags, fields)   |
+------------------+              +------------------+
         ^                                 |
         |                                 |
         +-------- pull (FSRS stats) ------+
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANKI_CONNECT_URL` | `http://127.0.0.1:8765` | AnkiConnect endpoint |
| `ANKI_DECK_NAME` | `CCNA::ITN` | Base deck name |
| `ANKI_NOTE_TYPE` | `Basic` | Default note type |

### Constants (src/anki/config.py)

| Constant | Value | Description |
|----------|-------|-------------|
| `FLASHCARD_NOTE_TYPE` | `LearningOS-v2` | Standard flashcard note type |
| `CLOZE_NOTE_TYPE` | `LearningOS-v2 Cloze-NEW` | Cloze deletion note type |
| `BASE_DECK` | `CCNA::ITN` | Parent deck |
| `CURRICULUM_ID` | `ccna-itn` | Tag prefix for curriculum |
| `SOURCE_TAG` | `cortex` | System identifier tag |
| `ANKI_ATOM_TYPES` | `("flashcard", "cloze")` | Types that sync to Anki |

---

## Push Service

**File**: `src/anki/push_service.py`

Pushes clean atoms from PostgreSQL to Anki with batched operations (~50x faster than sequential).

### Function: push_clean_atoms()

```python
def push_clean_atoms(
    anki_client: AnkiClient | None = None,
    db_session: Session | None = None,
    min_quality: str = "B",
    dry_run: bool = False,
    incremental: bool = True,
) -> dict[str, Any]:
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `anki_client` | `AnkiClient` | None | AnkiConnect client |
| `db_session` | `Session` | None | Database session |
| `min_quality` | `str` | `"B"` | Minimum quality grade |
| `dry_run` | `bool` | `False` | Preview without changes |
| `incremental` | `bool` | `True` | Only sync new/changed |

### Quality Thresholds

| Grade | Score |
|-------|-------|
| A | >= 0.9 |
| B | >= 0.7 |
| C | >= 0.5 |
| D | >= 0.3 |
| F | >= 0.0 |

### Incremental vs Full Sync

**Incremental** (default): Only atoms where:
- `anki_note_id IS NULL` (new)
- `anki_synced_at IS NULL` (never synced)
- `updated_at > anki_synced_at` (modified)

**Full**: All atoms matching quality filter

### Return Value

```python
{
    "created": int,      # New notes created in Anki
    "updated": int,      # Existing notes updated
    "skipped": int,      # Atoms not synced
    "errors": list[str]  # Error messages
}
```

---

## Pull Service

**File**: `src/anki/pull_service.py`

Pulls FSRS scheduling stats from Anki back to PostgreSQL.

### Function: pull_review_stats()

```python
def pull_review_stats(
    anki_client: AnkiClient | None = None,
    db_session: Session | None = None,
    dry_run: bool = False,
    query: str | None = None,
    sections: list[str] | None = None,
) -> dict[str, Any]:
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | None | Custom Anki search query |
| `sections` | `list[str]` | None | Section IDs to filter |

### Query Building

Priority:
1. Custom `query` parameter
2. `sections` list converted to tag query
3. Default: All notes in deck

Example section query:
```
deck:CCNA::ITN* (tag:section:2.1 OR tag:section:2.2)
```

### FSRS Stats Updated

| Field | Description |
|-------|-------------|
| `anki_note_id` | Note ID in Anki |
| `anki_interval` | Days until next review |
| `anki_ease_factor` | Ease multiplier (stored / 1000) |
| `anki_review_count` | Total reviews |
| `anki_lapses` | Times forgotten |
| `anki_stability` | FSRS stability (approx. interval) |
| `anki_difficulty` | FSRS difficulty (0-1, inverted from ease) |
| `anki_queue` | Card queue state |
| `anki_synced_at` | Last sync timestamp |

### Difficulty Calculation

```python
# Ease 2.5 = difficulty 0.5
# Ease 1.3 = difficulty ~0.9
difficulty = max(0.0, min(1.0, (3.0 - ease_factor) / 2.0))
```

---

## Bidirectional Sync

### Function: sync_bidirectional()

```python
def sync_bidirectional(
    anki_client: AnkiClient | None = None,
    db_session: Session | None = None,
    min_quality: str = "B",
    dry_run: bool = False,
) -> dict[str, Any]:
```

Performs push then pull in sequence.

### Return Value

```python
{
    "push": { ... },  # Push stats
    "pull": { ... }   # Pull stats
}
```

---

## Deck Structure

Cards are organized into module subdecks:

```
CCNA::ITN
  CCNA::ITN::M01 Networking Today
  CCNA::ITN::M02 Basic Switch and End Device Configuration
  CCNA::ITN::M03 Protocols and Models
  ...
  CCNA::ITN::M17 Build a Small Network
```

### Module Names

| Module | Name |
|--------|------|
| 1 | Networking Today |
| 2 | Basic Switch and End Device Configuration |
| 3 | Protocols and Models |
| 4 | Physical Layer |
| 5 | Number Systems |
| 6 | Data Link Layer |
| 7 | Ethernet Switching |
| 8 | Network Layer |
| 9 | Address Resolution |
| 10 | Basic Router Configuration |
| 11 | IPv4 Addressing |
| 12 | IPv6 Addressing |
| 13 | ICMP |
| 14 | Transport Layer |
| 15 | Application Layer |
| 16 | Network Security Fundamentals |
| 17 | Build a Small Network |

---

## Note Fields

Cards use 6-field `LearningOS-v2` note type:

| Field | Content |
|-------|---------|
| `front` | Question text |
| `back` | Answer text |
| `concept_id` | Unique card ID (e.g., `NET-M11-S2.3-FC001`) |
| `tags` | Space-separated tag string |
| `source` | `cortex` |
| `metadata_json` | JSON with curriculum_id, module, section, atom_type |

### Example metadata_json

```json
{
  "curriculum_id": "ccna-itn",
  "module_number": 11,
  "section_id": "11.2.3",
  "atom_type": "flashcard"
}
```

---

## Tag Structure

Each card gets these tags:

| Tag | Example | Description |
|-----|---------|-------------|
| Source | `cortex` | System identifier |
| Curriculum | `ccna-itn` | Course identifier |
| Module | `ccna-itn:m11` | Module number |
| Type | `type:flashcard` | Atom type |
| Section | `section:11.2.3` | Section ID |

---

## CLI Commands

### Push to Anki

```bash
# Default (B+ quality, incremental)
nls sync anki-push

# A quality only
nls sync anki-push --min-quality A

# Full sync (not incremental)
nls sync anki-push --full

# Preview
nls sync anki-push --dry-run
```

### Pull from Anki

```bash
# All decks
nls sync anki-pull

# Specific sections
nls sync anki-pull --sections 11.2,11.3

# Custom query
nls sync anki-pull --query "deck:CCNA::ITN::M11* tag:type:flashcard"
```

### Bidirectional

```bash
nls sync all
```

---

## AnkiClient

**File**: `src/anki/anki_client.py`

Low-level AnkiConnect HTTP wrapper.

### Key Methods

| Method | Description |
|--------|-------------|
| `check_connection()` | Verify AnkiConnect is running |
| `batch_find_notes(queries)` | Find notes by concept_id |
| `batch_add_notes(payloads)` | Create multiple notes |
| `batch_update_notes(payloads)` | Update multiple notes |
| `_invoke(action, params)` | Raw AnkiConnect call |
| `_invoke_multi(actions)` | Batched multi action |

### Batching

Push service uses `BATCH_SIZE = 100` atoms per API call for ~50x speedup.

---

## Error Handling

### Connection Errors

```python
if not client.check_connection():
    raise RuntimeError(
        "Cannot connect to Anki. Ensure Anki is running with AnkiConnect addon."
    )
```

### Duplicate Handling

Push service uses:
```python
"options": {"allowDuplicate": False, "duplicateScope": "deck"}
```

### Offline Mode

CortexSession falls back to offline mode when Anki unreachable:
- Buffers pending sync to `outputs/cache/pending_sync.json`
- Flushes on next successful connection

---

## Troubleshooting

### Anki Not Connected

1. Verify Anki is running
2. Check AnkiConnect addon is installed
3. Verify port 8765 is not blocked
4. Test: `curl http://127.0.0.1:8765`

### Note Type Mismatch

Ensure note types exist in Anki:
- `LearningOS-v2` with fields: front, back, concept_id, tags, source, metadata_json
- `LearningOS-v2 Cloze-NEW` for cloze deletions

### Sync Conflicts

When `updated_at > anki_synced_at`:
- Push updates Anki note
- Pull overwrites local FSRS stats

---

## See Also

- [Configuration Reference](configuration.md)
- [Architecture Overview](../explanation/architecture.md)
- [FSRS Algorithm](../explanation/fsrs-algorithm.md)
