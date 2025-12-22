# Greenlight Handoff v2

This document specifies the updated handoff protocol between cortex-cli and Greenlight for runtime atoms that require IDE/editor capabilities.

## Overview
Greenlight handles atoms that require code execution, diffs, or IDE integrations. cortex-cli will route complex atoms to Greenlight via a handoff API and render a simplified result in the terminal.

## API: POST /greenlight/handoff
Request body:
```json
{
  "atom_id": "atom:code_eval:v1:0001",
  "learner_id": "user:123",
  "context": {"repo": "owner/repo", "path": "src/main.py", "branch": "feature/x"},
  "payload": { /* atom payload */ }
}
```

Response:
```json
{
  "handoff_id": "ghandoff:0001",
  "status": "queued",
  "estimated_wait_seconds": 12
}
```

## Webhook: POST /greenlight/handoff/{id}/result
Greenlight will POST results to a callback URL provided during the handoff registration or via an agreed webhook.

Result body example:
```json
{
  "handoff_id": "ghandoff:0001",
  "status": "completed",
  "result": {
    "score": 0.8,
    "details": { "stdout": "...", "stderr": "...", "diff": "..." }
  }
}
```

## Error handling
- 429: rate limited — implement exponential backoff (start 1s, max 1m)
- 500: server error — retry with backoff up to 3 times
- 400: invalid payload — return error to user and log for content owner

## Security
- Use mutual TLS or signed JWT tokens between services.
- Validate payload sizes and enforce limits on attachments.

## Implementation notes
- Provide a `greenlight` client library in `src/clients/greenlight.py` with methods: `handoff(atom, context)`, `get_status(handoff_id)`, `register_webhook(url)`.
- Use idempotency keys for handoffs to avoid duplicate processing.

---

This specification is a concise v2; expand with example code snippets, client usage, and error-case walkthroughs as needed.
