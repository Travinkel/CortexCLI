# API Endpoints Reference

REST API specification for Cortex.

---

## Overview

| Item | Value |
|------|-------|
| Base URL | `http://localhost:8100` |
| Protocol | HTTP/1.1 |
| Content Type | `application/json` |
| Authentication | None (localhost only) |

### Interactive Documentation

- Swagger UI: [http://localhost:8100/docs](http://localhost:8100/docs)
- ReDoc: [http://localhost:8100/redoc](http://localhost:8100/redoc)
- OpenAPI JSON: [http://localhost:8100/openapi.json](http://localhost:8100/openapi.json)

---

## Greenlight Handoff (conceptual contract)

Purpose: cortex-cli can delegate runtime/IDE atoms to Greenlight and receive a graded result.

See `docs/reference/atom-envelope.schema.json` for the shared envelope and `docs/reference/greenlight-handoff.openapi.yaml` for the OpenAPI draft.

### Request

```
POST /greenlight/run-atom
{
  "atom_id": "uuid",
  "owner": "greenlight",
  "grading_mode": "runtime",
  "atom_type": "code_submission" | "debugging" | "diff_review" | "cli_task",
  "runner": {
    "language": "python",
    "entrypoint": "main.py",
    "tests": "tests/test_main.py",
    "time_limit_ms": 3000,
    "memory_limit_mb": 256,
    "sandbox_policy": "isolated"
  },
  "diff_context": {
    "base_path": "src/",
    "patch": "...",
    "review_rubric": ["passes tests", "matches spec", "minimal change"]
  },
  "meta_wrappers": {
    "collect_confidence": true,
    "collect_difficulty": true,
    "allow_self_correction": true,
    "error_tagging": true
  }
}
```

### Response

```
{
  "atom_id": "uuid",
  "correct": true,
  "partial_score": 0.8,
  "feedback": "Tests 1-4 passed; fix off-by-one in edge case.",
  "test_results": {
    "passed": ["test_basic", "test_perf"],
    "failed": ["test_edge"],
    "logs": "...",
    "stdout": "...",
    "stderr": "..."
  },
  "diff_suggestion": null,
  "git_suggestions": ["git switch -c fix-edge", "git add -p", "git commit -m 'Fix edge case'"],
  "meta": {
    "confidence": 3,
    "difficulty": 4,
    "error_tag": "off_by_one"
  }
}
```

Notes:
- `owner`/`grading_mode`/`runner` fields align with the shared atom schema (see `docs/reference/learning-atoms.md`).
- cortex-cli may present the returned result in the terminal; Greenlight provides the full IDE UX when invoked directly.

---

## Response Codes

| Code | Meaning |
|------|---------|
| 200 | OK |
| 201 | Created |
| 400 | Bad Request |
| 404 | Not Found |
| 422 | Validation Error |
| 500 | Internal Server Error |

### Error Format

```json
{
  "detail": "Error message",
  "error_code": "OPTIONAL_CODE",
  "timestamp": "2025-12-09T10:30:00Z"
}
```

---

## Health & Status

### GET /

Root endpoint.

**Response**:
```json
{
  "service": "notion-learning-sync",
  "version": "0.1.0",
  "status": "ok"
}
```

### GET /health

Component health status.

**Response**:
```json
{
  "status": "healthy",
  "components": {
    "database": "ok",
    "notion": "configured",
    "anki": "configured"
  }
}
```

### GET /config

Current configuration (non-sensitive).

---

## Sync Endpoints

### POST /api/sync/notion

Full sync from Notion.

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dry_run` | boolean | false | Preview only |
| `force` | boolean | false | Re-sync unchanged |

**Response**:
```json
{
  "sync_id": "uuid",
  "status": "completed",
  "results": {
    "flashcards": {"added": 50, "updated": 30}
  }
}
```

### POST /api/sync/notion/incremental

Incremental sync (changed items only).

### GET /api/sync/status

Last sync operation status.

---

## Cleaning Endpoints

### POST /api/clean/atomicity

Run atomicity validation.

**Request**:
```json
{
  "mode": "relaxed",
  "filters": {"concept_id": "uuid"}
}
```

**Response**:
```json
{
  "checked": 1250,
  "atomic": 980,
  "verbose": 220,
  "needs_split": 50
}
```

### POST /api/clean/duplicates

Detect duplicates.

**Request**:
```json
{
  "similarity_threshold": 0.85,
  "method": "fuzzy"
}
```

### POST /api/clean/ai-rewrite

AI rewriting for verbose cards.

---

## Review Queue

### GET /api/review

List review queue items.

**Query Parameters**:

| Parameter | Type | Default |
|-----------|------|---------|
| `status` | string | pending |
| `limit` | int | 20 |
| `offset` | int | 0 |

### POST /api/review/{id}/approve

Approve a review item.

**Request** (optional):
```json
{
  "notes": "LGTM",
  "edits": {"front": "Custom question"}
}
```

### POST /api/review/{id}/reject

Reject a review item.

**Request**:
```json
{
  "reason": "Lost important context"
}
```

---

## Anki Endpoints

### POST /api/anki/push

Push atoms to Anki.

**Request**:
```json
{
  "filters": {"module_id": "uuid"},
  "deck_name": "CCNA::ITN"
}
```

**Response**:
```json
{
  "pushed": 125,
  "updated": 30,
  "skipped": 15
}
```

### POST /api/anki/pull-stats

Pull review stats from Anki.

### GET /api/anki/status

AnkiConnect status.

**Response**:
```json
{
  "anki_connect": {"available": true, "version": 6},
  "deck": {"name": "CCNA::ITN", "card_count": 1250},
  "sync_stats": {"pending_push": 235}
}
```

---

## Content Endpoints

### GET /api/atoms

List learning atoms.

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `concept_id` | UUID | Filter by concept |
| `module_id` | UUID | Filter by module |
| `is_atomic` | boolean | Filter by atomicity |
| `in_anki` | boolean | Filter synced to Anki |
| `due_date` | date | Filter by due date (<=) |
| `limit` | int | Items per page (default 50) |
| `offset` | int | Pagination offset |

**Response**:
```json
{
  "total": 1485,
  "items": [
    {
      "id": "uuid",
      "card_id": "NET-M1-015-DEC",
      "front": "What does TCP stand for?",
      "back": "Transmission Control Protocol",
      "quality_score": 0.95,
      "is_atomic": true
    }
  ]
}
```

### GET /api/concepts

Knowledge hierarchy.

### GET /api/export/atoms

Bulk export atoms.

**Query Parameters**:

| Parameter | Type | Default |
|-----------|------|---------|
| `format` | string | json |

Options: `json`, `csv`

---

## See Also

- [CLI Commands](cli-commands.md)
- [Configuration](configuration.md)
