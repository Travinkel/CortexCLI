# Batch 2d: Quality Gates (BDD + CI)

Branch: batch-2d-quality-ci
Worktree: ../cortex-batch-2d-quality-ci
Priority: high (quality foundation for Wave 2+)
Estimated effort: 2 days
Status: pending

## Objective

Establish BDD scaffolding and CI quality gates so new handlers and schemas land with automated validation.

## Dependencies

Required:
- Batch 1a merged (schema exists)
- Batch 2a merged (integration hooks exist)

Blocks:
- Wave 2 handlers (should land with tests wired)

## Files to Create or Modify

- tests/bdd/features/*
- tests/bdd/steps/*
- .github/workflows/pr-checks.yml (BDD job)
- tests/fixtures/* (seed data for BDD)

## Checklist

- Add BDD feature files for skill graph, greenlight queue, and atom selection
- Add step definitions with database fixtures
- Wire BDD tests into CI
- Add a local test entry (make test-bdd or script)
- Update docs/explanation/bdd-testing-strategy.md and ci-cd-pipeline.md

## Testing

```bash
pytest -m bdd
```

## Commit Strategy

```bash
cd ../cortex-batch-2d-quality-ci

git add tests/bdd

git commit -m "test(batch2d): Add BDD feature scaffolding for core flows

Generated with Claude Code

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

git add .github/workflows/pr-checks.yml

git commit -m "chore(batch2d): Add CI gates for BDD, migrations, and tests

Generated with Claude Code

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

git push -u origin batch-2d-quality-ci
```

## GitHub Issues

```bash
gh issue create \
  --title "[Batch 2d] Quality Gates (BDD + CI)" \
  --body "Add BDD scaffolding and CI gates for core flows.\n\nAreas:\n- tests/bdd\n- CI workflow updates\n\nStatus: complete" \
  --label "batch-2d,quality,testing,ci" \
  --milestone "Phase 1: Foundation"
```

## Success Metrics

- BDD tests run locally
- CI runs BDD + unit tests + migration checks
- BDD scenarios cover skill graph + greenlight + atom selection
## testing and ci

- add or update tests relevant to this batch
- add or update bdd scenarios where applicable
- ensure pr-checks.yml passes before merge


