# How to Validate Atom Quality

This guide describes a research-grade validation workflow for learning atoms, including psychometric analyses and distractor effectiveness.

## Goals
- Ensure items measure intended skills.
- Detect low-quality distractors or ambiguous prompts.
- Compute item statistics (p-value, discrimination, distractor analysis).

## Data collection
- Collect response logs: learner_id, atom_id, timestamp, response, correctness, context metadata.
- Sample size: target >= 200 responses per item for stable p-value estimates (domain-dependent).

## Analyses
- p-value (item difficulty): proportion correct.
- Point-biserial correlation (discrimination): correlation of item correctness with total test score.
- Distractor analysis: frequency of selection per incorrect option; flag distractors selected > 20% among incorrect responders.

## Procedures
1. Run an item analysis script on the ingestion logs to compute statistics.
2. Flag items with p < 0.1 or p > 0.95 for review.
3. Flag items with negative discrimination for revision.
4. Review distractor texts for clarity and modality biases.

## Tools
- Use `scripts/analyze_item_quality.py` to produce CSV reports and suggested revisions.
- Visualize distributions using Jupyter and seaborn for exploratory analysis.

## Example metrics output
| atom_id | p_value | discrimination | flagged_distractor |
|---------|---------|----------------|--------------------|
| atom:mcq:0001 | 0.82 | 0.34 | None |
| atom:cloze:0032 | 0.12 | -0.02 | distractor B |

## Recommendations
- For items with negative discrimination, rewrite stem or review scoring rules.
- For ambiguous items, collect qualitative feedback from 5-10 subject-matter experts.
- Maintain an item lifecycle (draft -> pilot -> research -> production) and track status via metadata.

---

This guide assumes you have access to response logs and basic data analysis tooling. If you'd like, I can scaffold `scripts/analyze_item_quality.py` to compute p-values and discrimination metrics.
