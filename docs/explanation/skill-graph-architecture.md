# Skill Graph Architecture

This document describes the skill graph design, database schema, mastery tracking, and scheduling integration (FSRS). It is intended for engineers implementing the skill graph and its integration with atoms and the scheduling system.

## Overview

The skill graph enables many-to-many mapping between learning atoms and skills. Each atom links to one or more skills with weights indicating how much the atom measures that skill.

## Database Schema

### skills
- id (TEXT PK)
- name
- parent_id (nullable)
- cognitive_level (enum)
- icap_engagement (enum)
- created_at, updated_at

### atom_skill_weights
- id
- atom_id (FK -> atoms.id)
- skill_id (FK -> skills.id)
- weight (FLOAT 0..1)
- is_primary (BOOL)

### learner_skill_mastery
- id
- learner_id
- skill_id
- mastery_prob (FLOAT 0..1)
- last_updated
- fsrs_params (JSON) -- optional

## Bayesian Mastery Updates

We update per-skill mastery probabilities based on observed responses to linked atoms. A simple bayesian update:

P(M | D) = P(D | M) * P(M) / (P(D | M) * P(M) + P(D | ~M) * P(~M))

Where D is observed correct/incorrect and likelihoods are derived from item difficulty and discrimination.

## FSRS Integration

FSRS scheduling uses retrievability estimates and item stability to compute next practice intervals. Integrate per-skill stability updates by mapping atom outcomes to skill-level retrievability.

R(t) = exp(-t / S)

Where S is stability parameter.

## API Endpoints

### GET /skills/{id}
Return skill metadata and atom links.

### POST /learners/{id}/skills/{skill_id}/update
Body: {"outcome": "correct"|"incorrect", "timestamp": ...}
Updates mastery probability and schedules next review.

## Implementation notes
- Normalize skill IDs (namespace:domain:topic[:subtopic]).
- Allow fractional weights for atom->skill mapping.
- Provide tooling to bulk import taxonomy from CSV/Notion exports.

## Testing
- Unit tests for Bayesian update function.
- Integration tests for end-to-end flows: atom attempted -> skill update -> scheduler next date.

---

This file is a concise architecture overview; expand with ER-diagrams, SQL migrations, and example queries as needed.
