# SharedKernel Architecture

## Overview

SharedKernel is the monorepo containing shared infrastructure for all Astartes products. It provides reusable components that multiple products depend on, avoiding code duplication and ensuring consistency.

**Location:** `E:\Repo\project-astartes\SharedKernel\`

## Components

```
SharedKernel/
├── AstartesAgents/       # Agent orchestration & supervision
├── KnowledgeBase/        # Evidence storage, API, schemas
├── MCP/                  # Model Context Protocol servers
├── ResearchEngine/       # Systematic review & lifting pipelines
└── ContentExtractor/     # Technical content parsing (Batch 9)
```

### Component Responsibilities

| Component | Responsibility | Consumers |
|-----------|---------------|-----------|
| **AstartesAgents** | Agent lifecycle, task routing, supervision | All AI-powered features |
| **KnowledgeBase** | Evidence storage, search, validation | CortexCLI, RigorHub, ResearchEngine |
| **MCP** | Model Context Protocol servers | Claude Code, AI agents |
| **ResearchEngine** | Audit, review, lifting pipelines | KnowledgeBase (write path) |
| **ContentExtractor** | PDF/TXT/MD parsing, classification | CortexCLI, ResearchEngine, RigorHub |

## Dependency Graph

```
                    ┌─────────────────────────────────────┐
                    │           PRODUCTS                   │
                    ├─────────────────────────────────────┤
                    │  CortexCLI    RigorHub    Future    │
                    └───────┬─────────┬───────────┬───────┘
                            │         │           │
                            ▼         ▼           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         SHARED KERNEL                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │ ContentExtractor │    │  KnowledgeBase   │    │ AstartesAgents│  │
│  │                  │    │                  │    │               │  │
│  │ - PDFExtractor   │    │ - Evidence API   │    │ - Supervisor  │  │
│  │ - TXTExtractor   │    │ - Search         │    │ - Task Router │  │
│  │ - Classifier     │    │ - Validation     │    │ - Lifecycle   │  │
│  └────────┬─────────┘    └────────┬─────────┘    └───────────────┘  │
│           │                       │                                  │
│           │         ┌─────────────┴─────────────┐                   │
│           │         │                           │                   │
│           ▼         ▼                           ▼                   │
│  ┌──────────────────────────────┐    ┌──────────────────────────┐  │
│  │      ResearchEngine          │    │          MCP             │  │
│  │                              │    │                          │  │
│  │ - Systematic Review          │    │ - kb.search              │  │
│  │ - Pedagogical Audit          │    │ - kb.item                │  │
│  │ - Content Lifting            │    │ - kb.edges               │  │
│  │ - Master Ledger (write)      │    │ - (read-only interface)  │  │
│  └──────────────────────────────┘    └──────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Read/Write Paths

### Write Path (ResearchEngine only)

```
ContentExtractor → ResearchEngine → Master Ledger
     (parse)          (audit/lift)     (PostgreSQL)
```

Only ResearchEngine can write to the Master Ledger. This ensures:
- Single source of truth
- Cochrane-class audit trail
- Consistent provenance tracking

### Read Path (All products)

```
Products → KnowledgeBase API/MCP → Master Ledger
              (read-only)            (PostgreSQL)
```

All products consume evidence via read-only API or MCP.

## Package Structure

Each component is an installable Python package:

| Component | Package Name | Install |
|-----------|--------------|---------|
| ContentExtractor | `astartes-content-extractor` | `pip install -e SharedKernel/ContentExtractor` |
| KnowledgeBase | `astartes-knowledge-base` | `pip install -e SharedKernel/KnowledgeBase` |
| ResearchEngine | `astartes-research-engine` | `pip install -e SharedKernel/ResearchEngine` |

## Usage in Products

### CortexCLI

```python
# Content extraction
from astartes_content_extractor import PDFExtractor, GeminiClassifier
from astartes_content_extractor.models import RawChunk

# Knowledge Base access
from astartes_knowledge_base import KBClient
```

### RigorHub

```python
# Document processing
from astartes_content_extractor import extract_and_classify

# Evidence display
from astartes_knowledge_base import search_evidence
```

### ResearchEngine

```python
# Internal - same repo
from .services.lifting import LiftingPipeline
from .services.audit import PedagogicalAudit
```

## Development Workflow

### Adding a New Component

1. Create directory in SharedKernel
2. Add `pyproject.toml` with package config
3. Implement with clear API
4. Add tests
5. Document in this file

### Updating Existing Component

1. Make changes in SharedKernel
2. Run component tests
3. Run integration tests in consuming products
4. Version bump if breaking changes

### Local Development

```bash
# Install all SharedKernel components in dev mode
cd E:/Repo/project-astartes/SharedKernel
pip install -e ContentExtractor/
pip install -e KnowledgeBase/
pip install -e ResearchEngine/

# Now products can import
cd E:/Repo/cortex-cli
python -c "from astartes_content_extractor import PDFExtractor; print('OK')"
```

## Related Documents

- [Knowledge Integration Architecture](knowledge-integration.md)
- [Batch 9: SharedKernel Extractor](../agile/batch-9-shared-kernel-extractor.md)
- [Batch 8a: KB Ledger Upgrade](../agile/batch-8a-kb-ledger.md)
- [Batch 8b: KB Consumer](../agile/batch-8b-kb-consumer.md)
