# Continuous Integration and Delivery Pipeline

## Overview

This document specifies the automated testing and deployment pipeline for Cortex-CLI, ensuring code quality and cognitive validity before merging to production.

## Pipeline Philosophy

A DARPA-class learning system requires stricter quality gates than standard software. We verify not just code correctness, but **cognitive soundness**—does the implementation match learning science principles?

## Pipeline Stages

### Stage 1: Pre-Commit Hooks (Local)

**Trigger:** `git commit`

**Tools:** pre-commit framework

**Checks:**
- Code formatting (ruff format)
- Import sorting (isort)
- Type hint validation (mypy --strict)
- Security scan (bandit)
- Large file detection (< 1MB)
- Merge conflict markers
- Trailing whitespace removal

**Configuration:** `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.8
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
        args: [--strict, --ignore-missing-imports]

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: [-r, src/, -ll]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-merge-conflict
      - id: check-added-large-files
        args: [--maxkb=1024]
```

**Bypass:** Use `git commit --no-verify` only when explicitly required (documented in commit message).

### Stage 2: Pull Request Checks (GitHub Actions)

**Trigger:** Opening PR, pushing to PR branch

**Workflow:** `.github/workflows/pr-checks.yml`

**Checks:**

1. **Linting & Type Safety**
   ```yaml
   - name: Lint with ruff
     run: ruff check src/ tests/ --output-format=github

   - name: Type check with mypy
     run: mypy src/ --strict --show-error-codes
   ```

2. **Unit Tests**
   ```yaml
   - name: Run unit tests
     run: pytest tests/unit/ -v --cov=src --cov-report=term-missing --cov-fail-under=85
   ```

3. **Integration Tests**
   ```yaml
   - name: Run integration tests
     run: pytest tests/integration/ -v --maxfail=5
     env:
       DATABASE_URL: postgresql://test:test@localhost:5432/cortex_test
   ```

4. **Migration Validation**
   ```yaml
   - name: Validate migrations
     run: |
       psql -U postgres -d cortex_test -f src/db/migrations/*.sql
       psql -U postgres -d cortex_test -c "\dt"  # Verify tables created
   ```

5. **Security Scan**
   ```yaml
   - name: Security audit
     run: |
       bandit -r src/ -ll
       safety check
   ```

**Failure Policy:** Any check failure blocks merge. No overrides except by maintainer with documented reason.

### Stage 3: Integration Test Suite (Nightly)

**Trigger:** Scheduled (daily at 02:00 UTC)

**Workflow:** `.github/workflows/nightly-integration.yml`

**Checks:**

1. **Full Integration Tests** (all scenarios)
2. **Acceptance Tests** (learning outcome validation)
3. **Psychometric Validation** (item analysis on sample cohort)
4. **Performance Benchmarks**
   - Atom selection latency < 100ms
   - Mastery update < 50ms
   - Session throughput > 100 atoms/sec

**Reporting:** Generate report, post to Slack/Discord if failures detected.

### Stage 4: Deployment (Post-Merge)

**Trigger:** Merge to `master` branch

**Workflow:** `.github/workflows/deploy.yml`

**Steps:**

1. **Build:** Package Python wheel
2. **Smoke Test:** Run critical path tests against staging DB
3. **Database Migration:** Apply new migrations to production (with backup)
4. **Deploy:** Update production environment
5. **Health Check:** Verify API endpoints responding

**Rollback:** Automatic rollback if health checks fail within 5 minutes.

## GitHub Actions Workflows

### Workflow: PR Checks

**File:** `.github/workflows/pr-checks.yml`

```yaml
name: Pull Request Checks

on:
  pull_request:
    branches: [master]
  push:
    branches: [batch-*]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -e .[dev]
          pip install ruff mypy bandit safety
      - name: Lint
        run: ruff check src/ tests/ --output-format=github
      - name: Type check
        run: mypy src/ --strict --show-error-codes
      - name: Security scan
        run: |
          bandit -r src/ -ll
          safety check

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: cortex_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -e .[dev,test]

      - name: Run unit tests
        run: |
          pytest tests/unit/ -v \
            --cov=src \
            --cov-report=term-missing \
            --cov-report=xml \
            --cov-fail-under=85

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

      - name: Run integration tests
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5432/cortex_test
        run: |
          pytest tests/integration/ -v --maxfail=5

  migrations:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: cortex_test
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4
      - name: Apply migrations
        run: |
          for f in src/db/migrations/*.sql; do
            echo "Applying $f"
            psql -U postgres -h localhost -d cortex_test -f "$f"
          done
        env:
          PGPASSWORD: test

      - name: Verify schema
        run: |
          psql -U postgres -h localhost -d cortex_test -c "\dt" | tee schema.txt
          grep -q "learning_atoms" schema.txt
          grep -q "skills" schema.txt
          grep -q "atom_skill_weights" schema.txt
        env:
          PGPASSWORD: test
```

### Workflow: Nightly Integration Tests

**File:** `.github/workflows/nightly-integration.yml`

```yaml
name: Nightly Integration Tests

on:
  schedule:
    - cron: '0 2 * * *'  # 02:00 UTC daily
  workflow_dispatch:  # Manual trigger

jobs:
  full-integration:
    runs-on: ubuntu-latest
    timeout-minutes: 60

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: cortex_test
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -e .[dev,test]

      - name: Seed test database
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5432/cortex_test
        run: |
          psql $DATABASE_URL -f tests/fixtures/skills_seed.sql
          psql $DATABASE_URL -f tests/fixtures/atoms_seed.sql
          psql $DATABASE_URL -f tests/fixtures/misconceptions_seed.sql

      - name: Run acceptance tests
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5432/cortex_test
        run: pytest tests/acceptance/ -v --tb=short

      - name: Run psychometric validation
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5432/cortex_test
        run: pytest tests/psychometric/ -v

      - name: Performance benchmarks
        run: |
          python scripts/benchmark_atom_selection.py
          python scripts/benchmark_mastery_update.py

      - name: Generate report
        if: always()
        run: |
          python scripts/generate_test_report.py > report.md
          cat report.md >> $GITHUB_STEP_SUMMARY

      - name: Notify on failure
        if: failure()
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: 'Nightly integration tests failed!'
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### Workflow: Deploy to Staging

**File:** `.github/workflows/deploy-staging.yml`

```yaml
name: Deploy to Staging

on:
  push:
    branches: [master]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: staging

    steps:
      - uses: actions/checkout@v4

      - name: Build wheel
        run: |
          pip install build
          python -m build

      - name: Backup database
        run: |
          pg_dump $STAGING_DB_URL > backup-$(date +%Y%m%d-%H%M%S).sql
        env:
          STAGING_DB_URL: ${{ secrets.STAGING_DB_URL }}

      - name: Apply migrations
        run: |
          for f in src/db/migrations/*.sql; do
            psql $STAGING_DB_URL -f "$f" || exit 1
          done
        env:
          STAGING_DB_URL: ${{ secrets.STAGING_DB_URL }}

      - name: Deploy package
        run: |
          scp dist/*.whl deploy@staging:/opt/cortex/
          ssh deploy@staging 'pip install --upgrade /opt/cortex/*.whl'

      - name: Health check
        run: |
          sleep 10
          curl -f https://staging.cortex.example.com/health || exit 1

      - name: Rollback on failure
        if: failure()
        run: |
          psql $STAGING_DB_URL < backup-*.sql
          ssh deploy@staging 'systemctl restart cortex'
```

## Branch Protection Rules

**Master Branch:**
- Require pull request reviews (1 approver minimum)
- Require status checks to pass:
  - `lint`
  - `test / unit tests`
  - `test / integration tests`
  - `migrations / verify schema`
- Require linear history (no merge commits)
- Require signed commits

**Batch Branches:**
- No protection (allows fast iteration)
- Must squash merge to master

## Quality Gates

### Code Coverage

- **Unit Tests:** 85% minimum coverage
- **Integration Tests:** Cover all critical paths (session start → response → mastery update)
- **Acceptance Tests:** Cover all cognitive subsystems

**Coverage Exceptions:**
- Visualization code (src/ui/ascii_engine.py)
- CLI argument parsing
- Type stubs

**Enforcement:** `--cov-fail-under=85` in pytest config.

### Type Safety

- **Strict Mode:** All production code (`src/`) uses mypy `--strict`
- **Test Code:** Relaxed mode allowed for mocks/fixtures
- **No `Any` Types:** Except for JSONB deserialization (use TypedDict)

**Configuration:** `pyproject.toml`

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
check_untyped_defs = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

### Security

- **Dependency Scanning:** `safety check` on every PR
- **Code Scanning:** `bandit -ll` (low/low severity minimum)
- **Secret Detection:** GitHub secret scanning enabled
- **SAST:** CodeQL analysis on master branch

**Policy:** Security vulnerabilities block merge. No exceptions.

## Performance Benchmarks

**Atom Selection:** < 100ms for skill gap query (99th percentile)

```python
# scripts/benchmark_atom_selection.py
import timeit

def benchmark_atom_selection():
    selector = SkillBasedAtomSelector(db, tracker)
    atoms = selector.select_atoms_by_skill_gap(learner_id, module_id, limit=5)

duration = timeit.timeit(benchmark_atom_selection, number=1000) / 1000
assert duration < 0.1, f"Atom selection too slow: {duration*1000:.1f}ms"
```

**Mastery Update:** < 50ms for Bayesian update + FSRS (99th percentile)

```python
# scripts/benchmark_mastery_update.py
def benchmark_mastery_update():
    tracker.update_skill_mastery(learner_id, atom_id, is_correct=True, ...)

duration = timeit.timeit(benchmark_mastery_update, number=1000) / 1000
assert duration < 0.05, f"Mastery update too slow: {duration*1000:.1f}ms"
```

## Failure Handling

### Test Failures

**Unit/Integration Test Failure:**
1. PR blocked from merging
2. Developer investigates locally
3. Fix committed to PR branch
4. Checks re-run automatically

**Nightly Test Failure:**
1. Slack notification to #engineering
2. Issue created automatically with test output
3. Assigned to on-call engineer
4. Must be triaged within 24 hours

### Migration Failures

**Staging Migration Failure:**
1. Automatic rollback to previous schema
2. Database backup restored
3. Alert sent to #ops channel
4. Migration must be fixed before retry

**Production Migration Failure:**
1. Immediate rollback (< 5 minutes)
2. Incident declared
3. Post-mortem required within 48 hours
4. Migration tested on staging clone before retry

## Monitoring and Alerts

**Metrics Tracked:**
- Test pass rate (unit, integration, acceptance)
- Code coverage trend
- Deployment success rate
- Mean time to recovery (MTTR)
- Build duration

**Alerts:**
- Coverage drops below 80%: Warning
- Coverage drops below 75%: Critical
- Nightly tests fail 2 consecutive days: Critical
- Deployment rollback: Incident

**Dashboard:** GitHub Actions insights + custom Grafana dashboard

## Related Documentation

- [BDD Testing Strategy](bdd-testing-strategy.md): Test methodology and scenarios
- [Atom Type Taxonomy](atom-type-taxonomy.md): Full atom type catalog for test coverage
- [Transfer Testing](../explanation/transfer-testing.md): Learning outcome validation

## Continuous Improvement

**Monthly Review:**
- Analyze test failure patterns
- Identify flaky tests (remove or fix)
- Update coverage targets if consistently exceeded
- Review benchmark thresholds

**Quarterly Review:**
- Evaluate new testing tools
- Update dependency versions
- Assess CI/CD performance (build speed)
- Review incident reports
