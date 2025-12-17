# How To: Configure Anki Sync

Set up bidirectional synchronization between Cortex and Anki.

---

## Prerequisites

- Cortex installed and configured
- Anki Desktop 2.1.54+
- Learning atoms in PostgreSQL

---

## Install AnkiConnect

1. Open Anki
2. Go to **Tools > Add-ons**
3. Click **Get Add-ons...**
4. Enter code: `2055492159`
5. Click **OK** and restart Anki

Verify:
```bash
curl http://127.0.0.1:8765 -X POST -d '{"action":"version","version":6}'
```

Expected: `{"result": 6, "error": null}`

---

## Configure Cortex

Add to `.env`:

```bash
# AnkiConnect URL
ANKI_CONNECT_URL=http://127.0.0.1:8765

# Target deck
ANKI_DECK_NAME=CCNA::ITN

# Note type
ANKI_NOTE_TYPE=Basic
```

Use `::` for nested decks: `CCNA::ITN::Synced`

---

## Push Cards to Anki

```bash
# Preview
nls sync anki-push --dry-run

# Push all eligible cards
nls sync anki-push

# Push only Grade A/B cards
nls sync anki-push --min-quality B
```

### Push Criteria

| Criterion | Requirement |
|-----------|-------------|
| Atom type | `flashcard` or `cloze` |
| Quality score | >= 0.75 (Grade B) |
| Front length | >= 10 characters |
| Back length | >= 3 characters |
| Review status | `needs_review = false` |

MCQ, true/false, and Parsons problems remain in Cortex CLI.

---

## Pull Review Stats from Anki

After studying in Anki:

```bash
nls sync anki-pull
```

### Automatic Session Sync

Cortex automatically syncs with Anki at session start:

1. When you run `nls cortex start`, Cortex pulls latest FSRS stats from Anki
2. This ensures scheduling decisions reflect reviews performed in Anki
3. If Anki is unavailable, the session continues without blocking

```
$ nls cortex start
Syncing with Anki...
Synced 42 atoms from Anki (156 cards found)
```

**Note**: Automatic sync is skipped when resuming a session (`nls cortex resume`) to preserve session state.

### Stats Retrieved

| Anki Field | Database Column | Description |
|------------|-----------------|-------------|
| `factor` | `anki_ease_factor` | Ease factor (2.5 = 250%) |
| `interval` | `anki_interval_days` | Days until next review |
| `reps` | `anki_review_count` | Total reviews |
| `lapses` | `anki_lapses` | Times forgotten |
| `due` | `anki_due_date` | Next review date |

**Note**: The columns are `anki_stability` and `anki_synced_at` for FSRS stability tracking.

---

## Full Sync Pipeline

```bash
nls sync all
```

Executes:
1. Notion > PostgreSQL sync
2. Cleaning pipeline
3. Push to Anki
4. Pull stats from Anki

---

## In-Session Sync

At session end, the remediation menu offers full bidirectional sync:

```
REMEDIATION OPTIONS

  [1] Generate study notes for struggled topics
  [2] Generate additional practice questions
  [3] Full Anki sync (push atoms + pull stats)
  [s] Skip remediation
```

Selecting option **3** performs:
1. **Push**: Sends new/updated atoms to Anki
2. **Pull**: Retrieves latest FSRS stats from Anki

This is useful for syncing progress to mobile before leaving your desk.

---

## Scheduled Sync

### Linux/macOS (crontab -e)

```bash
0 2 * * * cd /path/to/notion-learning-sync && ./venv/bin/nls sync all >> /var/log/cortex-sync.log 2>&1
```

### Windows (Task Scheduler)

```powershell
$action = New-ScheduledTaskAction -Execute "python" -Argument "-m src.cli.main sync all" -WorkingDirectory "C:\path\to\notion-learning-sync"
$trigger = New-ScheduledTaskTrigger -Daily -At "2:00AM"
Register-ScheduledTask -TaskName "CortexSync" -Action $action -Trigger $trigger
```

---

## Troubleshooting

### AnkiConnect Not Responding

**Error**: `ConnectionError: Failed to connect to Anki`

**Solutions**:
1. Ensure Anki is running
2. Verify AnkiConnect is installed: **Tools > Add-ons**
3. Check port: `curl http://127.0.0.1:8765`
4. Check firewall settings

### Duplicate Cards

**Solutions**:
1. Verify `anki_note_id` is populated in database
2. Use `--dry-run` first
3. In Anki: **Browse > Sort by Front > Delete duplicates**

### Stats Not Updating

**Checks**:
1. Have you reviewed cards in Anki?
2. Is `anki_card_id` populated in the database?
3. Verify card exists with AnkiConnect `cardsInfo` action

---

## See Also

- [Session Remediation](../explanation/session-remediation.md) - Bidirectional sync details
- [FSRS Algorithm](../explanation/fsrs-algorithm.md) - Spaced repetition scheduling
- [CLI Reference](../reference/cli-commands.md) - Command reference
- [Database Schema](../reference/database-schema.md) - Anki-related columns
