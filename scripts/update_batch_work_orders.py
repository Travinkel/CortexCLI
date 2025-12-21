#!/usr/bin/env python3
"""
Update all batch work orders with BDD testing requirements and strategy document links.
"""

import re
from pathlib import Path

# BDD testing section template
BDD_TESTING_TEMPLATE = """
### BDD Testing Requirements

**See:** [BDD Testing Strategy](../explanation/bdd-testing-strategy.md)

Create tests appropriate for this batch:
- Unit tests for all new classes/functions
- Integration tests for database interactions
- Property-based tests for complex logic (use hypothesis)

### CI Checks

**See:** [CI/CD Pipeline](../explanation/ci-cd-pipeline.md)

This batch must pass:
- Linting (ruff check)
- Type checking (mypy --strict)
- Security scan (bandit)
- Unit tests (85% coverage minimum)
- Integration tests (all critical paths)
"""

# Strategy documents section template
STRATEGY_DOCS_TEMPLATE = """### Strategy Documents
- [BDD Testing Strategy](../explanation/bdd-testing-strategy.md) - Testing approach for cognitive validity
- [CI/CD Pipeline](../explanation/ci-cd-pipeline.md) - Automated quality gates and deployment
- [Atom Type Taxonomy](../reference/atom-type-taxonomy.md) - 100+ atom types with ICAP classification
- [Schema Migration Plan](../explanation/schema-migration-plan.md) - Migration to polymorphic JSONB atoms

### Work Orders"""


def update_batch_file(file_path: Path):
    """Update a single batch work order file."""

    print(f"Updating {file_path.name}...")

    content = file_path.read_text(encoding='utf-8')

    # Check if already updated
    if 'BDD Testing Requirements' in content:
        print(f"  [OK] Already updated, skipping")
        return

    # Find the Testing section
    # Pattern: ## Testing followed by content, then ## (next section)
    testing_pattern = r'(## Testing\n\n)(.*?)(## \w+)'

    def replace_testing(match):
        header = match.group(1)
        existing_content = match.group(2)
        next_section = match.group(3)

        # Add "Manual Validation" subheader if not present
        if '### Manual Validation' not in existing_content:
            existing_content = f"### Manual Validation\n\n{existing_content}"

        return f"{header}{existing_content}\n{BDD_TESTING_TEMPLATE}\n{next_section}"

    # Replace testing section
    updated_content = re.sub(testing_pattern, replace_testing, content, flags=re.DOTALL)

    # Update Reference section
    # Pattern: ## Reference followed by content
    reference_pattern = r'(## Reference\n\n)(.*?)(---|\Z)'

    def replace_reference(match):
        header = match.group(1)
        existing_content = match.group(2)
        footer = match.group(3)

        # Check if "Master Plan" is present
        if 'Master Plan' in existing_content:
            # Replace with new structure
            new_reference = f"{header}{STRATEGY_DOCS_TEMPLATE}\n{existing_content}\n{footer}"
        else:
            # Just add strategy docs
            new_reference = f"{header}{STRATEGY_DOCS_TEMPLATE}\n\n{existing_content}\n{footer}"

        return new_reference

    updated_content = re.sub(reference_pattern, replace_reference, updated_content, flags=re.DOTALL)

    # Write updated content
    file_path.write_text(updated_content, encoding='utf-8')
    print(f"  [OK] Updated successfully")


def main():
    """Update all batch work order files."""

    agile_dir = Path('E:/Repo/cortex-cli/docs/agile')

    # Get all batch files except batch-1a (already updated manually)
    batch_files = sorted(agile_dir.glob('batch-*.md'))
    batch_files = [f for f in batch_files if f.name != 'batch-1a-skill-database.md']

    print(f"Found {len(batch_files)} batch files to update\n")

    for batch_file in batch_files:
        try:
            update_batch_file(batch_file)
        except Exception as e:
            print(f"  [ERROR] {e}")

    print(f"\n[OK] Batch work orders updated")


if __name__ == '__main__':
    main()
