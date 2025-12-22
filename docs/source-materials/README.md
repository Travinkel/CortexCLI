# Source Materials

This folder stores raw and curated inputs for the ETL pipeline. Organize items by intent (curriculum, textbooks, reference, curated) and keep provenance in the manifest.

## Structure
- curriculum/: Course syllabi, modules, exams, and learning objectives organized by domain.
- textbooks/: Authoritative books and chapters used as technical base sources.
- reference/: RFCs, cheatsheets, and standards used for exact technical truth.
- curated/: Hand-picked artifacts like exam keys, lab traces, and high-value snippets.
- legacy/: Archived or unclassified sources awaiting triage.
- manifest.csv: Inventory of all files with domain/type/status metadata.

## Conventions
- Keep filenames as-is unless a rename clarifies scope.
- Store multi-part items in a folder (for example, `curriculum/ccna/modules`).
- Update manifest.csv whenever files move or new sources are added.

## Intake Checklist
1. Place files in the correct domain folder.
2. Update manifest.csv (domain, source_type, status).
3. Add a short note in manifest.csv for provenance or licensing.
