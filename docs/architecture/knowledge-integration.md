# Knowledge Integration Architecture

## Overview

This document describes the architecture for integrating CortexCLI with the Master Knowledge Ledger in ResearchEngine. The design follows a strict separation of concerns: **ResearchEngine owns writes**, **CortexCLI reads only**.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              ASTARTES ECOSYSTEM                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                    RESEARCH ENGINE (Write Path)                            │  │
│  │                    E:\Repo\project-astartes\ResearchEngine                 │  │
│  ├───────────────────────────────────────────────────────────────────────────┤  │
│  │                                                                            │  │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌────────────┐  │  │
│  │  │ SYSTEMATIC  │    │ PEDAGOGICAL │    │ CONTENT     │    │ CLEAN ATOM │  │  │
│  │  │ REVIEW      │───►│ AUDIT       │───►│ LIFTING     │───►│ GENERATION │  │  │
│  │  │             │    │             │    │             │    │            │  │  │
│  │  └─────────────┘    └─────────────┘    └─────────────┘    └────────────┘  │  │
│  │         │                  │                  │                  │         │  │
│  │         ▼                  ▼                  ▼                  ▼         │  │
│  │  ┌─────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    MASTER KNOWLEDGE LEDGER                          │  │  │
│  │  │                    (PostgreSQL - Port 5432)                         │  │  │
│  │  ├─────────────────────────────────────────────────────────────────────┤  │  │
│  │  │                                                                      │  │  │
│  │  │  knowledge_items ◄──── knowledge_edges ────► knowledge_items        │  │  │
│  │  │        │                                            │                │  │  │
│  │  │        ▼                                            ▼                │  │  │
│  │  │  ┌──────────────────────────────────────────────────────────────┐   │  │  │
│  │  │  │ tech_sources ──► tech_nodes ──► knowledge_bridge ──► clean_atoms│ │  │  │
│  │  │  │ (books/docs)    (sections)      (evidence links)    (atoms)     │ │  │  │
│  │  │  └──────────────────────────────────────────────────────────────┘   │  │  │
│  │  │                                                                      │  │  │
│  │  └─────────────────────────────────────────────────────────────────────┘  │  │
│  │                                    │                                       │  │
│  │                                    │ (read-only)                           │  │
│  │                                    ▼                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    KNOWLEDGE BASE API + MCP                         │  │  │
│  │  │                    (HTTP: 8000, MCP: 8001)                          │  │  │
│  │  └─────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                            │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                       │                                          │
│                                       │ (read-only queries)                      │
│                                       ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                    CORTEX CLI (Read Path)                                  │  │
│  │                    E:\Repo\cortex-cli                                      │  │
│  ├───────────────────────────────────────────────────────────────────────────┤  │
│  │                                                                            │  │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌────────────┐  │  │
│  │  │ TECHNICAL   │    │ CONTENT     │    │ KB          │    │ LOCAL ATOM │  │  │
│  │  │ EXTRACTOR   │───►│ CLASSIFIER  │───►│ ENRICHMENT  │───►│ STORAGE    │  │  │
│  │  │ (PDF/TXT)   │    │ (Gemini)    │    │ (Evidence)  │    │            │  │  │
│  │  └─────────────┘    └─────────────┘    └─────────────┘    └────────────┘  │  │
│  │                                                                            │  │
│  │  CLI Commands:                                                             │  │
│  │  - nls content ingest --source <path>                                      │  │
│  │  - nls content enrich --domain <domain>                                    │  │
│  │  - nls content status                                                      │  │
│  │                                                                            │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                    RIGOR HUB (Web UI)                                      │  │
│  │                    Consumes KB API for evidence display                    │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Write Path (ResearchEngine Only)

```
1. INGEST
   tech_sources ← Upload PDF/book metadata (content_hash, license, quality_tier)

2. PARSE
   tech_nodes ← Extract chapters/sections/paragraphs with offsets

3. AUDIT
   knowledge_bridge ← Compute pedagogical_deficit_score, risk_of_bias_score

4. REVIEW
   knowledge_bridge ← Link tech_nodes to knowledge_items via edge traversal

5. LIFT
   clean_atoms ← Generate ICAP-classified atoms with full provenance
```

### Read Path (CortexCLI + RigorHub)

```
1. QUERY
   KB API/MCP ← Search for evidence by concept/topic

2. ENRICH
   Local atoms ← Add evidence_id, justification_science_ref

3. STORE
   local_atoms table ← Store with provenance (source_file, offsets)

4. SERVE
   Study sessions ← Present enriched atoms to learner
```

## Database Schema

### Master Ledger (ResearchEngine)

```sql
-- Technical sources (books, documents)
CREATE TABLE tech_sources (
    id UUID PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content_hash VARCHAR(64) UNIQUE,
    source_version VARCHAR(50),
    license VARCHAR(100),
    quality_tier INTEGER DEFAULT 2,  -- 1=Elite, 2=Standard, 3=Reference
    source_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Pedagogical units (chapters, sections, paragraphs)
CREATE TABLE tech_nodes (
    id UUID PRIMARY KEY,
    tech_source_id UUID REFERENCES tech_sources(id),
    node_type VARCHAR(50),  -- chapter, section, paragraph, code_block
    title VARCHAR(500),
    content_text TEXT,
    content_hash VARCHAR(64),
    offsets JSONB,  -- {start: int, end: int, page: int}
    parent_node_id UUID REFERENCES tech_nodes(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Cochrane-style evidence bridge
CREATE TABLE knowledge_bridge (
    id UUID PRIMARY KEY,
    tech_node_id UUID REFERENCES tech_nodes(id),
    knowledge_item_id UUID REFERENCES knowledge_items(id),
    pedagogical_deficit_score FLOAT DEFAULT 0.0,
    risk_of_bias_score FLOAT DEFAULT 0.0,
    suggested_atom_types JSONB,  -- ["parsons", "flashcard", "mcq"]
    synthesis_notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Generated learning atoms
CREATE TABLE clean_atoms (
    id UUID PRIMARY KEY,
    knowledge_bridge_id UUID REFERENCES knowledge_bridge(id),
    knowledge_item_id UUID REFERENCES knowledge_items(id),  -- Direct FK
    content JSONB NOT NULL,
    grading_logic JSONB NOT NULL,
    atom_type VARCHAR(50) NOT NULL,
    icap_level VARCHAR(20) NOT NULL,  -- passive, active, constructive, interactive
    lifting_model_version VARCHAR(50),
    provenance_tech_ref UUID REFERENCES tech_nodes(id),
    justification_science_ref VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Local Storage (CortexCLI)

```sql
-- Locally generated/enriched atoms
CREATE TABLE local_atoms (
    id UUID PRIMARY KEY,
    content JSONB NOT NULL,
    grading_logic JSONB NOT NULL,
    atom_type VARCHAR(50) NOT NULL,
    domain VARCHAR(50) NOT NULL,
    icap_level VARCHAR(20) NOT NULL,

    -- Provenance (always required)
    provenance_tech_ref VARCHAR(255) NOT NULL,
    source_file VARCHAR(500),
    source_offsets JSONB,

    -- Evidence (populated by enrichment)
    evidence_id UUID,
    justification_science_ref VARCHAR(500),
    enrichment_confidence FLOAT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);
```

## API Contracts

### KnowledgeBase API (HTTP)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/kb/search` | GET | Search knowledge items |
| `/api/kb/items/{id}` | GET | Get item by ID |
| `/api/kb/items/ref/{reference}` | GET | Get item by citation |
| `/api/kb/edges/{id}` | GET | Get edges for item |
| `/api/kb/rag` | POST | Get RAG context |
| `/api/kb/atoms` | GET | Get clean atoms |
| `/api/kb/audit/status` | GET | Get audit metrics |

### KnowledgeBase MCP Tools

| Tool | Parameters | Returns |
|------|------------|---------|
| `kb.search` | query, domain, limit | List[KnowledgeItem] |
| `kb.item` | item_id | KnowledgeItem |
| `kb.item_by_reference` | reference | KnowledgeItem |
| `kb.edges` | item_id, edge_type | List[KnowledgeEdge] |
| `kb.rag_context` | query, max_tokens | str |
| `kb.clean_atoms` | domain, limit | List[CleanAtom] |
| `kb.audit_status` | domain | AuditStatus |
| `kb.health` | - | HealthStatus |

## Key Principles

### 1. Postgres-First

The database is the source of truth. All other services (API, MCP, agents) are read-only views.

### 2. Write Isolation

Only ResearchEngine pipelines write to the Master Ledger. CortexCLI and RigorHub are read-only consumers.

### 3. Full Provenance

Every atom tracks:
- **provenance_tech_ref**: Which tech_node it came from
- **justification_science_ref**: Which knowledge_item validates it
- **evidence_id**: Direct link for audit queries

### 4. Cochrane Standards

- **Systematic Review**: Edge-aware evidence synthesis
- **Pedagogical Audit**: Expert blind spot detection
- **Risk of Bias**: Vendor/methodology bias scoring
- **Deficit Scoring**: Passive wall identification

### 5. ICAP Classification

All atoms are classified by engagement level:
- **Passive**: Reading, watching
- **Active**: Highlighting, note-taking
- **Constructive**: Explaining, generating
- **Interactive**: Discussing, collaborating

## Implementation Batches

| Batch | Repo | Scope |
|-------|------|-------|
| 8a: KB Ledger Upgrade | ResearchEngine | Schema, audit, review, lifting |
| 8b: KB Consumer | CortexCLI | Client, enrichment, CLI |
| 8c: MCP Registration | AstartesAgents | Supervisor, Docker, docs |

## Related Documents

- [Batch 8a: KB Ledger Upgrade](../agile/batch-8a-kb-ledger.md)
- [Batch 8b: KB Consumer](../agile/batch-8b-kb-consumer.md)
- [Batch 8c: MCP Registration](../agile/batch-8c-mcp-registration.md)
- [Batch 7: Technical Content Extractor](../agile/batch-7-content-extractor.md)
