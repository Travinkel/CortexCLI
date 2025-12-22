# Batch 9: SharedKernel Technical Content Extractor

**Branch:** `batch-9-shared-kernel-extractor`
**Repo:** `E:\Repo\project-astartes\SharedKernel`
**Priority:** HIGH | **Effort:** 1-2 days | **Status:** Pending

## Overview

Extract the Technical Content Extractor from CortexCLI into SharedKernel so all Astartes products can use it. This creates a reusable library for parsing PDFs, TXTs, and other technical documents into structured chunks.

## SharedKernel Structure

```
E:\Repo\project-astartes\SharedKernel\
├── AstartesAgents/       # Agent orchestration
├── KnowledgeBase/        # Evidence storage + API
├── MCP/                  # Model Context Protocol servers
├── ResearchEngine/       # Systematic review pipeline
└── ContentExtractor/     # NEW - Technical content parsing
    ├── src/
    │   ├── extractors/
    │   │   ├── __init__.py
    │   │   ├── base.py
    │   │   ├── pdf_extractor.py
    │   │   ├── txt_extractor.py
    │   │   └── markdown_extractor.py
    │   ├── classifiers/
    │   │   ├── __init__.py
    │   │   ├── gemini_classifier.py
    │   │   └── concept_extractor.py
    │   └── models/
    │       ├── __init__.py
    │       ├── raw_chunk.py
    │       └── tech_node.py
    ├── tests/
    ├── pyproject.toml
    └── README.md
```

## Files to Move from CortexCLI

| Source (cortex-cli) | Destination (SharedKernel/ContentExtractor) |
|---------------------|---------------------------------------------|
| `src/etl/extractors/pdf_extractor.py` | `src/extractors/pdf_extractor.py` |
| `src/etl/extractors/txt_extractor.py` | `src/extractors/txt_extractor.py` |
| `src/etl/transformers/gemini_classifier.py` | `src/classifiers/gemini_classifier.py` |

## New Files to Create

| File | Purpose |
|------|---------|
| `src/extractors/base.py` | Abstract base class for extractors |
| `src/extractors/markdown_extractor.py` | Markdown/MDX parsing |
| `src/classifiers/concept_extractor.py` | Extract key concepts from text |
| `src/models/raw_chunk.py` | Dataclass for extracted chunks |
| `src/models/tech_node.py` | Dataclass matching KB tech_nodes |
| `pyproject.toml` | Package config (astartes-content-extractor) |

## Package Definition

**pyproject.toml:**

```toml
[project]
name = "astartes-content-extractor"
version = "0.1.0"
description = "Technical content extraction for Astartes products"
dependencies = [
    "pymupdf>=1.23.0",
    "google-cloud-aiplatform>=1.38.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio"]
```

## Integration with Products

### CortexCLI

```python
# Before (local)
from src.etl.extractors.pdf_extractor import PDFExtractor

# After (SharedKernel)
from astartes_content_extractor.extractors import PDFExtractor
from astartes_content_extractor.classifiers import GeminiClassifier
```

### ResearchEngine

```python
# For lifting pipeline
from astartes_content_extractor.extractors import PDFExtractor
from astartes_content_extractor.models import RawChunk, TechNode
```

### RigorHub

```python
# For document ingestion
from astartes_content_extractor import extract_pdf, classify_content
```

## API Design

```python
# Simple extraction
from astartes_content_extractor import extract

chunks = extract("path/to/document.pdf")
# Returns: List[RawChunk]

# With classification
from astartes_content_extractor import extract_and_classify

classified = extract_and_classify(
    "path/to/document.pdf",
    classifier="gemini"  # or "local"
)
# Returns: List[ClassifiedChunk]

# Batch processing
from astartes_content_extractor import BatchExtractor

extractor = BatchExtractor(
    source_dir="docs/source-materials",
    output_format="tech_nodes"
)
results = await extractor.process_all()
```

## Migration Steps

1. **Create ContentExtractor directory** in SharedKernel
2. **Copy extractors** from cortex-cli (preserve git history if possible)
3. **Refactor imports** to be package-relative
4. **Add package config** (pyproject.toml)
5. **Update cortex-cli** to import from SharedKernel
6. **Update ResearchEngine** to use shared extractors
7. **Remove duplicated code** from cortex-cli

## Commit Strategy

```bash
cd E:/Repo/project-astartes/SharedKernel

# Create component
mkdir -p ContentExtractor/src/{extractors,classifiers,models}

# Initialize
git add ContentExtractor/
git commit -m "feat(batch9): Initialize ContentExtractor component in SharedKernel"

# Add extractors
git commit -m "feat(batch9): Add PDF and TXT extractors"

# Add classifiers
git commit -m "feat(batch9): Add Gemini content classifier"

# Add package config
git commit -m "feat(batch9): Add pyproject.toml for astartes-content-extractor"

git push origin main
```

## CortexCLI Update

After SharedKernel is ready, update cortex-cli:

```bash
cd E:/Repo/cortex-cli

# Add SharedKernel as dependency
pip install -e ../project-astartes/SharedKernel/ContentExtractor

# Update imports in src/etl/
# Remove local extractors (now in SharedKernel)
```

## Success Criteria

- [ ] ContentExtractor component created in SharedKernel
- [ ] PDF, TXT, Markdown extractors working
- [ ] Gemini classifier integrated
- [ ] Package installable via pip
- [ ] CortexCLI imports from SharedKernel
- [ ] ResearchEngine can use extractors
- [ ] Unit tests pass

## Testing

```bash
cd E:/Repo/project-astartes/SharedKernel/ContentExtractor

# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest tests/

# Test from cortex-cli
cd E:/Repo/cortex-cli
python -c "from astartes_content_extractor import extract; print('OK')"
```

## Dependencies

- Wave 3 (Schemas) - Not blocking, parallel work
- Batch 7 (Technical Content Extractor) - Source of code to move

## Blocks

- Batch 8b (KB Consumer) - Should import from SharedKernel
- Future products - Will use SharedKernel extractors

---

**Reference:** SharedKernel Architecture | **Related:** Batch 7, Batch 8b
