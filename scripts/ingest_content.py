#!/usr/bin/env python3
"""
Content Ingestion Script.

Ingests technical content using pedagogy-informed ETL pipeline.

Usage:
    python scripts/ingest_content.py docs/source-materials/curriculum/ccna --domain networking
    python scripts/ingest_content.py textbook.pdf --output-json atoms.json
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.etl.models import RawChunk
from src.etl.extractors.pdf_extractor import PDFExtractor, PDFExtractionConfig
from src.etl.transformers.gemini_classifier import GeminiContentClassifier, GeminiClassifierConfig
from src.etl.transformers.pedagogy_informed import PedagogyInformedTransformer, PedagogyTransformerConfig
from src.etl.transformers.base import TransformerChain


async def run_pipeline(
    source: Path,
    domain: str,
    use_gemini: bool,
    use_research_engine: bool,
    limit: int,
) -> list:
    """Run the ETL pipeline."""
    print(f"\n[Step 1] Extracting content from {source}...")

    all_chunks = []

    if source.is_file():
        files = [source]
    else:
        files = list(source.glob("**/*.pdf")) + list(source.glob("**/*.txt"))

    files = files[:limit]
    print(f"  Found {len(files)} files to process")

    for file_path in files:
        try:
            if file_path.suffix.lower() == ".pdf":
                config = PDFExtractionConfig()
                extractor = PDFExtractor(file_path, config)
                chunks = await extractor.extract()
                all_chunks.extend(chunks)
                print(f"  + {file_path.name}: {len(chunks)} chunks")
            elif file_path.suffix.lower() == ".txt":
                content = file_path.read_text(encoding="utf-8", errors="replace")
                chunk = RawChunk(
                    chunk_id=str(uuid4()),
                    source_file=str(file_path),
                    source_type=domain,
                    title=file_path.stem,
                    content=content[:5000],
                    word_count=len(content.split()),
                )
                all_chunks.append(chunk)
                print(f"  + {file_path.name}: 1 chunk")
        except Exception as e:
            print(f"  - {file_path.name}: {e}")

    if not all_chunks:
        print("\nNo content extracted.")
        return []

    print(f"\n  Total chunks: {len(all_chunks)}")

    # Step 2: Transform
    print("\n[Step 2] Classifying and transforming...")

    classifier_config = GeminiClassifierConfig(use_gemini=use_gemini, fallback_to_heuristics=True)
    pedagogy_config = PedagogyTransformerConfig(use_research_engine=use_research_engine, fallback_to_heuristics=True)

    pipeline = [
        GeminiContentClassifier(config=classifier_config),
        PedagogyInformedTransformer(config=pedagogy_config),
    ]
    chain = TransformerChain(pipeline)

    atoms = await chain.run(all_chunks)
    print(f"  Generated {len(atoms)} atoms")

    return atoms


def main():
    parser = argparse.ArgumentParser(description="Ingest content using pedagogy-informed ETL")
    parser.add_argument("source", type=Path, help="Source file or directory")
    parser.add_argument("--domain", "-d", default="networking", help="Domain (networking, dotnet, etc.)")
    parser.add_argument("--gemini", action="store_true", help="Use Gemini for classification")
    parser.add_argument("--research", action="store_true", help="Use ResearchEngine")
    parser.add_argument("--output-json", "-o", type=Path, help="Save atoms to JSON")
    parser.add_argument("--limit", "-l", type=int, default=100, help="Max files to process")
    parser.add_argument("--show-evidence", action="store_true", help="Show evidence provenance")

    args = parser.parse_args()

    if not args.source.exists():
        print(f"Error: Source not found: {args.source}")
        sys.exit(1)

    print("=" * 60)
    print("Pedagogy-Informed Content Ingestion")
    print("=" * 60)
    print(f"  Source: {args.source}")
    print(f"  Domain: {args.domain}")
    print(f"  Use Gemini: {args.gemini}")
    print(f"  Use ResearchEngine: {args.research}")

    atoms = asyncio.run(run_pipeline(
        source=args.source,
        domain=args.domain,
        use_gemini=args.gemini,
        use_research_engine=args.research,
        limit=args.limit,
    ))

    if not atoms:
        return

    # Results
    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)

    atom_type_counts = {}
    for atom in atoms:
        atom_type_counts[atom.atom_type] = atom_type_counts.get(atom.atom_type, 0) + 1

    print(f"\nGenerated {len(atoms)} atoms:")
    for atom_type, count in sorted(atom_type_counts.items(), key=lambda x: -x[1]):
        print(f"  {atom_type}: {count}")

    if args.show_evidence:
        print("\nEvidence Provenance:")
        for atom in atoms[:10]:
            print(f"\n  [{atom.atom_type}] {atom.content.prompt[:50]}...")
            if atom.source_fact_basis:
                print(f"    Evidence: {atom.source_fact_basis[:80]}...")

    if args.output_json:
        output_data = [atom.to_dict() for atom in atoms]
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(output_data, indent=2, default=str), encoding="utf-8")
        print(f"\nSaved {len(atoms)} atoms to {args.output_json}")


if __name__ == "__main__":
    main()
