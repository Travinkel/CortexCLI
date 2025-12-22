Create GitHub issues for Batch 5a

This folder contains `create_gh_issues.py`, a safe, idempotent tool to generate GitHub issues for the 100+ atom taxonomy implementation.

Usage (dry-run, recommended first):

```powershell
# Print all gh commands (safe)
python -m scripts.create_gh_issues --dry-run

# Print and write a JSON log
python -m scripts.create_gh_issues --dry-run --log-file tmp_gh_issues.json
```

To execute against a repository (requires `gh` installed and an authenticated session):

```powershell
# Execute creation (interactive confirmation required unless --confirm)
python -m scripts.create_gh_issues --execute --repo owner/repo --confirm

# Execute but skip creating issues that already match by title
python -m scripts.create_gh_issues --execute --repo owner/repo --confirm --skip-if-exists

# Execute with smaller rate to avoid throttling
python -m scripts.create_gh_issues --execute --repo owner/repo --confirm --wait-per-item 0.5 --wait-between-chunks 2

# Execute and write a JSON log of created/skipped/failed items
python -m scripts.create_gh_issues --execute --repo owner/repo --confirm --log-file gh_issue_log.json
```

Safety notes:
- Default is dry-run: do not run `--execute` until you review output.
- `--skip-if-exists` performs a simple title search and is not perfect; manual review recommended.
- The script uses `gh issue create` under the hood; make sure `gh` is installed and you are logged in.


