# schema migration plan: flashcard to polymorphic atoms

## purpose

Move from front/back flashcard storage to polymorphic JSONB atoms with explicit grading logic, ICAP metadata, and misconception linkage.

## current bottlenecks

- front/back text fields force JSON parsing in handlers
- database cannot index atom content
- distractors are not linked to misconception ids
- bloom levels are stored instead of ICAP + cognitive load
- grading logic is hardcoded in engine conditionals

## target schema

Core tables:
- learning_atoms (content jsonb, grading_logic jsonb)
- atom_response_options (distractor -> misconception)
- skills and atom_skill_weights (already in place)

Required columns on learning_atoms:
- content jsonb (prompt, assets, parameters)
- grading_logic jsonb (correct answer, tests, rules)
- engagement_mode (icap)
- element_interactivity_index (clt)
- knowledge_dimension (factual, conceptual, procedural, metacognitive)

## migration phases

1. add new columns (non-breaking)
2. backfill content and grading_logic from front/back
3. create atom_response_options and extract distractors
4. update handlers to use jsonb + grader strategies
5. remove front/back and enforce not null

## grading strategy refactor

- replace monolithic if/elif in learning_engine with strategy classes
- learning_atoms stores grading_strategy key
- engine calls strategy.evaluate(user_input, grading_logic)

## icap replacement

- remove blooms_level from generators and schemas
- add engagement_mode + element_interactivity_index
- update prompts and atom factories to output ICAP tags

## validation and tests

- migration tests: no atoms left with null content or grading_logic
- schema checks: jsonb validates against schemas
- bdd scenarios: grading and remediation flows

## links

- learning-atom-taxonomy.md
- bdd-testing-strategy.md
- ci-cd-pipeline.md
