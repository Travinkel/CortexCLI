"""
Create GitHub issues for batch 5a (safe, idempotent, dry-run capable).

Usage:
  python -m scripts.create_gh_issues --dry-run
  python -m scripts.create_gh_issues --repo owner/repo --execute --confirm

This script generates `gh issue create` commands and, optionally, executes them using the GitHub CLI.
It intentionally defaults to --dry-run to avoid accidental issue creation.

Design notes:
- generate_issues() returns a list of issue dicts: {title, body, labels, milestone}
- build_command() returns the gh CLI command string for an issue
- main() supports --dry-run, --execute, --chunk-size, --repo, --confirm, --log-file

Idempotency when executing:
- If --execute and --skip-if-exists are provided, the script will check for existing issues
  by title using `gh issue list --repo <repo> --search "in:title '<title>'" --json title`.
  This is a simple heuristic and may be tuned.

This file keeps external calls optional and testable without GH credentials.
"""

from __future__ import annotations
import argparse
import json
import logging
import os
import shlex
import subprocess
import sys
from typing import Dict, List
import time
import hashlib

logger = logging.getLogger("create_gh_issues")


def generate_issues() -> List[Dict]:
    """Generate the 135 issues described in docs/agile/batch-5a-github-issues.md.

    Returns a list of dicts with keys: title, body, labels (list), milestone (optional).
    """
    issues = []

    # Epic: Skill Graph Foundation (5 issues)
    sg_titles = [
        "[Batch 1] Skill Graph Database Schema",
        "[Batch 1] SkillMasteryTracker with Bayesian Updates",
        "[Batch 1] Skill-Based Atom Selection",
        "[Batch 1] Skill Taxonomy Seed Data",
        "[Batch 1] Integration Tests",
    ]
    for t in sg_titles:
        issues.append({
            "title": t,
            "body": "See docs/agile/batch-1-skill-graph.md and migrations/030_skill_graph.sql\n\nFiles: Migration 030_skill_graph.sql, skill_taxonomy_seed.sql",
            "labels": ["batch-1", "database", "skill-graph", "enhancement"],
            "milestone": "Phase 1: Foundation",
        })

    # Epic: Greenlight Integration (6 issues)
    gl_titles = [
        "GreenlightClient HTTP Client",
        "SessionManager Greenlight Handoff",
        "Greenlight Queue Table",
        "Terminal Result Rendering",
        "Retry/Fallback Strategies",
        "Integration Tests with Mock Server",
    ]
    for t in gl_titles:
        issues.append({
            "title": f"[Batch 2] {t}",
            "body": "Greenlight integration work. See docs/agile and docs/explanation/greenlight-integration.md",
            "labels": ["batch-2", "greenlight", "integration"],
            "milestone": "Phase 2: Greenlight",
        })

    # Epic: Tier 1 Atom Handlers (18 issues)
    handler_names = [
        "cloze_dropdown",
        "short_answer_exact",
        "multiple_choice_single",
        "multiple_choice_multiple",
        "parsons",
        "ordering",
        "matching",
        "fill_in_blank",
        "true_false",
        "numeric_entry",
        "drag_and_drop",
        "image_hotspot",
        "select_all_that_apply",
        "code_eval",
        "essay_stub",
    ]
    for name in handler_names:
        issues.append({
            "title": f"[Batch 3] Handler: {name}",
            "body": f"Implement handler `{name}` and add unit tests. See docs/agile/batch-3a-handlers-declarative.md",
            "labels": ["batch-3", "handler"],
        })
    # 3 additional batch-level
    for t in [
        "Handler Registry Updates",
        "Unit Test Suite",
        "Skill Linking Integration",
    ]:
        issues.append({
            "title": f"[Batch 3] {t}",
            "body": "Batch-level handler work",
            "labels": ["batch-3", "integration"],
        })

    # Epic: JSONB Schema & Validation (103 issues)
    issues.append({
        "title": "Atom Envelope v2 Schema",
        "body": "Top-level atom envelope v2 schema",
        "labels": ["batch-4", "schema"],
    })

    # One issue per subschema (100 total) — create placeholders
    for i in range(1, 101):
        issues.append({
            "title": f"[Batch 4] Schema Subschema {i:03d}",
            "body": f"Define JSON schema for subschema {i:03d}.",
            "labels": ["batch-4", "schema", f"subschema-{i:03d}"],
        })

    # 3 more schema-related issues
    for t in [
        "AtomValidator Class Implementation",
        "Validation Pipeline Integration",
        "Validation Test Suite",
    ]:
        issues.append({
            "title": f"[Batch 4] {t}",
            "body": "Validation and testing for JSON schemas",
            "labels": ["batch-4", "validation"],
        })

    # Epic: Documentation (2 issues)
    issues.append({
        "title": "[Batch 5] Update All Documentation Files",
        "body": "Refresh docs to include atom taxonomy and skill graph overviews",
        "labels": ["batch-5", "docs"],
    })
    issues.append({
        "title": "[Batch 5] Create Implementation Guide",
        "body": "Add implementation guide for new atom types and handlers",
        "labels": ["batch-5", "docs"],
    })

    # total should be 135
    assert len(issues) == 135, f"Generated {len(issues)} issues, expected 135"
    return issues


def build_command(issue: Dict, repo: str = None) -> str:
    """Build a gh CLI command string for printing purposes. Keep single-line by escaping newlines."""
    title = issue.get("title", "Untitled")
    body = issue.get("body", "")
    labels = issue.get("labels", [])
    milestone = issue.get("milestone")

    # Sanitize newlines in title/body so printed commands stay single-line
    title = title.replace("\n", "\\n")
    body = body.replace("\n", "\\n")

    cmd = ["gh", "issue", "create"]
    if repo:
        cmd += ["--repo", repo]
    cmd += ["--title", title]
    if body:
        cmd += ["--body", body]
    if labels:
        cmd += ["--label", ",".join(labels)]
    if milestone:
        cmd += ["--milestone", milestone]

    # Quote/escape arguments for safe shell execution when printing
    return " ".join(shlex.quote(c) for c in cmd)


def build_command_args(issue: Dict, repo: str = None) -> List[str]:
    """Build gh CLI argument list for subprocess.run (no shell)."""
    title = issue.get("title", "Untitled")
    body = issue.get("body", "")
    labels = issue.get("labels", [])
    milestone = issue.get("milestone")

    cmd = ["gh", "issue", "create"]
    if repo:
        cmd += ["--repo", repo]
    cmd += ["--title", title]
    if body:
        cmd += ["--body", body]
    if labels:
        cmd += ["--label", ",".join(labels)]
    if milestone:
        cmd += ["--milestone", milestone]
    return cmd


def issue_exists(title: str, repo: str) -> bool:
    """Check for an existing issue with this title using gh CLI.

    Returns True if a match is found. Requires `gh` to be installed and logged in.
    """
    try:
        cmd = [
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--search",
            f"in:title '{title}'",
            "--limit",
            "100",
            "--json",
            "title",
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        hits = json.loads(out)
        return any(h.get("title") == title for h in hits)
    except Exception:
        # If any error occurs (gh missing, JSON parse), be conservative and return False
        return False


def execute_command(cmd: str) -> int:
    """Execute a shell command using subprocess.call; return exit code."""
    try:
        rc = subprocess.call(cmd, shell=True)
        return rc
    except Exception as e:
        logger.error("Execution error: %s", e)
        return 1


def chunked(iterable: List, size: int):
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create GitHub issues for batch 5a (safe)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Only print commands (default)")
    parser.add_argument("--execute", action="store_true", help="Execute commands (requires gh and/or GITHUB_TOKEN)")
    parser.add_argument("--repo", type=str, help="GitHub repo in owner/repo format")
    parser.add_argument("--chunk-size", type=int, default=50, help="Number of issues to create per chunk")
    parser.add_argument("--confirm", action="store_true", help="Skip interactive confirmation when executing")
    parser.add_argument("--skip-if-exists", action="store_true", help="Skip creating an issue if a title match exists in the repo")
    parser.add_argument("--log-file", type=str, help="Path to write a JSON log of created/dry-run commands")
    parser.add_argument("--wait-per-item", type=float, default=0.0, help="Seconds to wait between each request")
    parser.add_argument("--wait-between-chunks", type=float, default=1.0, help="Seconds to wait between chunks")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    issues = generate_issues()
    commands = [build_command(i, repo=args.repo) for i in issues]

    log_records = []

    if args.dry_run and not args.execute:
        logger.info("Dry run: will print %d commands", len(commands))
        for c in commands:
            print(c)
        if args.log_file:
            with open(args.log_file, "w", encoding="utf-8") as f:
                json.dump({"mode": "dry-run", "commands": commands}, f, indent=2)
        return 0

    # If executing, optionally confirm
    if args.execute:
        if not args.repo:
            logger.error("--execute requires --repo owner/repo")
            return 2
        if not args.confirm:
            resp = input(f"About to execute {len(commands)} commands against repo {args.repo}. Proceed? [y/N]: ")
            if resp.lower() not in ("y", "yes"):
                print("Aborted by user")
                return 1

        # chunk and execute
        for chunk_idx, chunk in enumerate(chunked(list(zip(issues, commands)), args.chunk_size), start=1):
            logger.info("Processing chunk %d/%d (size=%d)", chunk_idx, (len(issues) + args.chunk_size - 1) // args.chunk_size, len(chunk))
            for idx_in_chunk, (issue, printed_cmd) in enumerate(chunk, start=1):
                title = issue.get("title")
                # skip if exists check
                if args.skip_if_exists:
                    try:
                        if issue_exists(title, args.repo):
                            logger.info("Skipping existing issue: %s", title)
                            log_records.append({"title": title, "status": "skipped_exists"})
                            continue
                    except Exception:
                        # On any error assume not exists (conservative)
                        logger.warning("Could not check existing issues for title: %s", title)
                # Build arg list and attempt execution with retries
                cmd_args = build_command_args(issue, repo=args.repo)
                attempts = 0
                max_attempts = 3
                backoff = 1.0
                created = False
                while attempts < max_attempts and not created:
                    attempts += 1
                    logger.info("Executing (%d/%d chunk %d/%d): %s (attempt %d)", idx_in_chunk, len(chunk), chunk_idx, (len(issues) + args.chunk_size - 1) // args.chunk_size, title, attempts)
                    try:
                        proc = subprocess.run(cmd_args, capture_output=True, text=True)
                        if proc.returncode == 0:
                            created = True
                            log_records.append({"title": title, "status": "created", "stdout": proc.stdout.strip()})
                            logger.info("Created issue: %s", title)
                        else:
                            stderr = (proc.stderr or "").lower()
                            logger.warning("Failed to create issue '%s' rc=%d stderr=%s", title, proc.returncode, proc.stderr.strip())
                            # simple rate-limit/backoff heuristic
                            if "rate limit" in stderr or "rate limited" in stderr or proc.returncode in (1, 2, 126, 127, 128):
                                logger.info("Retrying after backoff %.1fs", backoff)
                                time.sleep(backoff)
                                backoff *= 2
                                continue
                            else:
                                log_records.append({"title": title, "status": f"failed_rc_{proc.returncode}", "stderr": proc.stderr.strip()})
                                break
                    except Exception as e:
                        logger.error("Exception executing gh command for title %s: %s", title, e)
                        time.sleep(backoff)
                        backoff *= 2
                        continue

                # wait between items to be gentle
                if args.wait_per_item and args.wait_per_item > 0:
                    time.sleep(args.wait_per_item)

            # wait between chunks
            if args.wait_between_chunks and args.wait_between_chunks > 0:
                logger.info("Waiting %.1fs between chunks", args.wait_between_chunks)
                time.sleep(args.wait_between_chunks)

        # write log file if requested
        if args.log_file:
            try:
                with open(args.log_file, "w", encoding="utf-8") as f:
                    json.dump({"mode": "execute", "records": log_records}, f, indent=2)
            except Exception as e:
                logger.error("Could not write log file %s: %s", args.log_file, e)

        return 0

    # Fallback: print commands
    for c in commands:
        print(c)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
