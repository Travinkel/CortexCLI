# Batch Execution Status

Last updated: 2025-12-21 22:00

## Wave 1: Infrastructure (COMPLETE)
- [x] Batch 1a: Skill Database (merged)
- [x] Batch 1b: Skill Tracker (merged)
- [x] Batch 1c: Skill Selection (merged)
- [x] Batch 2a: Greenlight Client (merged)
- [x] Batch 2b: Greenlight Integration (merged)
- [x] Batch 2c: Greenlight Database (merged)

## Wave 1.5: Content Pipeline (COMPLETE)
- [x] Batch 7: Technical Content Extractor (merged to master)
  - PDF/TXT extraction with pedagogy-informed classification
  - Evidence-backed atom generation (Parsons & Haden, Chi et al.)
  - CLI: `nls content ingest`, `nls content sources`
  - Gemini LLM integration for content classification

## Wave 1.5: Quality Gates
- [ ] Batch 2d: Quality Gates (BDD + CI)

## Wave 2: Handlers (COMPLETE)
- [x] Batch 3a: Declarative Handlers (PR #16, merged)
  - cloze_dropdown, short_answer_exact, short_answer_regex, list_recall, ordered_list_recall
- [x] Batch 3b: Procedural Handlers (PR #17, merged)
  - faded_parsons, distractor_parsons, timeline_ordering, sql_query_builder, equation_balancing
- [x] Batch 3c: Diagnostic Handlers (PR #18, merged)
  - confidence_slider, effort_rating, categorization, script_concordance_test, key_feature_problem

**Total handlers in registry: 22** (7 original + 15 new from Wave 2)

## Wave 3: Schemas (READY FOR PARALLEL EXECUTION)

**Worktrees prepared:** All rebased to latest master (dbdf020)

| Batch | Worktree Path | CLAUDE.md | Schema Count |
|-------|---------------|-----------|--------------|
| 4a: Declarative | `../cortex-batch-4a-schemas-declarative` | Ready | 12 schemas |
| 4b: Procedural | `../cortex-batch-4b-schemas-procedural` | Ready | 11 schemas |
| 4c: Diagnostic | `../cortex-batch-4c-schemas-diagnostic` | Ready | 9 schemas |
| 4d: Generative | `../cortex-batch-4d-schemas-generative` | Ready | 8 schemas |
| 4e: Advanced | `../cortex-batch-4e-schemas-advanced` | Ready | 60+ schemas |

**To execute Wave 3 in parallel:**
```bash
# Terminal 1: Batch 4a (12 declarative schemas)
cd E:/Repo/cortex-batch-4a-schemas-declarative
claude

# Terminal 2: Batch 4b (11 procedural schemas)
cd E:/Repo/cortex-batch-4b-schemas-procedural
claude

# Terminal 3: Batch 4c (9 diagnostic schemas)
cd E:/Repo/cortex-batch-4c-schemas-diagnostic
claude

# Terminal 4: Batch 4d (8 generative schemas)
cd E:/Repo/cortex-batch-4d-schemas-generative
claude

# Terminal 5: Batch 4e (60+ advanced schemas)
cd E:/Repo/cortex-batch-4e-schemas-advanced
claude
```

- [ ] Batch 4a: Declarative Schemas (ready)
- [ ] Batch 4b: Procedural Schemas (ready)
- [ ] Batch 4c: Diagnostic Schemas (ready)
- [ ] Batch 4d: Generative Schemas (ready)
- [ ] Batch 4e: Advanced Schemas (ready)

## Wave 4: Documentation
- [ ] Batch 5a: GitHub Issues (blocked until Wave 3 complete)
- [ ] Batch 5b: Documentation (blocked until Wave 3 complete)

## Wave 5: Knowledge Integration (Cochrane-Class Systematic Review)

**Architecture:** See [docs/architecture/knowledge-integration.md](../architecture/knowledge-integration.md)

**The Vision:** Transform RigorHub into a Cochrane-class Systematic Review Engine where:
- ResearchEngine owns the Master Ledger (write path)
- CortexCLI + RigorHub consume via read-only API/MCP
- Every atom has full provenance (tech source) + justification (scientific evidence)

| Batch | Repo | Scope | Status |
|-------|------|-------|--------|
| 8a: KB Ledger Upgrade | ResearchEngine | Schema, audit, review, lifting | Blocked (Wave 4) |
| 8b: KB Consumer | CortexCLI | Client, enrichment, CLI commands | Blocked (8a) |
| 8c: MCP Registration | AstartesAgents | Supervisor, Docker, agent docs | Blocked (8a) |

### Batch 8a: KB Ledger Upgrade (ResearchEngine)
- [ ] Add `tech_sources.license` column
- [ ] Add `clean_atoms.knowledge_item_id` direct FK
- [ ] Upgrade audit with expert blind spot detection
- [ ] Implement edge-aware systematic review
- [ ] Route lifting through ETL + ICAP classifier

### Batch 8b: KB Consumer (CortexCLI)
- [ ] MCP/API client for read-only KB access
- [ ] `nls content enrich --domain <domain>` command
- [ ] Local atom storage with provenance fields
- [ ] Evidence linking at enrichment time

### Batch 8c: MCP Registration (AstartesAgents)
- [ ] Supervisor config for kb-mcp service
- [ ] Docker Compose integration
- [ ] Agent integration documentation
- [ ] Health check endpoint

**Work Orders:**
- [batch-8a-kb-ledger.md](batch-8a-kb-ledger.md)
- [batch-8b-kb-consumer.md](batch-8b-kb-consumer.md)
- [batch-8c-mcp-registration.md](batch-8c-mcp-registration.md)

## Wave 6: SharedKernel Consolidation

**Architecture:** See [docs/architecture/shared-kernel.md](../architecture/shared-kernel.md)

**The Vision:** Extract reusable components into SharedKernel monorepo so all Astartes products share common infrastructure.

| Batch | Repo | Scope | Status |
|-------|------|-------|--------|
| 9: ContentExtractor | SharedKernel | PDF/TXT extractors, classifiers | Blocked (Wave 5) |

### Batch 9: SharedKernel ContentExtractor
- [ ] Create `ContentExtractor/` in SharedKernel
- [ ] Move PDF/TXT extractors from cortex-cli
- [ ] Move Gemini classifier from cortex-cli
- [ ] Package as `astartes-content-extractor`
- [ ] Update cortex-cli to import from SharedKernel
- [ ] Update ResearchEngine to use shared extractors

**Work Orders:**
- [batch-9-shared-kernel-extractor.md](batch-9-shared-kernel-extractor.md)

**SharedKernel Structure:**
```
E:\Repo\project-astartes\SharedKernel\
├── AstartesAgents/       # Agent orchestration
├── KnowledgeBase/        # Evidence storage + API
├── MCP/                  # Model Context Protocol servers
├── ResearchEngine/       # Systematic review pipeline
└── ContentExtractor/     # NEW - Technical content parsing
```
