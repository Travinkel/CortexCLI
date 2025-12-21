# Phase 0: Honest Assessment & Known Issues
**Status:** Infrastructure complete; significant implementation gaps remain  
**Date:** 2025-12-21

## What Was Actually Accomplished
- Parsing: 33/33 source files parsed; 298 chunks extracted.
- Generation: 421 atoms via deterministic templates (no LLM cost).
- Coverage: 56.7% of content chunks converted (target 30%).
- Infra: Added schema migrations (misconceptions, response options, error log, psychometrics), UniversalChunker, template engine, metadata/seed data.

## Implemented vs Designed
- Implemented handlers: 7 (flashcard, cloze, mcq, true_false, numeric, matching, parsons).
- Designed only: support for 80+ atom types (metadata + schema), psychometric fields, misconception tagging in MCQ options.
- Implemented generation: 5 template rules; skewed toward definitions → flashcards.
- Not implemented: computation of IRT/psychometric fields; runtime routing to Greenlight; additional handlers.

## Known Issues & Gaps
1) Tables → Matching produced 0 atoms  
   - Likely regex/table parsing bug or missing/unsuitable tables. Needs investigation and fix.
2) Atom distribution skewed  
   - 339/421 are flashcards; other types underrepresented.
3) Quality unvalidated  
   - No atomicity/duplication checks or study-session validation of generated atoms.
4) Handler gap  
   - Only 7 of 80+ atom types have working handlers; runtime atoms not wired to Greenlight.
5) Psychometric claims not realized  
   - Fields exist, but calculation/population is pending.
6) Metric clarity  
   - Coverage refers to % of content chunks converted, not mastery or topic coverage.

## Risks
- Template-generated atoms may be lower quality than LLM-assisted; risk of shallow coverage.
- Misconception tags may rot without handler/UI support and validation.
- Schema additions need migration safety, constraints, and backfill strategy across Postgres/SQLite.

## Immediate Fixes (Phase 1 Pre-Work)
- Debug and fix table parsing/template for matching atoms; re-run generation.
- Add validation harness: atomicity, duplication, numeric tolerance checks; sample QA of generated atoms.
- Implement 3–5 additional handlers (short_answer, cloze_advanced, numeric_extended, sequencing, error_spotting).
- Separate “Designed vs Implemented” in status reports; temper claims to reflect actual handler coverage.

