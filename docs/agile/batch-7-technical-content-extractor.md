# Batch 7: Technical Content Extractor

**Status:** COMPLETE
**Branch:** master (integrated directly)
**Completed:** 2025-12-21

## Objective

Build the "Bridge" that synthesizes technical documentation (the "What") with ResearchEngine evidence (the "How") to produce pedagogically-optimized learning atoms.

## Deliverables

### Files Created

| File | Purpose |
|------|---------|
| `src/etl/extractors/pdf_extractor.py` | PDF extraction with PyMuPDF, chapter/code detection |
| `src/etl/transformers/gemini_classifier.py` | Content classification (factual/procedural/conceptual/metacognitive) |
| `src/etl/transformers/pedagogy_informed.py` | Evidence-backed pedagogical strategy mapping |
| `scripts/ingest_content.py` | Standalone ingestion script |
| `src/cli/main.py` | Added `content ingest` and `content sources` commands |

### CLI Commands Added

```bash
# Ingest curriculum content
nls content ingest docs/source-materials/curriculum/ccna/modules --domain networking

# Ingest with evidence display
nls content ingest <path> --show-evidence

# Save to JSON
nls content ingest <path> --output-json atoms.json

# List available sources
nls content sources
```

### Generated Outputs

| Output File | Atoms | Content |
|-------------|-------|---------|
| `outputs/curriculum-atoms.json` | 32 | All curriculum (CCNA + CDS + PROGII + SDE2) |
| `outputs/ccna-full-atoms.json` | 27 | CCNA modules + bundles + exams |
| `outputs/ccna-atoms.json` | 17 | CCNA modules only |

### Atom Type Distribution

- **parsons**: 27 (procedural CLI/config content)
- **short_answer**: 5 (conceptual explanations)

## Architecture

```
Technical Content → PDF/TXT Extractor → RawChunk
                          ↓
              GeminiContentClassifier
              (factual/procedural/conceptual/metacognitive)
                          ↓
              PedagogyInformedTransformer
              (EVIDENCE_STRATEGY_MAP → atom_type + evidence)
                          ↓
              TransformedAtom with provenance
```

## Evidence Strategy Map

The ResearchEngine is implemented as a hardcoded evidence map:

| Content Type | Complexity | Atom Type | Evidence |
|--------------|------------|-----------|----------|
| procedural | high | parsons | Parsons & Haden, 2006 |
| procedural | medium | ordered_list | Step sequencing |
| factual | high | mcq | Roediger & Butler, 2011 |
| factual | medium | flashcard | Karpicke & Roediger, 2008 |
| conceptual | high | short_answer | Chi et al., 1994 |
| metacognitive | high | scenario | Bransford et al., 2000 |

## Dependencies

- `pymupdf` (fitz) - PDF parsing
- Existing ETL models and base classes

## Future Enhancements

- [ ] Gemini API integration for LLM-powered classification
- [ ] ResearchEngine vector search for dynamic evidence lookup
- [ ] Bulk textbook ingestion (CCNA Official Guide, ASP.NET Core in Action)
- [ ] Atom hydration pipeline (raw → study-ready)

## Success Criteria

- [x] PDF extraction handles CCNA content
- [x] Content classification achieves reasonable accuracy
- [x] Evidence linkage - every atom has `source_fact_basis`
- [x] CLI functional - `nls content ingest` works
- [x] Generated atoms have ICAP classification
