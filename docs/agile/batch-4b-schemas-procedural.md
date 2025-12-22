# Batch 4b: Procedural & Sequential Schemas

**Branch:** `batch-4b-schemas-procedural`
**Priority:** MEDIUM | **Effort:** 1-2 days | **Status:** Pending

## Atom Types (11)

parsons_problem, faded_parsons, distractor_parsons, 2d_parsons, timeline_ordering, process_flow, gantt_adjustment, circuit_routing, molecule_assembly, equation_balancing, sql_query_builder

## Directory

`docs/reference/atom-subschemas/` (11 files)

## Template Example: parsons_problem.schema.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Parsons Problem",
  "type": "object",
  "required": ["code_lines", "correct_order"],
  "properties": {
    "code_lines": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 3,
      "maxItems": 15
    },
    "correct_order": {
      "type": "array",
      "items": {"type": "integer"},
      "description": "Indices of code_lines in correct order"
    },
    "language": {
      "type": "string",
      "enum": ["python", "java", "javascript", "bash", "sql"]
    }
  }
}
```

## Commit

```bash
git add docs/reference/atom-subschemas/*.schema.json
git commit -m "feat(batch4b): Add JSON schemas for 11 procedural/sequential atom types"
git push -u origin batch-4b-schemas-procedural
```

---

**Reference:** Plan Batch 4 | **Status:** Pending
## testing and ci

- add or update tests relevant to this batch
- add or update bdd scenarios where applicable
- ensure pr-checks.yml passes before merge


