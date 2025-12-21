# GitHub Issues

## Milestones

### Phase 0 Honest Assessment (addendum)
- Implemented infrastructure: parsing/generation pipeline, migrations, metadata/seed data. Generated 433 atoms with 58.4% chunk coverage via templates (LLM cost $0) after fixing the tables regex.
- Limitations: only 7 handlers implemented; psychometric fields not populated; atom mix skewed to flashcards; quality unvalidated (no atomicity/duplication/QA yet); runtime atoms not routed to Greenlight.
- Next fixes: add validation harness; implement additional handlers (short_answer, cloze_advanced, numeric_extended, sequencing, error_spotting); build session orchestrator + typed feedback; validate schema on Postgres/SQLite; route runtime atoms to Greenlight.

### [COMPLETED] Phase 0: ETL Pipeline Foundation (Weeks 1-2)

**Status:** Complete (2025-12-21)  
**Goal:** Infrastructure foundation without live learners

**Summary**
- Parser validation: 33/33 files parsed; 298 chunks extracted.
- Coverage: 58.4% of content chunks produced atoms (174/298).
- Atoms generated: 433 (templates, no LLM).
- Files created: migrations (024-027), metadata (`data/atom_type_metadata.json`), seed data (`data/misconception_seed_data.sql`), parser (`src/processing/course_chunker.py`), template engine (`src/content/generation/template_engine.py`), docs/tests (roadmap, TUI design, vision updates, `test_parsers.py`).

**Template breakdown**
| Rule | Generated | Notes |
|------|-----------|-------|
| CLI Commands -> Parsons | 10 | Low volume |
| Definitions -> Flashcards | 339 | Dominant |
| Tables -> Matching | 12 | Fixed regex |
| Numeric Examples -> Calculation | 71 | CCNA-heavy |
| Comparisons -> Compare Atoms | 1 | Very low |

**Implemented vs designed**
- Implemented handlers: 7 (flashcard, cloze, mcq, true_false, numeric, matching, parsons).
- Designed-only: 80+ atom metadata; psychometric fields; misconception tagging; additional handlers; Greenlight runtime routing.

**Known issues**
- Atom skew: flashcards dominate; procedural/structural atoms low.
- Quality unvalidated: no atomicity/duplication or study-session QA.
- Psychometric fields unpopulated; migrations untested on live DBs.
- Runtime atoms not routed to Greenlight; only 7 handlers live.

**Next steps (Phase 1 prep)**
- Validation harness (atomicity, duplication, numeric tolerance; sample QA).
- Implement additional handlers: short_answer, cloze_advanced, numeric_extended, sequencing, error_spotting.
- Build session orchestrator + typed feedback (outcome/error class/cognitive signal).
- Test migrations on Postgres/SQLite; align runtime handoff with Greenlight.

---

## Roadmap: DARPA Digital Tutor Implementation

**Vision:** Build a terminal-based adaptive learning system that rivals DARPA's Digital Tutor and Knewton's adaptive engine.  
**Status:** Phase 0 complete, Phase 1 starting  
**Last Updated:** 2025-12-21

### Phase 1: TUI Foundation (Weeks 1-2) - NEXT UP
- Install Textual; split-pane layouts (horizontal/vertical/3-pane); atom renderers (MCQ, Short Answer, Cloze, Parsons, Numeric, Confidence); keyboard navigation.

### Phase 2: Interactive Study Mode (Weeks 3-4)
- Session orchestration (goal → probe → core → stress → consolidation); live code/bash/SQL exec; CLI simulation; session state management.

### Phase 3: Intelligence Layer (Weeks 5-6)
- Cognitive load detection; confidence mismatch/hypercorrection; enhanced atom selection; session recording and analytics.

### Phase 4: Enhanced Atom Types (Weeks 7-8)
- Debugging challenges; design/architecture reasoning; system simulation; creative/transfer atoms.

### Phase 5: Greenlight Integration (Weeks 9-10)
- Error detection API; error → atom generation; IDE/CLI feedback loop with priority boosts.

### Phase 6: Right-Learning Integration (Weeks 11-12)
- API client for sync; export/import; content pipeline with validation/dedup/enrich/ingest; CI integration.

### Phase 7: Polish & Launch (Weeks 13-14)
- Performance; UX; docs; testing/QA; onboarding.

## Success Metrics
- Learning: retention 90% at 30 days; transfer 75%; mastery velocity 2x; confidence calibration <10% mismatch.
- UX: session completion 85%+; DAU 60%+; NPS >50.
- Technical: latency <100ms render; uptime 99.9%; data sync <5s; full offline support.

## Refactors / Features / Bugs (carry-over)
- Refactors: Anki field mappings; remove lazy imports; centralize grade logic; unify configuration; fix import structure; test migrations.
- Features: Expose Anki sync via API; configurable cloze note type; implement CLI import/config; implement mode strategies.
- Bugs: diversity weights unused; seeding inconsistency; hardcoded API URL; address atom skew/quality validation.

## New Workstreams (branches via git worktree)
- Validation & QA harness (`batch-validation`): per-atom subschema validation, atomicity/duplication checks, numeric tolerance, sample QA; test migrations on Postgres/SQLite with constraints/backfill.
- Tier-1 handlers + meta-cog (`batch-handlers`): short_answer, cloze_advanced, numeric_extended, sequencing, error_spotting; MCQ mode extensions; meta-cog prompts wrapper.
- Orchestrator & typed feedback (`batch-orchestrator`): session state machine (goal→probe→core→stress→consolidation, no repeat types unless diagnosing); typed feedback (outcome/error class/cognitive signal; hypercorrection); wire latency/attempts/confidence.
- Greenlight runtime handoff (`batch-greenlight-handoff`): implement `/greenlight/run-atom` per OpenAPI with auth/versioned errors; cortex-cli client delegation; typed `AtomResult` (partial score, test results, git/diff suggestions, meta-cog).
- Skill graph & tagging (`batch-skill-graph`): enforce atom→skill mapping and misconception/error-class tags; require skills on ingest; ensure response logging updates mastery.
