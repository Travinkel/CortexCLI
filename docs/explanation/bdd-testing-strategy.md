# bdd testing strategy

## purpose

Define behavior-driven tests that validate cognitive behavior, not just code paths. The goal is to verify that atom selection, grading, and mastery updates behave as the learning science requires.

## scope

- unit tests: grading and mastery formulas
- integration tests: session flow across selector, tracker, and storage
- bdd scenarios: given/when/then coverage of adaptive behavior
- acceptance checks: periodic validation of retention and transfer

## core principles

- cognition is the contract (tests assert learning behavior, not only values)
- misconceptions are first-class (distractors map to diagnoses)
- timing is signal (latency influences remediation)
- mastery is probabilistic (assert ranges, not exact values)

## bdd scenario patterns

- skill gap targeting
- hypercorrection when confidence is high and answer is wrong
- scaffolding step-down when constructive atoms fail
- promotion when active atoms are mastered
- greenlight execution handoff

## required artifacts

- tests/bdd/features/*.feature
- tests/bdd/steps/*.py
- fixtures for skills, atoms, misconceptions
- database setup for integration runs

## required coverage

- each atom family has at least one bdd scenario
- each remediation path has at least one bdd scenario
- each schema change has a migration test

## ci alignment

- bdd runs on pr checks (skip if no tests/bdd)
- nightly runs include acceptance and psychometric checks
- failures block merge unless explicitly waived

## links

- ci-cd-pipeline.md
- schema-migration-plan.md
- learning-atom-taxonomy.md
