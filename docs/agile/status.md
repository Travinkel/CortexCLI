# Batch Execution Status

Last updated: 2025-12-21 21:30

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

## Wave 2: Handlers (READY FOR PARALLEL EXECUTION)

**Worktrees prepared:** All rebased to latest master (4301558)

| Batch | Worktree Path | CLAUDE.md | Atom Types |
|-------|---------------|-----------|------------|
| 3a: Declarative | `../cortex-batch-3a-handlers-declarative` | Ready | cloze_dropdown, short_answer_exact, short_answer_regex, list_recall, ordered_list_recall |
| 3b: Procedural | `../cortex-batch-3b-handlers-procedural` | Ready | faded_parsons, distractor_parsons, timeline_ordering, sql_query_builder, equation_balancing |
| 3c: Diagnostic | `../cortex-batch-3c-handlers-diagnostic` | Ready | confidence_slider, effort_rating, categorization, script_concordance_test, key_feature_problem |

**To execute Wave 2 in parallel:**
```bash
# Terminal 1: Batch 3a
cd E:/Repo/cortex-batch-3a-handlers-declarative
claude

# Terminal 2: Batch 3b
cd E:/Repo/cortex-batch-3b-handlers-procedural
claude

# Terminal 3: Batch 3c
cd E:/Repo/cortex-batch-3c-handlers-diagnostic
claude
```

- [ ] Batch 3a: Declarative Handlers (ready)
- [ ] Batch 3b: Procedural Handlers (ready)
- [ ] Batch 3c: Diagnostic Handlers (ready)

## Wave 3: Schemas
- [ ] Batch 4a: Declarative Schemas (blocked until Wave 2 complete)
- [ ] Batch 4b: Procedural Schemas (blocked until Wave 2 complete)
- [ ] Batch 4c: Diagnostic Schemas (blocked until Wave 2 complete)
- [ ] Batch 4d: Generative Schemas (blocked until Wave 2 complete)
- [ ] Batch 4e: Advanced Schemas (blocked until Wave 2 complete)

## Wave 4: Documentation
- [ ] Batch 5a: GitHub Issues (blocked until Wave 3 complete)
- [ ] Batch 5b: Documentation (blocked until Wave 3 complete)

## Wave 5: Knowledge Injection
- [ ] Batch 6: Knowledge Injection Pipeline (blocked until KB populated)
