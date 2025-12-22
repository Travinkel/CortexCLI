# ResearchEngine Bridge

## Purpose
Define how ResearchEngine evidence guides ETL transforms without replacing the technical base. The technical base supplies factual content; ResearchEngine supplies instructional strategy.

## Integration Points
- Evidence lookup: map content segments to evidence IDs for retrieval practice, sequencing, contrastive examples, and misconception handling.
- Atom selection: use evidence to select ICAP level and atom type (for example, ordering for procedures, contrastive for trade-offs).
- Misconception mapping: tag generated atoms with misconception IDs when evidence points to common errors.

## Minimal Data Contract
Each generated atom should include:
- evidence_id: ResearchEngine evidence record used to justify the instructional strategy.
- strategy: High-level strategy label (retrieval, elaboration, contrastive, error-spotting).
- atom_type: Concrete atom template applied.
- rationale: Short explanation linking evidence to atom choice.

## Extraction Strategy Guidance
- Prefer sources with procedural steps, error states, and contrastive examples.
- Treat syllabi as topic maps, not source-of-truth content.
- Use technical references (RFCs, official docs) to ground factual correctness.
