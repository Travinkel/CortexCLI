# API Reference

Complete REST API documentation for notion-learning-sync.

## Base URL

```
http://localhost:8100
```

For production, replace with your deployment URL.

## Interactive Documentation

FastAPI provides automatic interactive documentation:

- **Swagger UI**: http://localhost:8100/docs
- **ReDoc**: http://localhost:8100/redoc
- **OpenAPI JSON**: http://localhost:8100/openapi.json

## Authentication

Currently, the API has no authentication (localhost only).

For production deployment, add authentication via:
- API keys (header: `X-API-Key`)
- OAuth2 / JWT tokens
- IP whitelist

## Common Response Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request parameters |
| 404 | Not Found | Resource not found |
| 422 | Unprocessable Entity | Validation error |
| 500 | Internal Server Error | Server error |

## Error Response Format

```json
{
  "detail": "Error message describing what went wrong",
  "error_code": "OPTIONAL_ERROR_CODE",
  "timestamp": "2025-12-01T10:30:00Z"
}
```

---

## Health & Status Endpoints

### GET /

Root endpoint returning service information.

**Response**:
```json
{
  "service": "notion-learning-sync",
  "version": "0.1.0",
  "status": "ok"
}
```

**Example**:
```bash
curl http://localhost:8100/
```

---

### GET /health

Comprehensive health check with component status.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-12-01T10:30:00.000Z",
  "components": {
    "database": "ok",
    "notion": "configured",
    "anki": "configured",
    "ai": "configured"
  },
  "config": {
    "protect_notion": true,
    "dry_run": false,
    "configured_databases": [
      "flashcards",
      "concepts",
      "concept_areas",
      "concept_clusters",
      "modules",
      "tracks",
      "programs"
    ]
  }
}
```

**Component Status Values**:
- `ok` - Component is working
- `configured` - Component is configured but not tested
- `not_configured` - Component needs configuration
- `error` - Component has errors

**Example**:
```bash
curl http://localhost:8100/health
```

---

### GET /config

Get current configuration (non-sensitive values only).

**Response**:
```json
{
  "database_url": "localhost:5432/notion_learning_sync",
  "notion": {
    "configured": true,
    "databases": {
      "flashcards": "abc123...",
      "concepts": "def456...",
      "concept_areas": "ghi789...",
      "concept_clusters": "jkl012...",
      "modules": "mno345...",
      "tracks": "pqr678...",
      "programs": "stu901..."
    }
  },
  "anki": {
    "connect_url": "http://127.0.0.1:8765",
    "deck_name": "LearningOS::Synced",
    "note_type": "Basic"
  },
  "ai": {
    "gemini_configured": true,
    "vertex_configured": false,
    "model": "gemini-2.0-flash"
  },
  "atomicity": {
    "front_max_words": 25,
    "back_optimal_words": 5,
    "back_warning_words": 15,
    "back_max_chars": 120,
    "mode": "relaxed"
  },
  "sync": {
    "interval_minutes": 120,
    "protect_notion": true,
    "dry_run": false
  }
}
```

**Example**:
```bash
curl http://localhost:8100/config
```

---

## Sync Endpoints

### POST /api/sync/notion

**(Future Implementation)**

Perform a full sync from all configured Notion databases.

**Request Body**: None required

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dry_run` | boolean | false | Log actions without making changes |
| `force` | boolean | false | Re-sync even if unchanged |

**Response**:
```json
{
  "sync_id": "uuid",
  "started_at": "2025-12-01T10:30:00Z",
  "status": "completed",
  "duration_seconds": 45.2,
  "results": {
    "flashcards": {
      "processed": 1250,
      "added": 50,
      "updated": 30,
      "unchanged": 1170
    },
    "concepts": {
      "processed": 150,
      "added": 5,
      "updated": 10,
      "unchanged": 135
    },
    "concept_areas": {
      "processed": 8,
      "added": 0,
      "updated": 1,
      "unchanged": 7
    },
    "concept_clusters": {
      "processed": 45,
      "added": 2,
      "updated": 3,
      "unchanged": 40
    },
    "modules": {
      "processed": 24,
      "added": 0,
      "updated": 2,
      "unchanged": 22
    },
    "tracks": {
      "processed": 6,
      "added": 0,
      "updated": 0,
      "unchanged": 6
    },
    "programs": {
      "processed": 2,
      "added": 0,
      "updated": 0,
      "unchanged": 2
    }
  },
  "errors": []
}
```

**Example**:
```bash
curl -X POST http://localhost:8100/api/sync/notion

# With dry run
curl -X POST "http://localhost:8100/api/sync/notion?dry_run=true"
```

---

### POST /api/sync/notion/incremental

**(Future Implementation)**

Perform an incremental sync (only changed items since last sync).

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `since` | datetime | last_synced_at | Sync items modified after this time |

**Response**: Same format as full sync

**Example**:
```bash
curl -X POST http://localhost:8100/api/sync/notion/incremental

# Custom time window
curl -X POST "http://localhost:8100/api/sync/notion/incremental?since=2025-12-01T00:00:00Z"
```

---

### GET /api/sync/status

**(Future Implementation)**

Get the status of the last sync operation.

**Response**:
```json
{
  "last_sync": {
    "sync_id": "uuid",
    "sync_type": "notion_full",
    "started_at": "2025-12-01T10:30:00Z",
    "completed_at": "2025-12-01T10:31:15Z",
    "status": "completed",
    "items_processed": 1485,
    "items_added": 57,
    "items_updated": 46,
    "error_message": null
  },
  "next_scheduled_sync": "2025-12-01T12:30:00Z"
}
```

**Example**:
```bash
curl http://localhost:8100/api/sync/status
```

---

## Cleaning Pipeline Endpoints

### POST /api/clean/atomicity

**(Future Implementation)**

Run atomicity validation on all or filtered flashcards.

**Request Body**:
```json
{
  "mode": "relaxed",
  "filters": {
    "concept_id": "uuid",
    "module_id": "uuid",
    "card_ids": ["NET-M1-001", "NET-M1-002"]
  }
}
```

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | string | config | 'relaxed' or 'strict' |
| `dry_run` | boolean | false | Don't update database |

**Response**:
```json
{
  "checked": 1250,
  "atomic": 980,
  "verbose": 220,
  "needs_split": 50,
  "details": {
    "avg_front_words": 12.3,
    "avg_back_words": 8.5,
    "violations": [
      {
        "card_id": "NET-M1-015",
        "front_words": 32,
        "back_words": 45,
        "issues": [
          "Question too long (32 words)",
          "Answer verbose (45 words)"
        ]
      }
    ]
  }
}
```

**Example**:
```bash
curl -X POST http://localhost:8100/api/clean/atomicity \
  -H "Content-Type: application/json" \
  -d '{"mode": "strict"}'
```

---

### POST /api/clean/duplicates

**(Future Implementation)**

Detect duplicate or near-duplicate flashcards.

**Request Body**:
```json
{
  "similarity_threshold": 0.85,
  "method": "fuzzy",
  "auto_merge": false
}
```

**Parameters**:
- `similarity_threshold`: 0.0-1.0, higher = more strict (default: 0.85)
- `method`: `fuzzy` (rapidfuzz) or `semantic` (embeddings)
- `auto_merge`: Automatically merge duplicates (default: false)

**Response**:
```json
{
  "total_checked": 1250,
  "duplicates_found": 23,
  "groups": [
    {
      "group_id": 1,
      "similarity": 0.95,
      "cards": [
        {
          "card_id": "NET-M1-015",
          "front": "What is TCP?",
          "back": "Transmission Control Protocol"
        },
        {
          "card_id": "NET-M2-008",
          "front": "What does TCP stand for?",
          "back": "Transmission Control Protocol"
        }
      ],
      "suggested_merge": {
        "front": "What does TCP stand for?",
        "back": "Transmission Control Protocol",
        "reason": "Keep shorter, clearer question"
      }
    }
  ],
  "merged": 0
}
```

**Example**:
```bash
curl -X POST http://localhost:8100/api/clean/duplicates \
  -H "Content-Type: application/json" \
  -d '{"similarity_threshold": 0.90, "method": "fuzzy"}'
```

---

### POST /api/clean/ai-rewrite

**(Future Implementation)**

Use AI to rewrite verbose flashcards.

**Request Body**:
```json
{
  "filters": {
    "atomicity_status": "verbose",
    "min_word_count": 20
  },
  "limit": 50,
  "auto_approve": false
}
```

**Parameters**:
- `limit`: Max cards to rewrite in this batch
- `auto_approve`: Automatically approve high-confidence rewrites (>0.9)

**Response**:
```json
{
  "batch_id": "uuid",
  "processed": 50,
  "queued_for_review": 48,
  "auto_approved": 2,
  "examples": [
    {
      "card_id": "NET-M1-015",
      "original": {
        "front": "What is the Transmission Control Protocol and what are its main characteristics?",
        "back": "TCP is a connection-oriented protocol that provides reliable, ordered delivery of data..."
      },
      "rewritten": {
        "front": "What does TCP guarantee?",
        "back": "Reliable, ordered data delivery"
      },
      "confidence": 0.92,
      "reason": "Split complex question, shortened answer"
    }
  ]
}
```

**Example**:
```bash
curl -X POST http://localhost:8100/api/clean/ai-rewrite \
  -H "Content-Type: application/json" \
  -d '{"limit": 100, "auto_approve": false}'
```

---

## Review Queue Endpoints

### GET /api/review

**(Future Implementation)**

List items in the review queue.

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | pending | Filter by status |
| `source` | string | all | Filter by AI source |
| `limit` | int | 20 | Items per page |
| `offset` | int | 0 | Pagination offset |

**Response**:
```json
{
  "total": 150,
  "limit": 20,
  "offset": 0,
  "items": [
    {
      "id": "uuid",
      "created_at": "2025-12-01T10:30:00Z",
      "status": "pending",
      "source": "gemini",
      "original": {
        "front": "What is TCP and how does it work?",
        "back": "TCP is a connection-oriented protocol..."
      },
      "rewritten": {
        "front": "What protocol ensures reliable data delivery?",
        "back": "TCP (Transmission Control Protocol)"
      },
      "quality_score": 0.88,
      "ai_confidence": 0.92,
      "rewrite_reason": "Simplified question, shortened answer"
    }
  ]
}
```

**Example**:
```bash
curl "http://localhost:8100/api/review?status=pending&limit=10"
```

---

### POST /api/review/{id}/approve

**(Future Implementation)**

Approve a review queue item and create the clean atom.

**Path Parameters**:
- `id`: UUID of the review queue item

**Request Body** (optional):
```json
{
  "notes": "Looks good, approved",
  "edits": {
    "front": "Custom edited question",
    "back": "Custom edited answer"
  }
}
```

**Response**:
```json
{
  "review_id": "uuid",
  "approved_at": "2025-12-01T10:35:00Z",
  "created_atom_id": "uuid",
  "card_id": "NET-M1-015-DEC"
}
```

**Example**:
```bash
curl -X POST http://localhost:8100/api/review/abc-123-def-456/approve \
  -H "Content-Type: application/json" \
  -d '{"notes": "Approved with minor edit", "edits": {"back": "TCP"}}'
```

---

### POST /api/review/{id}/reject

**(Future Implementation)**

Reject a review queue item and keep the original.

**Request Body**:
```json
{
  "reason": "AI rewrite lost important context"
}
```

**Response**:
```json
{
  "review_id": "uuid",
  "rejected_at": "2025-12-01T10:35:00Z",
  "status": "rejected"
}
```

**Example**:
```bash
curl -X POST http://localhost:8100/api/review/abc-123-def-456/reject \
  -H "Content-Type: application/json" \
  -d '{"reason": "Rewrite was too aggressive"}'
```

---

## Anki Integration Endpoints

### POST /api/anki/push

**(Future Implementation)**

Push clean atoms to Anki.

**Request Body**:
```json
{
  "filters": {
    "concept_id": "uuid",
    "module_id": "uuid",
    "card_ids": ["NET-M1-001", "NET-M1-002"]
  },
  "deck_name": "LearningOS::Synced",
  "overwrite_existing": false
}
```

**Parameters**:
- `deck_name`: Override default deck from config
- `overwrite_existing`: Update existing Anki notes (default: false)

**Response**:
```json
{
  "pushed": 125,
  "updated": 30,
  "skipped": 15,
  "errors": [],
  "details": {
    "new_notes": 125,
    "updated_notes": 30,
    "failed": []
  }
}
```

**Example**:
```bash
curl -X POST http://localhost:8100/api/anki/push \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

### POST /api/anki/pull-stats

**(Future Implementation)**

Pull review statistics from Anki and update clean_atoms.

**Response**:
```json
{
  "updated": 980,
  "errors": [],
  "summary": {
    "avg_ease_factor": 2.35,
    "avg_interval_days": 45.2,
    "total_reviews": 15420,
    "total_lapses": 234
  }
}
```

**Example**:
```bash
curl -X POST http://localhost:8100/api/anki/pull-stats
```

---

### GET /api/anki/status

**(Future Implementation)**

Check AnkiConnect connectivity and deck status.

**Response**:
```json
{
  "anki_connect": {
    "available": true,
    "version": 6
  },
  "deck": {
    "name": "LearningOS::Synced",
    "exists": true,
    "card_count": 1250
  },
  "sync_stats": {
    "total_atoms": 1485,
    "in_anki": 1250,
    "pending_push": 235,
    "last_push": "2025-12-01T08:00:00Z",
    "last_pull": "2025-12-01T09:30:00Z"
  }
}
```

**Example**:
```bash
curl http://localhost:8100/api/anki/status
```

---

## Content Access Endpoints

### GET /api/atoms

**(Future Implementation)**

List clean atoms with filtering, sorting, and pagination.

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `concept_id` | UUID | | Filter by concept |
| `module_id` | UUID | | Filter by module |
| `is_atomic` | boolean | | Filter by atomicity |
| `needs_review` | boolean | | Filter by review status |
| `in_anki` | boolean | | Filter synced to Anki |
| `due_date` | date | | Filter by due date (<=) |
| `sort` | string | created_at | Sort field |
| `order` | string | desc | asc or desc |
| `limit` | int | 50 | Items per page |
| `offset` | int | 0 | Pagination offset |

**Response**:
```json
{
  "total": 1485,
  "limit": 50,
  "offset": 0,
  "items": [
    {
      "id": "uuid",
      "card_id": "NET-M1-015-DEC",
      "front": "What does TCP stand for?",
      "back": "Transmission Control Protocol",
      "concept": {
        "id": "uuid",
        "name": "TCP/IP Protocol Suite"
      },
      "module": {
        "id": "uuid",
        "name": "Week 3: Network Protocols"
      },
      "quality_score": 0.95,
      "is_atomic": true,
      "anki_ease_factor": 2.50,
      "anki_interval_days": 60,
      "anki_due_date": "2025-12-15"
    }
  ]
}
```

**Example**:
```bash
# Get all atoms for a concept
curl "http://localhost:8100/api/atoms?concept_id=abc-123-def-456&limit=100"

# Get due atoms
curl "http://localhost:8100/api/atoms?due_date=2025-12-01&in_anki=true"

# Get atoms needing review
curl "http://localhost:8100/api/atoms?needs_review=true"
```

---

### GET /api/concepts

**(Future Implementation)**

Get the knowledge hierarchy.

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_atoms` | boolean | false | Include atom counts |
| `status` | string | all | Filter by status |

**Response**:
```json
{
  "concept_areas": [
    {
      "id": "uuid",
      "name": "Computer Science",
      "clusters": [
        {
          "id": "uuid",
          "name": "Computer Networks",
          "concepts": [
            {
              "id": "uuid",
              "name": "TCP/IP Protocol Suite",
              "status": "active",
              "atom_count": 45
            }
          ]
        }
      ]
    }
  ]
}
```

**Example**:
```bash
curl "http://localhost:8100/api/concepts?include_atoms=true"
```

---

### GET /api/export/atoms

**(Future Implementation)**

Bulk export clean atoms for ETL or backup.

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format` | string | json | json or csv |
| `filters` | object | {} | Same as /api/atoms |

**Response** (JSON):
```json
{
  "exported_at": "2025-12-01T10:30:00Z",
  "count": 1485,
  "atoms": [...]
}
```

**Response** (CSV):
```csv
id,card_id,front,back,concept_name,module_name,quality_score,anki_ease_factor
uuid,NET-M1-015-DEC,"What does TCP stand for?","Transmission Control Protocol","TCP/IP Protocol Suite","Week 3: Network Protocols",0.95,2.50
```

**Example**:
```bash
# Export as JSON
curl "http://localhost:8100/api/export/atoms?format=json" > atoms.json

# Export as CSV
curl "http://localhost:8100/api/export/atoms?format=csv" > atoms.csv
```

---

## Rate Limiting

Currently, no rate limiting is implemented (localhost only).

For production:
- Implement rate limiting per IP or API key
- Suggested limits:
  - Sync operations: 10 per hour
  - Read operations: 1000 per hour
  - Write operations: 100 per hour

## CORS

CORS is enabled for all origins in development.

For production, restrict to specific origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

## Webhooks (Future)

Future support for webhooks to notify external systems:

```
POST /api/webhooks/subscribe
{
  "url": "https://yourdomain.com/webhook",
  "events": ["sync.completed", "atom.created", "review.pending"]
}
```

## Client Examples

### Python

```python
import requests

BASE_URL = "http://localhost:8100"

# Health check
response = requests.get(f"{BASE_URL}/health")
print(response.json())

# Trigger sync
response = requests.post(f"{BASE_URL}/api/sync/notion")
sync_result = response.json()

# Get due atoms
response = requests.get(
    f"{BASE_URL}/api/atoms",
    params={"due_date": "2025-12-01", "in_anki": True}
)
atoms = response.json()["items"]
```

### JavaScript

```javascript
const BASE_URL = 'http://localhost:8100';

// Health check
const health = await fetch(`${BASE_URL}/health`).then(r => r.json());
console.log(health);

// Trigger sync
const syncResult = await fetch(`${BASE_URL}/api/sync/notion`, {
  method: 'POST'
}).then(r => r.json());

// Get review queue
const reviews = await fetch(`${BASE_URL}/api/review?status=pending`)
  .then(r => r.json());
```

### cURL

```bash
# Health check
curl http://localhost:8100/health | jq

# Trigger sync with dry run
curl -X POST "http://localhost:8100/api/sync/notion?dry_run=true" | jq

# Approve review item
curl -X POST http://localhost:8100/api/review/abc-123/approve \
  -H "Content-Type: application/json" \
  -d '{"notes": "LGTM"}' | jq
```

## OpenAPI Schema

Download the full OpenAPI schema:

```bash
curl http://localhost:8100/openapi.json > openapi.json
```

Use with code generators:
- [openapi-generator](https://github.com/OpenAPITools/openapi-generator)
- [swagger-codegen](https://github.com/swagger-api/swagger-codegen)

Generate Python client:
```bash
openapi-generator-cli generate -i openapi.json -g python -o ./client
```

## Support

For API issues or feature requests, see the main documentation at [docs/index.md](index.md).
