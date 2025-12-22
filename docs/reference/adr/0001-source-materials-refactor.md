# ADR 0001: Refactor Source Materials Layout

## Status
Accepted

## Context
The source-materials directory accumulated mixed inputs (modules, exams, books, and reference docs) without consistent structure. This made ETL ingestion and provenance tracking inconsistent and slowed curation.

## Decision
Introduce a standardized layout under docs/source-materials with these top-level buckets:
- curriculum/
- textbooks/
- reference/
- curated/
- legacy/

Add a manifest.csv inventory to track domain, source type, and status for every file.

## Consequences
- ETL pipelines can target specific buckets (curriculum vs. technical base) without manual filtering.
- New materials must be registered in manifest.csv and placed in a predictable folder.
- Legacy inputs remain accessible while being staged for triage.
