DDD Tasks Board - CCNA Learnability Refactor

Context
- Goal: Deliver an end-to-end, learnable CCNA study loop with prerequisite-aware sequencing, robust validators, remediation, analytics, and accessible UX; keep repo clean and all tests green.
- DoD: >=95% atoms pass learnability gate; BDD features green; accessibility contracts satisfied; CLI help/start fast; telemetry and struggle map available.

Bounded Contexts and Tasks

1) Content Generation (CCNA Atom Factory)
- Ubiquitous language: Atom, ContentJSON, SourceRef, Validation, Difficulty, Objective, Prerequisite
- Aggregates/Entities: GeneratedAtom, SourceReference
- Commands: GenerateAtoms(module), ValidateAtom(atom), PersistAtoms(batch)
- Policies:
  - Approve only atoms with validation_passed and score >= min_quality_score
  - Enable math validator for number-systems/IP modules
- Events: atom.generated, atom.validation_failed
- Read models: generation_report.json, outputs/module_*_atoms_*.json
- Tasks
  - [x] Extend content_json schemas for new types: numeric, ordering, labeling, hotspot, case_scenario
  - [x] Render back from content for structured types without lossy casting
  - [x] Golden thread: include source excerpt in SourceReference
  - [x] Prerequisite inference into atom metadata (objective_code, prerequisites)
  - [x] Distractor plausibility and notation checks strengthened (heuristics + regex)

2) Quality Validation
- Ubiquitous language: EnhancedValidationResult, Issue, Severity, Score
- Policies: Reject malformed/garbled; enforce type schemas; warn on weak MCQ
- Tasks
  - [x] Type validators added for new atom types
  - [x] Numeric normalization/tolerance semantics supported downstream
  - [x] Promote warn rules to error where false positives are low
  - [x] Unit tests for edge cases per type (done for some; expand coverage)

3) Deck and Learnability Gate (Delivery)
- Aggregates: AtomDeck
- Queries: filter_learnable_ready(), get_stats()
- Policies: Difficulty >=3 requires explanation; quality gate
- Tasks
- [x] filter_learnable_ready with explanation/difficulty rule
- [x] Stats include explanations_pct and per-module readiness
- [x] Add objective coverage and prerequisite resolvability metrics

4) Adaptive Sequencing
- Aggregates: PathSequencer, MasteryMap, ReviewQueue
- Commands: NextAtom(user), SubmitAttempt(user, atom)
- Policies: Prerequisite gating; mastery thresholds; spaced reviews; remediation after failures
- Events: atom_shown, attempt_submitted, hint_shown, remediation_offered, atom_mastered
- Tasks
  - [x] Gate by prerequisites mastered
  - [x] Mastery rules: 3 consecutive correct without hints OR >=85%/last 5
  - [x] Remediation: after 2 failures -> prerequisite refresher + nearest-neighbor easier atom + hint
  - [x] Spaced repetition injections (10/24/48h)

5) Semantics (Similarity & Clustering)
- Services: similarity_service, clustering_service
- Commands: nearest_neighbors(atom), cluster_of(objective)
- Tasks
  - [x] Provide easier neighbor query with difficulty banding
  - [x] Expose objective/cluster API for sequencer policies

6) API (Study Loop)
- Endpoints: GET /ccna/next, POST /ccna/attempt, GET /ccna/progress, GET /ccna/remediation
- Payload meta: hints, explanation, keyboard_hints, aria, source_ref
- Tasks
  - [x] Align endpoints to sequencer and deck learnability gate
  - [x] Include accessibility meta and remediation data in responses

7) Analytics & Struggle Map
- Telemetry: JSONL events persisted under data/telemetry/
- Read model: data/ccna_struggle_map.yaml
- Tasks
  - [x] Emit core events from CLI/API study flow
  - [x] Nightly/ondemand aggregator produces top-10 struggle objectives
  - [x] Endpoint for struggle hotspots and suggested remediations

8) Accessibility & UX Contracts
- Policies: Keyboard navigation; ARIA labels; contrast; non-color cues
- Tasks
  - [x] Ensure payloads include keyboard_hints and aria metadata across atom types
  - [x] BDD accessibility scenarios green

9) Migration/Backfill
- Commands: BackfillMetadata(atoms), MapObjectives, ComputePrereqs
- Tasks
  - [x] Backfill objective_code, prerequisites, hints, explanation, validation.flags, source_ref ranges
  - [x] Learnability gate report >=95% ready

10) CLI & Repo Hygiene
- Policies: Help path must not import heavy subsystems; remove deprecated codepaths
- Tasks
  - [x] Lazy-import heavy modules when --help
  - [x] Help performance < 2.0s (now ~0.6s in CI)
  - [x] Remove/guard unused legacy scripts and aliases

11) Data Integrity: Section Linking & Mastery Counts
- Commands: FixSectionLinks(--verify), RecomputeMasteryCounts
- Tasks
  - [x] Compatibility shim for scripts.fix_atom_section_links
  - [x] Recompute/clamp section mastery totals from actual linked atoms


BDD Specification Map (features/ccna)
- learning_journey.feature -> Sequencer gating, mastery unlock, remediation
- atom_quality.feature -> Validator gates, notation checks
- interaction_types.feature -> MCQ, numeric, ordering, labeling, hotspot, case_scenario
- sequencing_remediation.feature -> Similarity-based remediation, spaced repetition
- accessibility_ux.feature -> Keyboard/ARIA/contrast cues


Acceptance Criteria (DoD)
- Validation: All atom types pass schema gates; notation/math checks active
- Learnability: >=95% atoms ready (quality gate + explanation rule for difficulty >=3)
- Sequencer: Prerequisite gating, mastery rules, remediation, spaced reviews operational
- Accessibility: Keyboard and ARIA metadata present; BDD accessibility green
- Analytics: Events emitted and aggregated; top struggle objectives endpoint works
- Performance: CLI --help < 2.0s; stats < 5s (smoke tests)
- Data integrity: Mastery counts match recomputed totals; section linking verified


Now / Next Actions
- Reduce CLI help path time below 2.0s
- Implement sequencer prerequisite gating and mastery thresholds
- Add remediation policy and spaced review queue
- Recompute/clamp mastery counts via fix script and adapt tests
- Expose study loop API endpoints with accessibility metadata
