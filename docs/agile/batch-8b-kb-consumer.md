# Batch 8b: Knowledge Base Consumer

**Branch:** `batch-8b-kb-consumer`
**Repo:** `E:\Repo\cortex-cli`
**Priority:** HIGH | **Effort:** 2-3 days | **Status:** Pending

## Overview

Implement the "read path" for CortexCLI to consume evidence from the KnowledgeBase. This batch connects the Technical Content Extractor (Batch 7) to the Master Ledger (Batch 8a) via read-only API/MCP access.

## Prerequisites

- Batch 7 (Technical Content Extractor) complete ✅
- Batch 8a (KB Ledger Upgrade) complete
- KnowledgeBase API and MCP server running

> **SharedKernel Integration:** After [Batch 9](batch-9-shared-kernel-extractor.md) completes,
> the KB client should be considered for migration to `SharedKernel/KnowledgeBase/` so all
> Astartes products can use it. The extractors will already be in `SharedKernel/ContentExtractor/`.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CORTEX-CLI (Read-Only)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────┐     ┌─────────────────┐                        │
│  │ PDF/TXT         │     │ Gemini          │                        │
│  │ Extractor       │────►│ Classifier      │                        │
│  │ (Batch 7)       │     │ (Batch 7)       │                        │
│  └─────────────────┘     └────────┬────────┘                        │
│                                   │                                  │
│                                   ▼                                  │
│                    ┌───────────────────────────┐                    │
│                    │ KB CLIENT (NEW)           │                    │
│                    │ - MCP client adapter      │                    │
│                    │ - HTTP API fallback       │                    │
│                    │ - Evidence cache          │                    │
│                    └───────────────────────────┘                    │
│                                   │                                  │
│                                   ▼                                  │
│                    ┌───────────────────────────┐                    │
│                    │ ENRICHMENT TRANSFORMER    │                    │
│                    │ - Fetch evidence by topic │                    │
│                    │ - Select ICAP mode        │                    │
│                    │ - Apply grading strategy  │                    │
│                    └───────────────────────────┘                    │
│                                   │                                  │
│                                   ▼                                  │
│                    ┌───────────────────────────┐                    │
│                    │ LOCAL ATOM STORAGE        │                    │
│                    │ - provenance_tech_ref     │                    │
│                    │ - justification_science   │                    │
│                    │ - evidence_id             │                    │
│                    └───────────────────────────┘                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                              ▲
                              │ (read-only queries)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    RESEARCH ENGINE (Master Ledger)                   │
├─────────────────────────────────────────────────────────────────────┤
│  KnowledgeBase API (HTTP) ◄──── MCP Server (kb.* tools)             │
│  - /api/kb/search                kb.search                          │
│  - /api/kb/items/{id}            kb.item                            │
│  - /api/kb/edges/{id}            kb.edges                           │
│  - /api/kb/rag                   kb.rag_context                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Implementation

### 1. MCP Client Adapter

**File:** `src/clients/kb_client.py`

```python
from dataclasses import dataclass
from typing import Optional, List
import httpx

@dataclass
class KBConfig:
    api_url: str = "http://localhost:8000/api/kb"
    mcp_url: Optional[str] = None
    cache_ttl: int = 3600  # 1 hour

class KnowledgeBaseClient:
    """
    Read-only client for KnowledgeBase API/MCP.

    Provides:
    - Evidence search by concept/topic
    - Knowledge item retrieval
    - Edge traversal for related evidence
    - RAG context for atom generation
    """

    async def search_evidence(
        self,
        query: str,
        domain: str,
        min_confidence: float = 0.6
    ) -> List[EvidenceResult]:
        """Search for evidence supporting a concept."""

    async def get_item(self, item_id: str) -> KnowledgeItem:
        """Fetch a specific knowledge item."""

    async def get_edges(self, item_id: str) -> List[KnowledgeEdge]:
        """Get edges connected to a knowledge item."""

    async def get_rag_context(
        self,
        query: str,
        max_tokens: int = 2000
    ) -> str:
        """Get RAG context for atom generation."""
```

### 2. Content Enrichment Command

**File:** `src/cli/main.py` (extend)

```python
@content_group.command()
@click.option("--domain", required=True, help="Domain to enrich (networking, algorithms, etc.)")
@click.option("--min-confidence", default=0.6, help="Minimum evidence confidence")
@click.option("--dry-run", is_flag=True, help="Show what would be enriched")
@click.option("--limit", default=100, help="Max atoms to enrich")
async def enrich(domain: str, min_confidence: float, dry_run: bool, limit: int):
    """
    Enrich local atoms with evidence from KnowledgeBase.

    For each atom without evidence_id:
    1. Query KB for matching evidence
    2. Update atom with evidence_id and justification
    3. Optionally upgrade ICAP level based on evidence

    Example:
        nls content enrich --domain networking --min-confidence 0.7
    """
```

### 3. Enrichment Transformer

**File:** `src/etl/transformers/kb_enrichment.py`

```python
class KBEnrichmentTransformer(BaseTransformer):
    """
    Enrich atoms with evidence from KnowledgeBase.

    Flow:
    1. Extract key concepts from atom content
    2. Query KB for evidence supporting those concepts
    3. Select best evidence match by confidence
    4. Update atom with:
       - evidence_id
       - justification_science_ref
       - upgraded ICAP level (if evidence suggests higher engagement)
    """

    async def transform(self, atom: LocalAtom) -> EnrichedAtom:
        # Extract concepts
        concepts = self.extract_concepts(atom.content)

        # Query KB
        evidence = await self.kb_client.search_evidence(
            query=" ".join(concepts),
            domain=atom.domain,
            min_confidence=self.min_confidence
        )

        if not evidence:
            return atom  # No evidence found, return unchanged

        best_match = evidence[0]

        # Upgrade ICAP if evidence suggests it
        new_icap = self.icap_upgrade_check(atom, best_match)

        return EnrichedAtom(
            **atom.__dict__,
            evidence_id=best_match.id,
            justification_science_ref=best_match.reference,
            icap_level=new_icap,
            enrichment_confidence=best_match.confidence
        )
```

### 4. Local Atom Storage with Provenance

**File:** `src/db/models/atom.py` (extend)

```python
class LocalAtom(Base):
    __tablename__ = "local_atoms"

    id = Column(UUID, primary_key=True, default=uuid4)
    content = Column(JSONB, nullable=False)
    grading_logic = Column(JSONB, nullable=False)
    atom_type = Column(String(50), nullable=False)
    domain = Column(String(50), nullable=False)
    icap_level = Column(String(20), nullable=False)

    # Provenance (REQUIRED)
    provenance_tech_ref = Column(String(255), nullable=False)
    source_file = Column(String(500))
    source_offsets = Column(JSONB)  # {start: int, end: int}

    # Evidence (populated by enrichment)
    evidence_id = Column(UUID, nullable=True)
    justification_science_ref = Column(String(500), nullable=True)
    enrichment_confidence = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
```

## Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `src/clients/kb_client.py` | MCP/API client for KnowledgeBase |
| `src/clients/__init__.py` | Export client |
| `src/cli/science.py` | `nls science` command group (merged from Batch 6) |
| `src/etl/transformers/kb_enrichment.py` | Evidence enrichment transformer |
| `tests/test_kb_client.py` | Client unit tests |
| `tests/test_kb_enrichment.py` | Enrichment transformer tests |
| `tests/test_science_cli.py` | Science CLI tests |

### Modified Files

| File | Changes |
|------|---------|
| `src/cli/main.py` | Add `nls content enrich` + register science group |
| `src/db/models/atom.py` | Add provenance and evidence fields |
| `src/etl/transformers/__init__.py` | Export enrichment transformer |
| `config.py` | Add KB_API_URL, KB_MCP_URL settings |

## CLI Commands

### Content Commands (Enrichment)

```bash
# Enrich networking atoms with evidence
nls content enrich --domain networking --min-confidence 0.7

# Dry run to see what would be enriched
nls content enrich --domain algorithms --dry-run

# Full pipeline: ingest + enrich
nls content ingest --source docs/source-materials/curriculum/ccna-itn --domain networking
nls content enrich --domain networking

# Check enrichment status
nls content status --domain networking
```

### Science Commands (KB Query Interface)

**File:** `src/cli/science.py` (NEW - merged from deprecated Batch 6)

```python
@click.group()
def science():
    """Query and explore the KnowledgeBase evidence."""
    pass

@science.command()
async def status():
    """Show KnowledgeBase connection status and statistics."""
    # - KB connection health
    # - Total knowledge items
    # - Evidence by domain
    # - Last sync timestamp

@science.command()
async def domains():
    """List available evidence domains in KnowledgeBase."""
    # - learning-sciences
    # - cognitive-load
    # - cs-education
    # - instructional-design

@science.command()
@click.option("--domain", required=True)
@click.option("--query", default=None)
@click.option("--limit", default=10)
@click.option("--output-json", default=None)
async def search(domain: str, query: str, limit: int, output_json: str):
    """Search for evidence in KnowledgeBase."""

@science.command()
@click.argument("item_id")
async def show(item_id: str):
    """Show details of a specific knowledge item."""

@science.command()
@click.option("--domain", required=True)
@click.option("--dry-run", is_flag=True)
@click.option("--output-json", default=None)
async def ingest(domain: str, dry_run: bool, output_json: str):
    """
    Ingest evidence from KnowledgeBase and generate atoms.

    This transforms KB evidence directly into learning atoms,
    as opposed to 'content enrich' which adds evidence to existing atoms.
    """
```

**Usage:**

```bash
# Check KB connection
nls science status

# List domains
nls science domains

# Search for evidence
nls science search --domain learning-sciences --query "spaced repetition" --limit 5

# Show specific item
nls science show abc123-uuid

# Generate atoms directly from evidence (dry run)
nls science ingest --domain cs-education --dry-run --output-json preview.json

# Full ingest
nls science ingest --domain cognitive-load
```

## Environment Variables

```bash
# KnowledgeBase connection (read-only)
KB_API_URL=http://localhost:8000/api/kb
KB_MCP_URL=http://localhost:8001/mcp  # Optional, for MCP protocol

# Cache settings
KB_CACHE_TTL=3600
KB_CACHE_DIR=.cache/kb
```

## Commit Strategy

```bash
# KB Client
git add src/clients/kb_client.py src/clients/__init__.py
git commit -m "feat(batch8b): Add read-only KnowledgeBase client"

# Enrichment transformer
git add src/etl/transformers/kb_enrichment.py
git commit -m "feat(batch8b): Add KB enrichment transformer with evidence linking"

# CLI command
git add src/cli/main.py
git commit -m "feat(batch8b): Add 'nls content enrich' command"

# Atom model update
git add src/db/models/atom.py
git commit -m "feat(batch8b): Add provenance and evidence fields to LocalAtom"

git push -u origin batch-8b-kb-consumer
```

## Success Criteria

- [ ] KB client connects to API/MCP successfully
- [ ] `nls content enrich` finds and links evidence
- [ ] `nls science status` shows KB connection health
- [ ] `nls science domains` lists available domains
- [ ] `nls science search` returns evidence results
- [ ] `nls science ingest` generates atoms from evidence
- [ ] Atoms have valid provenance_tech_ref
- [ ] Atoms with evidence have valid evidence_id
- [ ] No writes to ResearchEngine DB (read-only)
- [ ] Unit tests pass with mocked KB responses

## Testing

```bash
# Unit tests with mocked KB
pytest tests/test_kb_client.py
pytest tests/test_kb_enrichment.py

# Integration test (requires running KB)
pytest tests/integration/test_kb_integration.py --kb-url http://localhost:8000
```

---

**Reference:** Wave 5 Knowledge Integration | **Depends On:** Batch 7, Batch 8a
