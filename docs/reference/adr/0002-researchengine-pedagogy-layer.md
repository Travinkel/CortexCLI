# ADR 0002: ResearchEngine Evidence as Pedagogical Layer

## Status
Accepted

## Context
The ETL pipeline needs a consistent way to translate technical content into high-quality learning atoms. ResearchEngine provides evidence-based guidance on instructional strategies, but the integration rules were not documented.

## Decision
Document ResearchEngine as the pedagogical layer that informs atom selection, difficulty modulation, and misconception handling. The technical base (textbooks, RFCs, labs) remains the source of factual truth; ResearchEngine supplies the instructional rationale.

## Consequences
- ETL transforms must reference ResearchEngine evidence IDs for atom justifications.
- Curriculum generation requires both technical base sources and research evidence to avoid hallucinated content.
- Future ingestion work should prioritize sources that include procedures, pitfalls, and examples to maximize evidence-driven atom variety.
