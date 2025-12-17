# CLI Command Reference

Complete command reference for the Cortex CLI.

---

## Command Structure

```
nls [COMMAND] [SUBCOMMAND] [OPTIONS]
```

Get help:
```bash
nls --help
nls sync --help
```

---

## Study Commands

### Core Study

| Command | Description |
|---------|-------------|
| `nls cortex start` | Start adaptive study session |
| `nls cortex start --mode war` | War/cram mode |
| `nls cortex start -i` | Interactive mode |
| `nls cortex start --modules 1-5,10-12` | Specify modules |
| `nls cortex start --limit 30` | Set session length |
| `nls cortex optimize` | Retention-optimized session (FSRS-4) |
| `nls cortex war` | Alias for war mode |
| `nls cortex resume` | Resume saved session |
| `nls cortex suggest` | Get study suggestions |

### Study Modes

- **Adaptive** (default): FSRS scheduling + interleaving
- **Optimize**: Full FSRS-4 + difficulty calibration
- **War**: Aggressive cram mode, ignores due dates

### Session Persistence

- Auto-saves every 5 questions
- **Ctrl+C** saves and quits
- Resume with `nls cortex resume`
- Sessions expire after 24 hours

### Session Lifecycle

| Phase | Behavior |
|-------|----------|
| **Start** | Auto-sync with Anki; check for unread notes related to queued atoms |
| **Study** | Fatigue detection; micro-notes on consecutive errors |
| **End** | Remediation menu if struggles detected |

### "I Don't Know" Option

During any question, type one of these inputs to indicate unfamiliarity:

| Input | Effect |
|-------|--------|
| `?` | Triggers "I don't know" response |
| `l` | Triggers "I don't know" response |
| `learn` | Triggers "I don't know" response |
| `idk` | Triggers "I don't know" response |
| `dk` | Triggers "I don't know" response |

**Behavior**:
- Correct answer is revealed immediately with explanation
- `dont_know_count` is incremented in database
- Section flagged for potential note generation
- No FSRS penalty (not counted as "incorrect")

### Post-Session Remediation Menu

At session end, if errors occurred, an interactive menu appears:

```
REMEDIATION OPTIONS

  [1] Generate study notes for struggled topics
  [2] Generate additional practice questions
  [3] Full Anki sync (push atoms + pull stats)
  [s] Skip remediation
```

| Option | Action |
|--------|--------|
| **1** | Generate adaptive study notes (depth based on error rate) |
| **2** | Generate LLM practice questions for weak sections |
| **3** | Full bidirectional Anki sync |
| **s** | Skip and exit |

Study notes are displayed in terminal and saved to `outputs/notes/`.

---

## Progress & Analysis

| Command | Description |
|---------|-------------|
| `nls cortex stats` | Comprehensive statistics |
| `nls cortex today` | Today's summary |
| `nls cortex path` | Learning path with progress |
| `nls cortex module <N>` | Module N details |
| `nls cortex persona` | Learner persona profile |
| `nls cortex diagnose` | Cognitive diagnosis |
| `nls cortex check` | Preflight system check |

---

## Struggle & Remediation

| Command | Description |
|---------|-------------|
| `nls cortex struggle --show` | View struggle map |
| `nls cortex struggle --interactive` | Set struggles interactively |
| `nls cortex struggle --modules 11,12,14` | Set specific modules |
| `nls cortex struggle --intensity high` | Set intensity |
| `nls cortex remediation` | Show remediation sections |
| `nls cortex force-z` | Prerequisite gap analysis |

### Study Notes (Hub Menu Option 7)

Access study notes through the Cortex hub:

```bash
nls cortex start  # Select option 7 from hub menu
```

| Sub-Option | Description |
|------------|-------------|
| **1** | View all study notes |
| **2** | View unread notes only |
| **3** | Generate notes for weak sections |
| **b** | Return to hub |

See [Use Study Notes](../how-to/use-study-notes.md) for detailed instructions.

---

## Reading Commands

| Command | Description |
|---------|-------------|
| `nls cortex read <module>` | Read module interactively |
| `nls cortex read <module> --toc` | Show table of contents |
| `nls cortex read <module> --section <id>` | Read specific section |
| `nls cortex read <module> --search <query>` | Search within module |

### Navigation

- **n** or **Enter**: Next section
- **p**: Previous section
- **t**: Table of contents
- **q**: Quit

---

## Sync Commands

| Command | Description |
|---------|-------------|
| `nls sync all` | Full pipeline: Notion > PostgreSQL > Anki |
| `nls sync notion` | Sync from Notion |
| `nls sync notion --full` | Full sync (all pages) |
| `nls sync notion --dry-run` | Preview without changes |
| `nls sync notion --parallel` | Parallel fetching |
| `nls sync anki-push` | Push atoms to Anki |
| `nls sync anki-push --min-quality B` | Push Grade A/B only |
| `nls sync anki-pull` | Pull stats from Anki |
| `nls sync anki-pull --deck "CCNA::ITN"` | Pull from specific deck |

---

## Anki Commands

| Command | Description |
|---------|-------------|
| `nls anki import` | Import from configured deck |
| `nls anki import --deck "My Cards"` | Import specific deck |
| `nls anki import --dry-run` | Preview import |
| `nls anki import --quality` | Import with quality analysis |

---

## Database Commands

| Command | Description |
|---------|-------------|
| `nls db init` | Initialize tables |
| `nls db migrate --migration 001` | Run specific migration |
| `nls db migrate --migration 001 --force` | Force re-run |

### Available Migrations

| Number | Description |
|--------|-------------|
| 001 | Initial schema |
| 002 | Anki import tables |
| 003 | Sync audit logging |
| 004 | Semantic embeddings |
| 005 | Prerequisites and quiz |
| 006 | CCNA generation |
| 007 | Adaptive learning |
| 008 | CCNA study path |
| 009 | Quiz responses |
| 010 | Enhanced tracking |
| 011 | CLT schema alignment |
| 012 | War mode schema |
| 013 | Rename tables to canonical |
| 014 | Neuromorphic cortex |
| 015 | Struggle weights table |
| 016 | Quarantine table |
| 017 | Fix FK constraints and views |
| 018 | Dynamic struggle weights / Remediation notes |
| 019 | Transfer testing |
| 020 | Struggle weight history |
| 021 | Socratic dialogue tables |

---

## Cleaning Commands

| Command | Description |
|---------|-------------|
| `nls clean check` | Check first 100 atoms |
| `nls clean check --limit 500` | Check more atoms |
| `nls clean run --dry-run` | Preview changes |
| `nls clean run` | Apply cleaning |
| `nls clean run --rewrite` | Enable AI rewriting |

---

## Content Commands

| Command | Description |
|---------|-------------|
| `nls content import <path>` | Import from local files |
| `nls content import <path> --dry-run` | Preview import |
| `nls content import <dir> --pattern "*.md"` | Import from directory |
| `nls content stats` | Local content statistics |

---

## JIT Generation Commands

Just-in-time content generation for filling knowledge gaps. See [JIT Generation Reference](./jit-generation.md) for detailed documentation.

| Command | Description |
|---------|-------------|
| `nls generate concept <uuid>` | Generate atoms for a concept |
| `nls generate concept <uuid> --count 5` | Generate 5 atoms |
| `nls generate concept <uuid> --type explanation` | Generate explanations |
| `nls generate concept <uuid> --dry-run` | Preview without saving |
| `nls generate gaps` | Find and fill content gaps |
| `nls generate gaps --min-atoms 5` | Set minimum threshold |
| `nls generate gaps --cluster <uuid>` | Limit to cluster |
| `nls generate stats` | Show JIT generation statistics |

### Content Types

| Type | Description |
|------|-------------|
| `practice` | Flashcards, MCQ, cloze (default) |
| `explanation` | Elaborative content for encoding errors |
| `worked_example` | Step-by-step for integration errors |

### Supported Import Formats

- **Q/A pairs**: `Q: question A: answer`
- **Markdown headers**: `## Question\nAnswer text`
- **Cloze deletions**: `The {{c1::answer}} is here`
- **MCQ**: `A) B) C) D)` with `*` marking correct

---

## Export Commands

| Command | Description |
|---------|-------------|
| `nls export cards --output cards.csv` | Export cards |
| `nls export stats --output stats.csv` | Export statistics |
| `nls export stats --deck "CCNA::ITN"` | Export specific deck |

---

## Graph Commands (Cortex 2.0)

| Command | Description |
|---------|-------------|
| `nls cortex sync2 pull` | Pull from Neo4j graph |
| `nls cortex sync2 push` | Push to Neo4j graph |
| `nls cortex sync2 status` | Graph sync status |
| `nls cortex graph stats` | Shadow Graph statistics |
| `nls cortex zscore compute` | Compute Z-scores |
| `nls cortex forcez analyze` | Force Z gap analysis |

---

## Utility Commands

| Command | Description |
|---------|-------------|
| `nls info` | Show configuration |
| `nls version` | Show version |

---

## Common Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview without changes |
| `--help` | Show command help |
| `--verbose` | Enable debug output |

---

## Environment Variables

| Variable | Effect |
|----------|--------|
| `DRY_RUN=true` | All commands preview only |
| `LOG_LEVEL=DEBUG` | Verbose logging |
| `PROTECT_NOTION=true` | Prevent writes to Notion |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error |
| 2 | Invalid arguments |

---

## Workflow Example

```bash
# 1. Check system
nls cortex check

# 2. Read material
nls cortex read 11 --toc
nls cortex read 11 --section 11.2

# 3. Study
nls cortex start

# 4. Interrupt (Ctrl+C saves)

# 5. Resume
nls cortex resume

# 6. Review progress
nls cortex stats

# 7. Sync to Anki
nls sync anki-push
```

---

## Troubleshooting

### Command Not Found

```
nls: command not found
```

**Solutions**:
1. Activate venv: `source venv/bin/activate`
2. Install: `pip install -e .`
3. Use module: `python -m src.cli.main`

### Database Error

**Solutions**:
1. Check PostgreSQL is running
2. Verify DATABASE_URL in `.env`
3. Create database: `createdb notion_learning_sync`

---

## See Also

- [JIT Generation](./jit-generation.md) - On-demand content generation system
- [Session Remediation](../explanation/session-remediation.md) - Detailed remediation system documentation
- [Configure Anki Sync](../how-to/configure-anki-sync.md) - Anki integration setup
- [First Study Session](../tutorials/first-study-session.md) - Tutorial for new users
