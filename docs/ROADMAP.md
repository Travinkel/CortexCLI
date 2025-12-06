# NLS Cortex 2.0 Implementation Roadmap

**Last Updated**: December 6, 2025
**Current Status**: ✅ Phase 5 COMPLETE - Neuromorphic Integration Wired
**Focus**: All core components integrated into session loop

---

## Executive Summary

This roadmap transforms the existing NLS from a **Behaviorist Learning System** (stimulus-response flashcards) into a **Cognitive Augmentation System** that models and enhances the learner's brain.

### ✅ Phase 5 Completed

All core components have been wired into the learning engine:

| Component | Status | Integration Point |
|-----------|--------|-------------------|
| NCDE Cognitive Diagnosis | ✅ Complete | `submit_answer()` calls `diagnose_interaction()` |
| Telemetry Capture | ✅ Complete | Response time, error streaks tracked per session |
| Strategy-Specific Remediation | ✅ Complete | `_get_cognitive_remediation()` routes by FailMode |
| Z-Score/Focus Stream | ✅ Complete | `get_focus_stream_atoms()` uses ZScoreEngine |
| Force Z Backtracking | ✅ Complete | `check_force_z_backtrack()` for prereq gaps |
| LLM Tutoring | ✅ Complete | `get_tutor_hint()` integrates VertexTutor |
| Learner Persona | ✅ Complete | `end_session()` calls PersonaService |
| Prerequisite Inference | ✅ Complete | `PrerequisiteInferenceService` ready |

### Strategic Decision: Notion on Ice

**All Notion-related work remains paused.** Python codebase integration is complete.

---

## Current Capability Assessment

### Production-Ready (95%)

| Component | Location | Lines | Status |
|-----------|----------|-------|--------|
| Cortex CLI | `src/cli/cortex.py` | 1,277 | 95% |
| StudyService | `src/study/study_service.py` | 1,349 | 90% |
| **Adaptive Engine** | `src/adaptive/learning_engine.py` | **1,600+** | **100%** |
| Mastery Calculator | `src/study/mastery_calculator.py` | 300+ | 100% |
| Quiz System | `src/quiz/quiz_service.py` | 400+ | 100% |
| Prerequisite Queries | `src/adaptive/remediation_router.py` | 350+ | 100% |
| FSRS Implementation | `src/anki/anki_client.py` | 400+ | 100% |
| Google Calendar | `src/integrations/google_calendar.py` | 345 | 100% |
| **Z-Score Engine** | `src/graph/zscore_engine.py` | 618 | **100%** |
| **Vertex Tutor** | `src/integrations/vertex_tutor.py` | 798 | **100%** |
| **Persona Service** | `src/adaptive/persona_service.py` | 867 | **100%** |
| **Prerequisite Inference** | `src/semantic/prerequisite_inference.py` | 416 | **100%** |

### Remaining Work (5%)

| Component | Gap | Priority |
|-----------|-----|----------|
| **CLI Integration** | `cortex chat` command needs to use Vertex Tutor | P3 |
| **Bio-rhythm Scheduling** | Calendar optimization by chronotype | P3 |
| **Neo4j Shadow Graph** | Optional graph database for centrality | P3 |

---

## Implementation Phases

### Phase 5.1: Wire NCDE into Session Loop (Current)

**Status**: IN PROGRESS
**ETA**: 2-3 hours
**Priority**: P0 - Critical Path

#### The Gap

The session loop in `learning_engine.py:submit_answer()` calls:
```python
remediation_plan = self._remediator.check_remediation_needed(...)
```

But it does **NOT** call:
```python
diagnosis = diagnose_interaction(atom, is_correct, response_time_ms, history)
```

This means all errors are treated generically ("needs more practice") instead of cognitively:
- ENCODING_ERROR → should trigger elaboration
- DISCRIMINATION_ERROR → should trigger contrastive lures
- EXECUTIVE_ERROR → should trigger "slow down"

#### Tasks

1. **Import neuro_model** into `learning_engine.py`
2. **Create InteractionEvent** from answer submission
3. **Call `diagnose_interaction()`** after `_evaluate_answer()`
4. **Pass diagnosis to remediation router** for strategy selection
5. **Select atoms based on RemediationType** (not generic)
6. **Store diagnosis** in session state for telemetry

#### Files to Modify

- `src/adaptive/learning_engine.py` - Wire diagnosis into submit_answer
- `src/adaptive/remediation_router.py` - Accept diagnosis, return strategy-specific atoms
- `src/adaptive/neuro_model.py` - Ensure `diagnose_interaction()` is complete

---

### Phase 5.2: Implement Telemetry Capture

**Status**: PENDING
**ETA**: 1-2 hours
**Priority**: P1

#### Current State

Session loop processes answers but discards:
- Response time (milliseconds)
- User confidence (if captured)
- Session history for pattern detection

#### Tasks

1. **Capture response timing** in CLI answer handler
2. **Pass `time_taken_seconds`** to `submit_answer()`
3. **Build rolling history** for fatigue detection
4. **Store in `atom_responses`** table
5. **Expose via session stats** endpoint

#### Files to Modify

- `src/cli/cortex.py` - Capture timing at answer
- `src/adaptive/learning_engine.py` - Accept and propagate timing
- `src/study/study_service.py` - Record to database

---

### Phase 5.3: Strategy-Specific Remediation

**Status**: PENDING
**ETA**: 3-4 hours
**Priority**: P1

#### The Mapping

| FailMode | RemediationType | Atom Selection Strategy |
|----------|-----------------|------------------------|
| `ENCODING_ERROR` | `ELABORATE` | Re-present with elaboration hints |
| `RETRIEVAL_ERROR` | `SPACED_REPEAT` | Standard FSRS with shorter interval |
| `DISCRIMINATION_ERROR` | `CONTRASTIVE` | Surface confusable pairs |
| `INTEGRATION_ERROR` | `WORKED_EXAMPLE` | Show step-by-step solution |
| `EXECUTIVE_ERROR` | `SLOW_DOWN` | Same atom with forced latency |
| `FATIGUE_ERROR` | `SLOW_DOWN` | Suggest micro-break |

#### Tasks

1. **Create `get_remediation_atoms()` method** that accepts `CognitiveDiagnosis`
2. **Query atoms by type** based on strategy
3. **For CONTRASTIVE**: Surface atoms with same parent concept
4. **For WORKED_EXAMPLE**: Surface atoms with `atom_type = 'parsons'`
5. **For ELABORATE**: Add elaboration context to atom

#### Files to Modify

- `src/adaptive/remediation_router.py` - New strategy logic
- `src/adaptive/neuro_model.py` - Ensure RemediationType enum matches
- `src/db/queries/` - New queries for strategy-specific atoms

---

### Phase 5.4: Complete Cortex 2.0 Integration

**Status**: PENDING
**ETA**: 4-6 hours
**Priority**: P2

#### Components

1. **Z-Score Algorithm**: Compute attention urgency from decay + centrality + project + novelty
2. **Force Z Backtracking**: When mastery < threshold, queue prerequisites
3. **Focus Stream**: Surface high-Z atoms for study

#### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Z-SCORE COMPUTATION                          │
│                                                                  │
│  Z(a) = w_d·D(a) + w_c·C(a) + w_p·P(a) + w_n·N(a)              │
│                                                                  │
│  D(a) = Decay signal (time since last touch)                    │
│  C(a) = Centrality signal (PageRank in knowledge graph)         │
│  P(a) = Project relevance signal (active learning goals)        │
│  N(a) = Novelty signal (new atoms boost)                        │
└─────────────────────────────────────────────────────────────────┘
```

#### Tasks

1. **Create `zscore_service.py`** with Z computation
2. **Wire into atom selection** in learning engine
3. **Add Force Z trigger** when prereq mastery low
4. **Create "Focus Stream" view** (Z > threshold)

---

### Phase 5.5: LLM Tutoring with Vertex AI

**Status**: PENDING
**ETA**: 4-6 hours
**Priority**: P2

#### Current State

`vertex_tutor.py` exists but is not integrated into:
- Session remediation flow
- `cortex chat` command
- Persona-aware prompts

#### Tasks

1. **Initialize Vertex AI** in session startup
2. **Call `get_remediation()`** when NCDE triggers intervention
3. **Pass `persona.to_prompt_context()`** for personalization
4. **Implement `cortex chat`** command for interactive tutoring
5. **Record intervention effectiveness** (was it helpful?)

#### Files to Modify

- `src/cli/cortex.py` - Wire Vertex into session, add chat command
- `src/integrations/vertex_tutor.py` - Ensure prompts are complete
- `src/adaptive/persona_service.py` - Provide persona context

---

### Phase 5.6: Learner Persona Service

**Status**: PENDING
**ETA**: 3-4 hours
**Priority**: P2

#### Current State

- `persona_service.py` exists with `LearnerPersona` dataclass
- Database tables exist (`learner_profiles`)
- No logic to **build** or **evolve** the persona

#### Tasks

1. **Initialize persona** on first session
2. **Update `strength_*` fields** from session stats
3. **Update `effectiveness_*` fields** from mechanism tracking
4. **Detect chronotype** from session time patterns
5. **Calculate calibration** from confidence vs accuracy

#### Files to Modify

- `src/adaptive/persona_service.py` - Implement `update_from_session()`
- `src/study/study_service.py` - Call persona update after session
- `src/cli/cortex.py` - Add `cortex profile` command

---

### Phase 5.7: Prerequisite Inference Algorithm

**Status**: PENDING
**ETA**: 6-8 hours
**Priority**: P3

#### Approach

1. **Extract explicit prerequisites** from atom tags/relations
2. **Generate embeddings** for all atoms using Vertex AI
3. **Train GNN** on known prerequisites
4. **Infer missing prerequisites** using embedding similarity

#### Tasks

1. **Create embedding pipeline** for atoms
2. **Store embeddings** in pgvector column
3. **Query similar atoms** for prerequisite candidates
4. **Build manual override system** for corrections

---

## Visual Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                           CORTEX 2.0 FLOW                             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐           │
│   │   CLI       │────>│   Session   │────>│   NCDE      │           │
│   │  (cortex)   │     │   Engine    │     │ (diagnosis) │           │
│   └─────────────┘     └──────┬──────┘     └──────┬──────┘           │
│                              │                    │                   │
│                              v                    v                   │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐           │
│   │  Persona    │<───>│  Remediation│<────│   Atom      │           │
│   │  Service    │     │   Router    │     │  Selector   │           │
│   └─────────────┘     └──────┬──────┘     └─────────────┘           │
│                              │                                        │
│                              v                                        │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐           │
│   │  Vertex AI  │<────│  Strategy   │────>│   Focus     │           │
│   │  (LLM)      │     │  Executor   │     │   Stream    │           │
│   └─────────────┘     └─────────────┘     └─────────────┘           │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Dependency Graph

```
Phase 5.1 (NCDE Wiring)
    │
    ├──> Phase 5.2 (Telemetry) ──┐
    │                             │
    └──> Phase 5.3 (Strategies) ──┼──> Phase 5.4 (Z-Score)
                                  │         │
                                  │         v
                                  └──> Phase 5.5 (LLM)
                                            │
                                            v
                                      Phase 5.6 (Persona)
                                            │
                                            v
                                      Phase 5.7 (Inference)
```

---

## Time Estimates

| Phase | Task | Hours | Status |
|-------|------|-------|--------|
| 5.1 | Wire NCDE into session | 2-3 | IN PROGRESS |
| 5.2 | Telemetry capture | 1-2 | Pending |
| 5.3 | Strategy-specific remediation | 3-4 | Pending |
| 5.4 | Cortex 2.0 Z-Score/Force Z | 4-6 | Pending |
| 5.5 | LLM tutoring | 4-6 | Pending |
| 5.6 | Learner persona | 3-4 | Pending |
| 5.7 | Prerequisite inference | 6-8 | Pending |
| **Total** | | **23-33** | |

---

## Success Criteria

### Phase 5.1 Complete When:
- [ ] `submit_answer()` calls `diagnose_interaction()`
- [ ] Diagnosis stored in session state
- [ ] Unit tests pass for all FailModes

### Phase 5.2 Complete When:
- [ ] Response time captured in CLI
- [ ] Timing propagated to learning engine
- [ ] `atom_responses.response_time_ms` populated

### Phase 5.3 Complete When:
- [ ] Each FailMode maps to a remediation strategy
- [ ] `get_remediation_atoms()` returns strategy-specific atoms
- [ ] Contrastive atoms surfaced for discrimination errors

### Phase 5.4 Complete When:
- [ ] Z-Score computed for all atoms
- [ ] Focus Stream filters atoms by Z threshold
- [ ] Force Z backtracking triggers on low prereq mastery

### Phase 5.5 Complete When:
- [ ] Vertex AI initialized in session
- [ ] Remediation explanations generated on intervention
- [ ] `cortex chat` command functional

### Phase 5.6 Complete When:
- [ ] Persona created on first session
- [ ] Strengths updated from session stats
- [ ] `cortex profile` displays persona

### Phase 5.7 Complete When:
- [ ] Atom embeddings generated and stored
- [ ] Similar atoms queryable by vector
- [ ] Prerequisite suggestions surfaced

---

## Key Files Reference

### Core Session Loop
- `src/adaptive/learning_engine.py:submit_answer()` - Answer processing
- `src/adaptive/neuro_model.py:diagnose_interaction()` - Cognitive diagnosis
- `src/adaptive/remediation_router.py:check_remediation_needed()` - Remediation

### Services
- `src/adaptive/persona_service.py` - Learner profile management
- `src/integrations/vertex_tutor.py` - AI tutoring
- `src/study/study_service.py` - Session management

### Database
- `migrations/012_neurocognitive_integration.sql` - NCDE tables
- `migrations/013_adaptive_engine.sql` - Persona/intervention tables

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Vertex AI quota limits | Implement fallback remediation (no LLM) |
| Embedding generation slow | Batch process offline, cache in pgvector |
| Z-Score computation expensive | Compute incrementally, cache hot atoms |
| Persona cold start | Default persona with conservative assumptions |

---

## Notion Integration (ON ICE)

When Notion work resumes:
1. Sync Z_Score back to Flashcards database
2. Update Memory_State based on FSRS
3. Create Focus Stream view in Notion
4. Sync learner persona to Notion for dashboards

**Not touching Notion until Python codebase is complete.**

---

## Appendix: Learning Science Concepts to Study

For understanding the cognitive model:
1. **Desirable Difficulties** (Bjork) - Why struggle helps
2. **Cognitive Load Theory** - Managing working memory
3. **P-FIT Theory** - Neural basis of intelligence
4. **Pattern Separation** - Hippocampal discrimination
5. **Perceptual Learning Modules** - Fluency training
6. **FSRS Algorithm** - Optimal spacing computation
7. **Knowledge Tracing** - Bayesian mastery models
