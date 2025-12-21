# Vision: Cortex-CLI as DARPA Digital Tutor Rival

## Executive Summary

**Cortex-CLI** is positioned to become the terminal-based equivalent of DARPA's Digital Tutor and Knewton's adaptive engine—a **personalized learning companion optimized for developers and technical learners** who live in the command line.

This document defines the unique positioning of Cortex-CLI within the broader Right-Learning ecosystem and establishes its technical vision as a cognition-aware, adaptive learning system.

---

## The Right-Learning Ecosystem: Three Unique Products

### **Greenlight: The Performance Coach**
**Unique Domain:** Real-time developer skill acceleration through TDD/BDD feedback loops

**Core Philosophy:** "Make you faster at fixing what's broken"

- **Measures:** Time-to-green, error pattern recognition, test coverage velocity
- **Learning Method:** Deliberate practice through failure analysis
- **Integration:** IDE plugins (real-time), CI/CD hooks (post-commit analysis)
- **Target User:** Professional developers improving their debugging/testing workflow
- **Key Differentiator:** Context-aware, real-time feedback during active development

**Greenlight owns:** The "in-flow" learning moment when you're actively coding and getting immediate feedback on how to improve your red→green process.

---

### **Cortex-CLI: The Knowledge Architect**
**Unique Domain:** Long-term retention & personal knowledge graph management

**Core Philosophy:** "Build deep, durable knowledge that compounds"

- **Measures:** FSRS mastery, prerequisite graph depth, knowledge retention curves
- **Learning Method:** Spaced repetition, atomic knowledge units, semantic relationships
- **Integration:** Notion (authoring), Anki (review), Neo4j (graph algorithms), CLI (automation)
- **Target User:** Self-directed learners building personal knowledge bases
- **Key Differentiator:** Offline-first, scriptable, optimized for long-term retention and knowledge graph traversal

**Cortex-CLI owns:** The "knowledge consolidation" space—taking raw notes/content and transforming them into a structured, reviewable, mastery-tracked knowledge base.

---

### **Right-Learning: The Learning Platform**
**Unique Domain:** Structured curriculum delivery with interactive, collaborative environments

**Core Philosophy:** "Learn by doing, together"

- **Measures:** Course completion, collaborative coding metrics, peer feedback
- **Learning Method:** Guided exercises, sandboxed coding challenges, instructor-led courses
- **Integration:** Web platform, multi-user sandboxes, LMS features
- **Target User:** Students, bootcamp participants, teams learning together
- **Key Differentiator:** Social, structured, web-based with live coding environments

**Right-Learning owns:** The "formal learning" experience—courses, cohorts, structured paths with rich interactive environments.

---

## Cortex-CLI Integration Partners

While Cortex-CLI is a standalone terminal-based learning tool, it integrates with two complementary systems to extend its capabilities:

### 1. Right-Learning Platform (Cloud Integration)
**Role:** Cloud-based adaptive learning platform
**Integration Type:** Mastery sync, curriculum mapping, Z-Score signals

**How It Works:**
- **Data Flow:** Bidirectional sync of learning progress and mastery scores
- **Use Case:** Study offline with cortex-cli, sync progress to Right-Learning for multi-device access
- **Content Pipeline:** Cortex-CLI validates and prepares atoms; Right-Learning serves them in web courses
- **Status:** Active integration (see [`adaptive-learning.md`](./adaptive-learning.md))

**Example Workflow:**
1. Complete a course module in Right-Learning (web platform)
2. Export progress → cortex-cli for offline study (airplane, secure network)
3. Study with FSRS-optimized spaced repetition in terminal
4. Re-sync mastery updates → Right-Learning when back online
5. Continue course with updated knowledge state

### 2. Greenlight IDE (Runtime Integration)
**Role:** IDE-based coding lab for runtime-dependent atoms
**Integration Type:** Atom handoff via REST API, shared telemetry

**How It Works:**
- **Data Flow:** Cortex-CLI → Greenlight (atom execution request), Greenlight → Cortex-CLI (test results, feedback)
- **Use Case:** When a learning atom requires code execution, debugging, or IDE tools
- **Handoff Protocol:** Terminal displays "Opening in Greenlight..." → IDE opens → learner codes/debugs → results sync back
- **Status:** Planned integration (see [`greenlight-integration.md`](./greenlight-integration.md))

**Example Workflow:**
1. Studying CCNA subnetting in cortex-cli (terminal drills)
2. Encounter atom: "Write Python function to calculate network address"
3. Cortex-CLI hands off to Greenlight IDE (requires code execution)
4. Write code in IDE, run tests, get feedback
5. Results (3/5 tests passed, partial credit) sync back to cortex-cli
6. Continue terminal session with next atom

### Integration Summary

| Aspect | Right-Learning | Greenlight |
|--------|----------------|------------|
| **Purpose** | Cloud sync for multi-device learning | Runtime execution for code atoms |
| **Direction** | Bidirectional (sync) | Request-Response (handoff) |
| **Atoms Handled** | All atom types (mirrors cortex-cli) | Code, debugging, CLI, projects |
| **When Used** | Multi-device access, team learning | Code execution, visual debugging |
| **Required?** | No (cortex-cli works standalone) | No (cortex-cli works without Greenlight) |

**Key Principle:** Cortex-CLI is the primary orchestrator. Both integrations are optional and extend functionality without breaking the standalone terminal experience.

---

## What a CLI Can Do That a Website Cannot

Cortex-CLI's power comes from capabilities that are impossible or impractical in a web browser:

### 1. **True Offline-First**
- No network dependency, works on planes, remote locations, air-gapped environments
- Zero data egress for privacy-conscious users or secure environments
- Full functionality without authentication or API calls

### 2. **OS-Level Integration**
- File system access for ETL pipelines (Notion → SQLite → Anki)
- Process spawning for sandboxed code execution
- Shell integration (aliases, completions, scripts)
- System-wide hotkeys and background services

### 3. **Zero Latency**
- Local computation, instant feedback, no HTTP round-trips
- Real-time FSRS calculations and adaptive scheduling
- Immediate mastery updates and Z-Score recalculations

### 4. **Privacy & Local-First**
- Your learning data never leaves your machine unless you explicitly sync
- No tracking, no analytics, no third-party scripts
- Full control over data storage and backups

### 5. **Scriptable & Automatable**
- Cron jobs for scheduled study sessions
- CI/CD integration for content validation pipelines
- Git hooks for automatic knowledge capture
- Shell aliases for muscle-memory workflows

### 6. **Resource Efficient**
- Runs in the background with minimal memory footprint
- Terminal multiplexer integration (tmux/screen)
- No browser overhead, no JavaScript bloat

### 7. **Deep IDE Integration** (via Greenlight)
- Hook into editor events, LSP servers, debuggers
- Capture compile errors and failed tests automatically
- Generate learning atoms from actual coding mistakes

### 8. **Terminal as a Learning Environment**
- Developers LIVE in the terminal; meet them where they are
- No context switching between browser and code
- Natural fit for CLI-heavy subjects (networking, DevOps, systems programming)

---

## Cortex-CLI Vision: The DARPA Digital Tutor for Developers

### Core Design Principles

1. **Adaptive, Not Algorithmic**
   - Content selection driven by cognitive models (FSRS, Z-Score, prerequisite graphs)
   - Not "next lesson" but "what maximizes learning right now"

2. **Mastery-Based, Not Time-Based**
   - Progress measured by retrievability and transfer capability
   - Not "completed 80% of course" but "mastered 80% of atoms"

3. **Cognition-Aware, Not Quiz-Aware**
   - Tracks cognitive load, error patterns, confidence calibration
   - Not "got 7/10 correct" but "struggling with subnet math, confident on OSI layers"

4. **Diagnostic, Not Evaluative**
   - Feedback identifies error class (misconception, slip, missing prerequisite)
   - Not "wrong" but "you're confusing correlation with causation"

5. **Transfer-Oriented, Not Recall-Oriented**
   - Prioritizes application atoms (debugging, design) over recognition atoms (MCQ)
   - Not "can you recognize OSPF?" but "can you troubleshoot OSPF neighbor issues?"

---

## Integration Architecture

### Greenlight → Cortex-CLI
**Automatic Remediation Pipeline**

When Greenlight detects a struggle pattern:
1. Greenlight identifies error class (e.g., "async/await timing confusion")
2. Generates a learning atom with diagnostic tagging
3. Pushes to Cortex-CLI via local API or file
4. Cortex-CLI schedules it in the review queue with boosted Z-Score
5. User gets targeted remediation in next study session

**Example:**
```
[Greenlight IDE Plugin]
  ↓ (detects 3 failed test runs with same error)
  ↓ generates atom: "Predict output of async function chain"
  ↓ tags: error_class=async_timing, confidence=low
  ↓
[Cortex-CLI]
  ↓ receives atom, computes Z-Score=0.92 (high priority)
  ↓ schedules in next session
  ↓ presents with scaffolded explanation
  ↓ tracks mastery until retrievability > 0.90
```

### Cortex-CLI → Right-Learning
**Content Validation & ETL Pipeline**

- Cortex-CLI acts as the **ETL engine** and **content validator**
- Right-Learning pulls clean, validated atoms via API
- Users can "export" their progress from Right-Learning, study offline with Cortex-CLI, then re-sync

**Data Flow:**
```
Notion (Source of Truth)
  ↓ sync
Cortex-CLI Staging (validation, deduplication)
  ↓ cleaning pipeline
Cortex-CLI Canonical DB (FSRS-tracked atoms)
  ↓ API
Right-Learning Platform (multi-user courses)
  ↓ export
Cortex-CLI Offline Study (air-gapped)
  ↓ import
Right-Learning Platform (progress sync)
```

### Cortex-CLI Standalone Value

Even without Greenlight or Right-Learning, Cortex-CLI is valuable for:

1. **Privacy-Conscious Users** - Local-only mode, no data egress
2. **Offline Environments** - Airplanes, secure networks, remote locations
3. **Power Users** - Scriptability, automation, git integration
4. **Notion Users** - ETL pipeline for personal knowledge bases
5. **Anki Users** - Bidirectional sync with enhanced mastery tracking
6. **Researchers** - Export learning graphs for analysis

---

## Key Features to Rival DARPA Digital Tutor

1. **Adaptive Content Delivery**
   - Today: Z-Score prioritization (decay, centrality, project, novelty).
   - Next: Cognitive load monitoring, error-pattern detection, time-on-task; CLI-only signals (shell history, git commits, IDE events via Greenlight).

2. **Interactive Problem-Solving**
   - Parsons/ordering; live code execution (Python/bash/SQL) in the practice pane.
   - Progressive hints; immediate feedback; guided CLI labs for networking/devops/sysadmin.

3. **Multi-Modal Learning**
   - Guided labs, debugging challenges (time-to-fix), refactoring exercises, command recall/fluency drills.

4. **Cognitive Model Tracking**
   - FSRS, prerequisite backtracking, PLM sidecar.
   - Add cognitive load index to adapt difficulty based on struggle vs flow.

5. **Split-Pane Modes (TUI)**
   - Horizontal: theory over practice.
   - Vertical: instruction vs workspace.
   - 3-pane: reference | workspace | feedback/mastery tracker.
   - Top bar: app/version/module/mastery/hotkeys; bottom strip: queue/latency/attempts/confidence prompt.

## Implementation Phases (Cortex-CLI)

- **Phase 1: TUI Foundation**
  - Split-pane interface (Textual/Rich).
  - Interactive study mode beyond flashcards; live code exec in practice pane.
  - Session recording: time-on-task, error patterns.

- **Phase 2: Enhanced Learning Modes**
  - Guided lab mode with checkpoints.
  - Debugging mode (broken code, time-to-fix tracking).
  - Fluency drills (timed command recall).

- **Phase 3: Intelligence Layer**
  - Cognitive load detection to adapt difficulty.
  - Greenlight integration for struggle ingestion → remediation atoms.
  - PLM sidecar to personalize beyond FSRS.

## Atom Taxonomy (Canonical Snapshot)

- **Recall/Recognition:** flashcards, cloze (single/multi/hints), short answer (exact/fuzzy), numeric/unit/tolerance, MCQ variants.
- **Structural/Ordering:** matching, bucket/grouping, sequencing/timelines, Parsons variants.
- **Numeric/Symbolic:** calculations, formula/regex, SQL/query prediction.
- **Application/Transfer:** scenarios, predictions, fault isolation.
- **Error-Focused:** spot/fix bugs, incorrect steps, false premises, config repair.
- **Comparison:** similarities/differences/trade-offs/when-to-use/boundary cases.
- **Explanation/Elaboration:** explain/teach-back/why/causal-chain.
- **Creative/Generative:** examples, counterexamples, analogies, test cases, designs.
- **CS-Specific:** code understanding (output/state/trace), code construction, debugging, config/CLI reasoning, system/architecture, algorithmic reasoning, testing/verification.
- **Meta-Cognitive:** confidence/difficulty, reflection, error tagging, self-correction.
- **Simulation/Dynamic:** CLI emulator, branching dialogue, sliders/state puzzles, graph/network construction (via DSL/IDE), labs.

---

## Next: Implementation Roadmap

See:
- [TUI Design](tui-design.md) for interface architecture
- [Learning Atoms Reference](../reference/learning-atoms.md) for atom taxonomy
- [Scientific Foundations](../reference/scientific-foundations.md) for cognitive science backing

---

**Status:** Vision Document (Living Document)
**Last Updated:** 2025-12-21
**Authors:** Project Astartes Team
