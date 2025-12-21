# Atom Schema & Integration Plan

Purpose: bridge the 100+ atom taxonomy to a workable implementation across cortex-cli (terminal) and Greenlight (IDE/runtime), with a single envelope/schema and clear routing.

## Critique of the proposed taxonomy + schema
- Good: broad coverage (100+ atoms), cognitive layering, JSON-centric schema.
- Gaps/risks:
  - No skill graph link: atoms must map to skills/concepts (many-to-many) for targeting and mastery tracking.
  - Validation missing: `payload`/`grading_logic` are open; need per-atom schema and validation.
  - Runtime atoms: need runner/test contract (language, entrypoint, test command, limits) and typed error results.
  - Diff/git guidance: should be typed (commands/patch) to avoid unsafe suggestions.
  - Meta-cog scales: confidence/difficulty must be defined (e.g., 1–5) and when to prompt (pre/post).
  - Telemetry: need latency, attempts, error class in results for routing and diagnostics.
  - DB compatibility: JSONB assumed; ensure SQLite fallback strategy if offline mode matters.

## Plan (repo-level)
- Schema & routing
  - Adopt the shared envelope (`docs/reference/atom-envelope.schema.json`) with `owner` (cortex|greenlight) and `grading_mode` (static|runtime|human|hybrid).
  - Add DB support: JSONB columns for `content`/`grading_logic`, skill linking, misconception tags, and runner/diff metadata for runtime atoms.
  - Define per-atom subschemas (Tier 1 first: short_answer, cloze_advanced, numeric_extended, sequencing, matching/bucket, error_spotting, mcq modes, meta-cog prompts).
  - Keep a typed result schema (AtomResult) with partial scores, test results, meta-cog captures, telemetry.
- Taxonomy coverage
  - Target 100+ interaction primitives (Grand Unified taxonomy: discrimination/perception, declarative, procedural/sequential, diagnosis/reasoning, generative, data/analysis, meta-cog/affective, fluency, plus domain-specific medical/flight/music/coding/logic).
  - Prioritize implementation by tiers: Tier 1 (existing + core recall/structural), Tier 2 (CS/debugging/runtime), Tier 3 (simulation/dynamic/creative), aligning runtime-heavy atoms to Greenlight.
- Runtime handoff (Greenlight)
  - Implement `/greenlight/run-atom` per `docs/reference/greenlight-handoff.openapi.yaml`.
  - Align runner fields to Greenlight capabilities (lang, entrypoint, tests, limits, sandbox_policy) and diff/git guidance output (typed suggestions).
  - cortex-cli: client wrapper that delegates runtime atoms, renders results in terminal.
- Handlers (cortex-cli)
  - Add Tier 1 handlers using the existing AtomHandler protocol; extend MCQ modes; add meta-cog wrappers.
  - Validation: enforce per-atom schema at load time; reject malformed atoms early.
- Skill graph & tagging
  - Add skill mapping table and misconception tags; ensure each atom declares targeted skills and optional misconceptions/error classes.
  - Wire mastery updates to responses (even if simple Bayesian/FSRS hybrid initially).
- Quality & tests
  - Add validation tests for each new handler; sample-based atomicity/duplication checks for generated atoms; numeric tolerance edge cases.
  - For runtime atoms, add integration tests that hit the handoff endpoint with a fixture runner.

## Suggested GitHub issues (draft text)
1) Finalize atom envelope and DB schema
   - Implement JSONB-backed Atom table with content/grading_logic, runner/diff metadata, skill links, misconception tags.
   - Add migrations for Postgres; document SQLite fallback.
   - Validate against `docs/reference/atom-envelope.schema.json`.
2) Runtime handoff: Greenlight API + cortex-cli client
   - Implement `/greenlight/run-atom` per `docs/reference/greenlight-handoff.openapi.yaml`.
   - Return typed AtomResult (partial score, test results, git suggestions, meta-cog).
   - Add cortex-cli client and terminal rendering for runtime atoms.
3) Tier 1 handlers (cortex-cli)
   - Add handlers: short_answer, cloze_advanced, numeric_extended, sequencing, matching/bucket, error_spotting; extend MCQ modes.
   - Add per-atom validation and hint/partial-credit logic; meta-cog prompts wrapper.
4) Skill graph & tagging
   - Add skill mapping and misconception/error-class tagging to atoms.
   - Update ingestion to require skills; update response logging to update mastery signals.
5) Quality and validation harness
   - Add schema validation step in ingest; add atomicity/duplication checks; numeric tolerance edge cases.
   - Add integration tests for runtime handoff with fixture runner; sample QA checklist for generated atoms.
