# How to Implement a New Atom Type

This guide walks through the steps to add a new atom type: handler, schema, tests, and documentation.

## 1. Add the JSON schema
Create a new schema under `src/schemas/` following the Atom Envelope v2 spec. Include `ui_hint`, `difficulty`, and `skill_links`.

Example filename: `src/schemas/atom_visual_hotspot.json`

## 2. Implement the handler
Add a new handler in `src/handlers/` named after the atom type. Handlers should export two functions:
- `validate(payload) -> (bool, errors)`
- `grade(payload, response) -> result` (structured result: correct:bool, score:float, feedback:str)

Example: `src/handlers/visual_hotspot.py`

## 3. Add unit tests
- Validation tests for schema conformance.
- Grading tests for edge cases (off-by-one coordinates, partial credit)
- Integration test: mock an ingestion flow and ensure atom appears in canonical DB tables.

## 4. Documentation
- Add a page in `docs/reference/` describing the atom type (UI examples and payload fields). Use `docs/reference/atom-taxonomy-v2.md` as the canonical taxonomy.

## 5. Add sample content
Add a sample JSON atom under `data/exports/` for manual QA and integration tests.

## 6. CI
- Add test cases to `pytest` suite.
- Add validation checks in the `cortex validate` pipeline.

## Implementation checklist
- [ ] Schema file added and referenced
- [ ] Handler implemented and registered
- [ ] Unit tests added (validation + grading)
- [ ] Sample data added in `data/exports/`
- [ ] Docs updated in `docs/reference/` and `README.md`

---

If you'd like, I can scaffold a concrete example (schema + handler + tests) for `visual_hotspot` and commit it to `batch-5b-documentation` branch.
