#!/usr/bin/env python3
"""cdr-sr-tracker.py — Cognitive Debt Ratio & Stability Ratio tracker.

Cold start (N < 30 commits): tracks CDR
Runtime (N >= 30 commits): tracks SR via 15-commit sliding window

Usage: python cdr-sr-tracker.py [--project-root .] [--output json]
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def run_git(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd)] + cmd,
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def count_total_lines(cwd: Path) -> int:
    """Count total active lines in src/ (excluding blank/comment lines)."""
    total = 0
    for py_file in cwd.rglob("src/**/*.py"):
        try:
            lines = py_file.read_text(encoding="utf-8").split("\n")
            total += sum(1 for l in lines if l.strip() and not l.strip().startswith("#"))
        except Exception:
            pass
    return total


def count_unverified_lines(cwd: Path) -> int:
    """Estimate unverified AI-generated lines via git blame.

    Lines authored by AI (Co-Authored-By: Claude/OpenAI/Copilot) that have
    NOT been modified by developer in subsequent commits are 'unverified'.
    """
    # This is a heuristic: lines where the last modifier is AI (not dev)
    unverified = 0
    for py_file in cwd.rglob("src/**/*.py"):
        try:
            output = run_git(
                ["blame", "--line-porcelain", str(py_file.relative_to(cwd))],
                cwd,
            )
            if not output:
                continue
            for line in output.split("\n"):
                if line.startswith("author-mail ") and (
                    "noreply@anthropic.com" in line
                    or "noreply@github.com" in line
                    or "copilot" in line.lower()
                ):
                    unverified += 1
        except Exception:
            pass
    return unverified


def compute_cdr(cwd: Path) -> dict[str, Any]:
    """Cognitive Debt Ratio — cold start proxy."""
    total = count_total_lines(cwd)
    unverified = count_unverified_lines(cwd)

    if total == 0:
        return {"cdr": 0.0, "total_lines": 0, "unverified_lines": 0, "status": "no_data"}

    cdr = unverified / total
    return {
        "cdr": round(cdr, 4),
        "total_lines": total,
        "unverified_lines": unverified,
        "threshold": 0.15,
        "status": "pass" if cdr <= 0.15 else "fail",
    }


def compute_sr(cwd: Path, window: int = 15) -> dict[str, Any]:
    """Stability Ratio — 15-commit sliding window.

    sigma* = proportion of files in the window that have NOT been
    re-opened within 14 days of their last commit.
    """
    commit_hashes = run_git(
        ["log", "--format=%H", f"-{window}"], cwd
    ).split("\n")
    commit_hashes = [h for h in commit_hashes if h]

    if len(commit_hashes) < window:
        return {
            "sr": None,
            "sigma": None,
            "status": "insufficient_data",
            "commits_available": len(commit_hashes),
            "commits_needed": window,
        }

    # For each file touched in this window, check if it was re-touched within 14 days
    files_touched: set[str] = set()
    files_reopened: set[str] = set()

    for commit in commit_hashes:
        changed = run_git(
            ["diff-tree", "--no-commit-id", "--name-only", "-r", commit], cwd
        ).split("\n")
        changed = [f for f in changed if f]

        for f in changed:
            if f in files_touched:
                files_reopened.add(f)
            files_touched.add(f)

        # Check 14-day window forward from this commit's date
        commit_date_str = run_git(
            ["log", "-1", "--format=%aI", commit], cwd
        )
        if commit_date_str:
            try:
                commit_date = datetime.fromisoformat(commit_date_str)
                cutoff = commit_date + timedelta(days=14)
                since = commit_date.isoformat()
                until = cutoff.isoformat()
                later_changes = run_git(
                    ["log", "--format=%H", f"--since={since}", f"--until={until}"],
                    cwd,
                ).split("\n")
                later_changes = [h for h in later_changes if h and h != commit]
                for later_commit in later_changes:
                    later_files = run_git(
                        ["diff-tree", "--no-commit-id", "--name-only", "-r", later_commit],
                        cwd,
                    ).split("\n")
                    for lf in later_files:
                        if lf in files_touched:
                            files_reopened.add(lf)
            except ValueError:
                pass

    if not files_touched:
        return {"sr": None, "sigma": None, "status": "no_data"}

    sigma_star = 1.0 - (len(files_reopened) / len(files_touched))
    sr = 1.0 / (4.0 * sigma_star * (1.0 - sigma_star)) if 0 < sigma_star < 1 else float("inf")

    return {
        "sr": round(sr, 2) if sr != float("inf") else "inf",
        "sigma": round(sigma_star, 4),
        "files_touched": len(files_touched),
        "files_reopened": len(files_reopened),
        "threshold": 2.4,
        "status": "pass" if sr >= 2.4 else "fail",
        "window_commits": len(commit_hashes),
    }


def main():
    parser = argparse.ArgumentParser(description="CDR/SR Tracker for dev-ownership skill")
    parser.add_argument("--project-root", type=Path, default=Path.cwd(),
                        help="Project root directory (default: CWD)")
    parser.add_argument("--output", choices=["json", "text"], default="text",
                        help="Output format")
    args = parser.parse_args()

    total_commits_str = run_git(["rev-list", "--count", "HEAD"], args.project_root)
    total_commits = int(total_commits_str) if total_commits_str.isdigit() else 0

    if total_commits < 30:
        mode = "cold_start"
        result = compute_cdr(args.project_root)
    else:
        mode = "runtime"
        result = compute_sr(args.project_root)

    result["mode"] = mode
    result["total_commits"] = total_commits

    if args.output == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"Mode: {mode} ({total_commits} commits)")
        if mode == "cold_start":
            print(f"CDR: {result.get('cdr', 'N/A')} (threshold ≤ 0.15)")
            print(f"  Unverified: {result.get('unverified_lines', '?')} lines")
            print(f"  Total:      {result.get('total_lines', '?')} lines")
            print(f"  Status:     {result.get('status', 'unknown')}")
        else:
            print(f"SR:  {result.get('sr', 'N/A')} (threshold ≥ 2.4)")
            print(f"  σ*:  {result.get('sigma', 'N/A')}")
            print(f"  Files touched:  {result.get('files_touched', '?')}")
            print(f"  Files reopened: {result.get('files_reopened', '?')}")
            print(f"  Status: {result.get('status', 'unknown')}")


if __name__ == "__main__":
    main()
