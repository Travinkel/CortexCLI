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

## Next: Implementation Roadmap

See:
- [TUI Design](tui-design.md) for interface architecture
- [Learning Atoms Reference](../reference/learning-atoms.md) for atom taxonomy
- [Scientific Foundations](../reference/scientific-foundations.md) for cognitive science backing

---

**Status:** Vision Document (Living Document)
**Last Updated:** 2025-12-21
**Authors:** Project Astartes Team
