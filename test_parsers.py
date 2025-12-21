"""
Test script for UniversalChunker and TemplateEngine.

Validates Phase 0 success criteria:
1. All 33 files parse without errors
2. Template rules achieve ~30% coverage
3. Output statistics for review
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from processing.course_chunker import UniversalChunker
from content.generation.template_engine import TemplateEngine


def test_all_files():
    """Test parsing all source files."""
    source_dir = Path(__file__).parent / "docs" / "source-materials"

    print("=" * 80)
    print("PHASE 0 PARSER VALIDATION")
    print("=" * 80)
    print()

    # Collect all files
    all_files = list(source_dir.glob("**/*.txt")) + list(source_dir.glob("**/*.md"))

    print(f"Found {len(all_files)} files to process")
    print()

    all_chunks = []
    parse_results = []

    # Test each file
    for file_path in sorted(all_files):
        relative_path = file_path.relative_to(source_dir)

        try:
            chunker = UniversalChunker(file_path)
            chunks = list(chunker.chunk_file())

            parse_results.append({
                "file": str(relative_path),
                "status": "[OK] SUCCESS",
                "chunks": len(chunks),
                "error": None
            })

            all_chunks.extend(chunks)

            print(f"[OK] {str(relative_path):<50} -> {len(chunks):>3} chunks")

        except Exception as e:
            parse_results.append({
                "file": str(relative_path),
                "status": "[FAIL] FAILED",
                "chunks": 0,
                "error": str(e)
            })

            print(f"[FAIL] {str(relative_path):<50} -> ERROR: {e}")

    print()
    print("=" * 80)
    print("PARSE RESULTS SUMMARY")
    print("=" * 80)
    print()

    total_files = len(parse_results)
    successful = sum(1 for r in parse_results if r["status"] == "[OK] SUCCESS")
    failed = sum(1 for r in parse_results if r["status"] == "[FAIL] FAILED")
    total_chunks = sum(r["chunks"] for r in parse_results)

    print(f"Total files:        {total_files}")
    print(f"Successful:         {successful} ({successful/total_files*100:.1f}%)")
    print(f"Failed:             {failed} ({failed/total_files*100:.1f}%)")
    print(f"Total chunks:       {total_chunks}")
    print()

    if failed > 0:
        print("FAILED FILES:")
        for r in parse_results:
            if r["status"] == "[FAIL] FAILED":
                print(f"  - {r['file']}: {r['error']}")
        print()

    # Test template engine coverage
    print("=" * 80)
    print("TEMPLATE ENGINE COVERAGE")
    print("=" * 80)
    print()

    engine = TemplateEngine()
    coverage = engine.get_coverage_stats(all_chunks)

    print(f"Total chunks:                  {coverage['total_chunks']}")
    print(f"Chunks with template atoms:    {coverage['chunks_with_template_atoms']}")
    print(f"Coverage rate:                 {coverage['coverage_rate']*100:.1f}%")
    print(f"Total atoms generated:         {coverage['total_atoms_generated']}")
    print()

    print("Atoms by rule:")
    for rule_name, count in coverage['atoms_by_rule'].items():
        print(f"  {rule_name:<50} {count:>4}")
    print()

    # Success criteria check
    print("=" * 80)
    print("PHASE 0 SUCCESS CRITERIA")
    print("=" * 80)
    print()

    criteria = [
        ("All files parse without errors", failed == 0),
        ("Template coverage >= 30%", coverage['coverage_rate'] >= 0.30),
        ("At least 100 atoms generated", coverage['total_atoms_generated'] >= 100),
    ]

    all_passed = True
    for criterion, passed in criteria:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status:<10} {criterion}")
        if not passed:
            all_passed = False

    print()

    if all_passed:
        print("SUCCESS: ALL PHASE 0 CRITERIA MET!")
    else:
        print("WARNING: SOME CRITERIA NOT MET - REVIEW NEEDED")

    print()

    return all_passed


if __name__ == "__main__":
    success = test_all_files()
    sys.exit(0 if success else 1)
