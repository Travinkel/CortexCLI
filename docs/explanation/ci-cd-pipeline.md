# ci cd pipeline

## purpose

Define the minimum CI gates for Cortex-CLI so cognitive behavior and data integrity are enforced before merge.

## pipelines

### pr checks

Triggered on pull_request and batch branch pushes.

Checks:
- lint (ruff)
- type checking (mypy)
- unit tests with coverage gate
- integration tests (postgres service)
- migration validation
- bdd scenarios (if tests/bdd exists)

Workflow: .github/workflows/pr-checks.yml

### nightly integration

Triggered on schedule or manual dispatch.

Checks:
- acceptance tests
- psychometric checks
- performance budgets (selector and mastery update)

Workflow: .github/workflows/nightly-integration.yml

### deploy staging

Triggered on master merge.

Checks:
- build and smoke test
- run migrations
- health check

Workflow: .github/workflows/deploy-staging.yml

## gates

- failing checks block merge
- coverage target: >= 85% for unit tests
- migrations must apply cleanly on postgres
- bdd scenarios must pass when present

## links

- bdd-testing-strategy.md
- schema-migration-plan.md
