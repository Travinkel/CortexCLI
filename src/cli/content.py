"""
Content Ingestion CLI.

Commands for ingesting technical content using the pedagogy-informed ETL pipeline.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

content_app = typer.Typer(
    help="Content ingestion and ETL pipeline commands",
    no_args_is_help=True,
)

console = Console()


@content_app.command("ingest")
def ingest_content(
    source: Path = typer.Argument(..., help="Source file or directory"),
    domain: str = typer.Option("networking", "--domain", "-d", help="Domain (networking, dotnet, etc.)"),
    output_json: Path = typer.Option(None, "--output-json", "-o", help="Save atoms to JSON"),
    limit: int = typer.Option(100, "--limit", "-l", help="Max files to process"),
    show_evidence: bool = typer.Option(False, "--show-evidence", help="Show evidence provenance"),
    use_gemini: bool = typer.Option(False, "--gemini", help="Use Gemini for classification"),
    use_research: bool = typer.Option(False, "--research", help="Use ResearchEngine enrichment"),
):
    """
    Ingest technical content using pedagogy-informed ETL.

    Examples:
        nls content ingest docs/source-materials/curriculum/ccna/modules --domain networking
        nls content ingest textbook.pdf --output-json atoms.json
    """
    from uuid import uuid4

    from src.etl.models import RawChunk
    from src.etl.extractors.pdf_extractor import PDFExtractor, PDFExtractionConfig
    from src.etl.transformers.gemini_classifier import GeminiContentClassifier, GeminiClassifierConfig
    from src.etl.transformers.pedagogy_informed import PedagogyInformedTransformer, PedagogyTransformerConfig
    from src.etl.transformers.base import TransformerChain

    if not source.exists():
        console.print(f"[red]Error: Source not found: {source}[/red]")
        raise typer.Exit(1)

    console.print("\n[bold cyan]Pedagogy-Informed Content Ingestion[/bold cyan]")
    console.print(f"  Source: {source}")
    console.print(f"  Domain: {domain}")
    console.print(f"  Use Gemini: {use_gemini}")
    console.print(f"  Use ResearchEngine: {use_research}")

    async def run_pipeline():
        console.print(f"\n[yellow][Step 1][/yellow] Extracting content from {source}...")

        all_chunks = []

        if source.is_file():
            files = [source]
        else:
            files = list(source.glob("**/*.pdf")) + list(source.glob("**/*.txt"))

        files = files[:limit]
        console.print(f"  Found {len(files)} files to process")

        for file_path in files:
            try:
                if file_path.suffix.lower() == ".pdf":
                    config = PDFExtractionConfig()
                    extractor = PDFExtractor(file_path, config)
                    chunks = await extractor.extract()
                    all_chunks.extend(chunks)
                    console.print(f"  [green]+[/green] {file_path.name}: {len(chunks)} chunks")
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
                    console.print(f"  [green]+[/green] {file_path.name}: 1 chunk")
            except Exception as e:
                console.print(f"  [red]-[/red] {file_path.name}: {e}")

        if not all_chunks:
            console.print("\n[yellow]No content extracted.[/yellow]")
            return []

        console.print(f"\n  Total chunks: {len(all_chunks)}")

        console.print("\n[yellow][Step 2][/yellow] Classifying and transforming...")

        classifier_config = GeminiClassifierConfig(use_gemini=use_gemini, fallback_to_heuristics=True)
        pedagogy_config = PedagogyTransformerConfig(use_research_engine=use_research, fallback_to_heuristics=True)

        pipeline = [
            GeminiContentClassifier(config=classifier_config),
            PedagogyInformedTransformer(config=pedagogy_config),
        ]
        chain = TransformerChain(pipeline)

        atoms = await chain.run(all_chunks)
        console.print(f"  Generated {len(atoms)} atoms")

        return atoms

    atoms = asyncio.run(run_pipeline())

    if not atoms:
        return

    # Results table
    console.print("\n[bold cyan]Results[/bold cyan]")

    atom_type_counts = {}
    for atom in atoms:
        atom_type_counts[atom.atom_type] = atom_type_counts.get(atom.atom_type, 0) + 1

    table = Table(title=f"Generated {len(atoms)} atoms")
    table.add_column("Atom Type", style="cyan")
    table.add_column("Count", justify="right", style="green")

    for atom_type, count in sorted(atom_type_counts.items(), key=lambda x: -x[1]):
        table.add_row(atom_type, str(count))

    console.print(table)

    if show_evidence:
        console.print("\n[bold]Evidence Provenance:[/bold]")
        for atom in atoms[:10]:
            console.print(f"\n  [{atom.atom_type}] {atom.content.prompt[:50]}...")
            if atom.source_fact_basis:
                console.print(f"    [dim]Evidence: {atom.source_fact_basis[:80]}...[/dim]")

    if output_json:
        output_data = [atom.to_dict() for atom in atoms]
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(output_data, indent=2, default=str), encoding="utf-8")
        console.print(f"\n[green]Saved {len(atoms)} atoms to {output_json}[/green]")


@content_app.command("sources")
def list_sources():
    """List available source material directories."""
    from pathlib import Path

    base = Path("docs/source-materials")

    if not base.exists():
        console.print("[yellow]No source-materials directory found[/yellow]")
        return

    table = Table(title="Available Source Materials")
    table.add_column("Directory", style="cyan")
    table.add_column("Files", justify="right")
    table.add_column("Types")

    for subdir in sorted(base.rglob("*")):
        if subdir.is_dir():
            files = list(subdir.glob("*.*"))
            if files:
                extensions = set(f.suffix for f in files)
                rel_path = subdir.relative_to(base)
                table.add_row(str(rel_path), str(len(files)), ", ".join(extensions))

    console.print(table)
