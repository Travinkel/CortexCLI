# Batch 8c: MCP Server Registration

**Branch:** `batch-8c-mcp-registration`
**Repo:** `E:\Repo\project-astartes\AstartesAgents`
**Priority:** MEDIUM | **Effort:** 1 day | **Status:** Pending

## Overview

Register the KnowledgeBase MCP server with the AstartesAgents supervisor and create documentation for agent integration.

## Prerequisites

- Batch 8a (KB Ledger Upgrade) complete
- MCP server implemented in ResearchEngine

## MCP Server Tools

The KnowledgeBase MCP server exposes these read-only tools:

| Tool | Description | Parameters |
|------|-------------|------------|
| `kb.search` | Search knowledge items | query, domain, limit |
| `kb.item` | Get item by ID | item_id |
| `kb.item_by_reference` | Get item by citation | reference |
| `kb.edges` | Get edges for item | item_id, edge_type |
| `kb.rag_context` | Get RAG context | query, max_tokens |
| `kb.clean_atoms` | Get generated atoms | domain, limit |
| `kb.audit_status` | Get audit metrics | domain |

## Implementation

### 1. Supervisor Configuration

**File:** `config/supervisord.conf` (extend)

```ini
[program:kb-mcp]
command=python -m services.knowledge_base.mcp.server
directory=/app/ResearchEngine
autostart=true
autorestart=true
stderr_logfile=/var/log/kb-mcp.err.log
stdout_logfile=/var/log/kb-mcp.out.log
environment=
    DATABASE_URL="%(ENV_KB_DATABASE_URL)s",
    MCP_PORT="8001"
```

### 2. Docker Compose Service

**File:** `docker-compose.yml` (extend)

```yaml
services:
  kb-mcp:
    build:
      context: ../ResearchEngine
      dockerfile: Dockerfile.mcp
    ports:
      - "8001:8001"
    environment:
      - KB_DATABASE_URL=${KB_DATABASE_URL}
      - MCP_PORT=8001
    depends_on:
      - postgres
    networks:
      - astartes-net
    restart: unless-stopped
```

### 3. Agent Integration Guide

**File:** `docs/agents/kb-integration.md`

```markdown
# KnowledgeBase Agent Integration

## Overview

The KnowledgeBase MCP server provides read-only access to the Master Knowledge
Ledger for all Astartes agents.

## Connection

```python
from mcp import Client

kb = Client("http://kb-mcp:8001")
```

## Available Tools

### kb.search
Search for knowledge items by query.

```python
results = await kb.call("kb.search", {
    "query": "spaced repetition effectiveness",
    "domain": "learning_science",
    "limit": 10
})
```

### kb.item
Get a specific knowledge item.

```python
item = await kb.call("kb.item", {"item_id": "uuid-here"})
```

### kb.edges
Get related knowledge items via edges.

```python
edges = await kb.call("kb.edges", {
    "item_id": "uuid-here",
    "edge_type": "supports"  # or "refines", "contradicts", "prerequisite"
})
```

### kb.rag_context
Get formatted context for RAG prompts.

```python
context = await kb.call("kb.rag_context", {
    "query": "How to teach recursion effectively",
    "max_tokens": 2000
})
```

## Use Cases

### 1. Evidence-Based Atom Generation

```python
# Get evidence for a concept
evidence = await kb.call("kb.search", {
    "query": "parsons problems effectiveness",
    "domain": "cs_education"
})

# Use evidence to inform atom generation
atom = generate_atom(
    content=raw_content,
    evidence_id=evidence[0]["id"],
    justification=evidence[0]["reference"]
)
```

### 2. Audit Query

```python
# Check pedagogical audit status
status = await kb.call("kb.audit_status", {"domain": "networking"})
print(f"High deficit nodes: {status['high_deficit_count']}")
print(f"Pending lifts: {status['pending_lifts']}")
```

## Important Notes

- All tools are READ-ONLY
- Writes happen only through ResearchEngine pipelines
- Cache responses when possible (TTL: 1 hour recommended)
- Rate limit: 100 requests/minute per agent
```

### 4. Health Check Endpoint

**File:** `services/knowledge_base/mcp/server.py` (extend)

```python
@mcp.tool("kb.health")
async def health_check() -> dict:
    """Check MCP server health and DB connection."""
    return {
        "status": "healthy",
        "db_connected": await check_db_connection(),
        "version": "1.0.0",
        "tools_available": list(mcp.tools.keys())
    }
```

## Files to Create/Modify

### In AstartesAgents

| File | Purpose |
|------|---------|
| `config/supervisord.conf` | Add kb-mcp program |
| `docker-compose.yml` | Add kb-mcp service |
| `docs/agents/kb-integration.md` | Agent integration guide |

### In ResearchEngine

| File | Purpose |
|------|---------|
| `Dockerfile.mcp` | MCP server container |
| `services/knowledge_base/mcp/server.py` | Add health check |

## Commit Strategy

```bash
# AstartesAgents
cd E:/Repo/project-astartes/AstartesAgents
git checkout -b batch-8c-mcp-registration

git add config/supervisord.conf docker-compose.yml
git commit -m "feat(batch8c): Add KnowledgeBase MCP to supervisor"

git add docs/agents/kb-integration.md
git commit -m "docs(batch8c): Add KB agent integration guide"

git push -u origin batch-8c-mcp-registration

# ResearchEngine
cd E:/Repo/project-astartes/ResearchEngine
git checkout -b batch-8c-mcp-registration

git add Dockerfile.mcp services/knowledge_base/mcp/server.py
git commit -m "feat(batch8c): Add MCP health check and Dockerfile"

git push -u origin batch-8c-mcp-registration
```

## Success Criteria

- [ ] MCP server starts via supervisor
- [ ] Docker compose includes kb-mcp service
- [ ] Health check returns valid response
- [ ] Agent integration docs are complete
- [ ] Rate limiting configured

## Testing

```bash
# Test MCP server locally
python -m services.knowledge_base.mcp.server

# Test health check
curl http://localhost:8001/health

# Test from agent
python -c "
from mcp import Client
kb = Client('http://localhost:8001')
print(kb.call('kb.health'))
"
```

---

**Reference:** Wave 5 Knowledge Integration | **Depends On:** Batch 8a
