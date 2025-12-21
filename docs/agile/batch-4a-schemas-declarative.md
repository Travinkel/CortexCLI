# Batch 4a: Declarative Memory Schemas

**Branch:** `batch-4a-schemas-declarative`
**Priority:** 🟢 MEDIUM | **Effort:** 1-2 days | **Status:** 🔴 Pending

## Objective

Create JSON Schema validation files for 12 declarative memory atom types.

## Atom Types (12)

1. flashcard
2. reverse_flashcard
3. image_to_term
4. audio_to_term
5. cloze_deletion
6. cloze_dropdown
7. cloze_bank
8. symbolic_cloze
9. short_answer_exact
10. short_answer_regex
11. list_recall
12. ordered_list_recall

## File Structure

```
docs/reference/atom-subschemas/
├── flashcard.schema.json
├── reverse_flashcard.schema.json
├── image_to_term.schema.json
├── audio_to_term.schema.json
├── cloze_deletion.schema.json
├── cloze_dropdown.schema.json
├── cloze_bank.schema.json
├── symbolic_cloze.schema.json
├── short_answer_exact.schema.json
├── short_answer_regex.schema.json
├── list_recall.schema.json
└── ordered_list_recall.schema.json
```

## Schema Template

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "<Atom Type>",
  "description": "<Description>",
  "type": "object",
  "required": ["<required fields>"],
  "properties": {
    "field_name": {
      "type": "string|number|array|object",
      "description": "<What this field does>",
      "minItems": <n>,  // for arrays
      "maxItems": <n>,  // for arrays
      "pattern": "<regex>",  // for strings
      "enum": ["<option1>", "<option2>"]  // for enums
    }
  }
}
```

## Example: cloze_dropdown.schema.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Cloze Dropdown Atom",
  "description": "Cloze deletion with dropdown selection (lower difficulty)",
  "type": "object",
  "required": ["cloze_text", "options", "correct_answer"],
  "properties": {
    "cloze_text": {
      "type": "string",
      "pattern": ".*\\{\\{c\\d+::[^}]+\\}\\}.*",
      "description": "Text with {{c1::answer}} placeholder"
    },
    "options": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 2,
      "maxItems": 6,
      "description": "Dropdown options (2-6 choices)"
    },
    "correct_answer": {
      "type": "string",
      "description": "Correct option (must be in options array)"
    },
    "case_sensitive": {
      "type": "boolean",
      "default": false
    }
  }
}
```

## Commit Strategy

```bash
# Create all 12 schema files
git add docs/reference/atom-subschemas/flashcard.schema.json
git add docs/reference/atom-subschemas/reverse_flashcard.schema.json
# ... (add all 12)

git commit -m "feat(batch4a): Add JSON schemas for 12 declarative memory atom types"
git push -u origin batch-4a-schemas-declarative
```

## Validation

Test each schema with example atom:

```python
import json
import jsonschema

schema = json.load(open("docs/reference/atom-subschemas/cloze_dropdown.schema.json"))
atom = {
    "cloze_text": "The OSI model has {{c1::seven}} layers.",
    "options": ["five", "seven", "nine"],
    "correct_answer": "seven"
}

jsonschema.validate(instance=atom, schema=schema)  # Should pass
```

## Reference

### Strategy Documents
- [BDD Testing Strategy](../explanation/bdd-testing-strategy.md) - Testing approach for cognitive validity
- [CI/CD Pipeline](../explanation/ci-cd-pipeline.md) - Automated quality gates and deployment
- [Atom Type Taxonomy](../reference/atom-type-taxonomy.md) - 100+ atom types with ICAP classification
- [Schema Migration Plan](../explanation/schema-migration-plan.md) - Migration to polymorphic JSONB atoms

### Work Orders

Plan lines 1084-1160 (Batch 4: JSONB Schema section)


---

**Status:** 🔴 Pending
