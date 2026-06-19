#!/usr/bin/env python3
"""run-mutation.py — Tiered mutation testing strategy.

方案B: Different depth for different context.
  Review exit:  targeted — only changed files (fast)
  Retrospect:   full run — entire project (deep)
  Small project: all mutants — no sampling (<200 lines)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime


def find_mutatest() -> str:
    """Find mutatest executable."""
    for path in [
        r"C:\Users\yfk\AppData\Local\Programs\Python\Python39\Scripts\mutatest.exe",
        r"C:\Users\yfk\AppData\Local\Programs\Python\Python311\Scripts\mutatest.exe",
    ]:
        if Path(path).exists():
            return path
    return None


def find_pytest_python() -> str:
    """Find Python that can run pytest."""
    for path in [
        r"C:\Users\yfk\AppData\Local\Programs\Python\Python39\python.exe",
        r"C:\Users\yfk\AppData\Local\Programs\Python\Python311\python.exe",
    ]:
        if Path(path).exists():
            return path
    return sys.executable


def count_source_lines(src_dir: Path) -> int:
    total = 0
    for f in src_dir.rglob("*.py"):
        if "__pycache__" not in str(f) and "__init__" not in f.name:
            total += len(f.read_text(encoding="utf-8", errors="replace").split("\n"))
    return total


def get_changed_files(project_root: Path) -> list[str]:
    """Get Python files changed since last commit."""
    result = subprocess.run(
        ["git", "-C", str(project_root), "diff", "--name-only", "HEAD~1" if _has_prev(project_root) else "HEAD"],
        capture_output=True, text=True
    )
    # If no previous commit, get all staged/unstaged
    if result.returncode != 0 or not result.stdout.strip():
        result = subprocess.run(
            ["git", "-C", str(project_root), "diff", "--name-only", "--cached"],
            capture_output=True, text=True
        )
    return [f for f in result.stdout.split("\n") if f.endswith(".py") and "test" not in f.lower()]


def _has_prev(root: Path) -> bool:
    r = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD~1"], capture_output=True)
    return r.returncode == 0


def run_mutation(src_path: str, project_root: Path, n_samples: int, mutatest: str, python: str) -> dict:
    """Run mutatest, return parsed results."""
    cmd = [
        mutatest,
        "-s", src_path,
        "-t", f"{python} -m pytest tests/ -q",
        "-n", str(n_samples),
    ]
    result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True, timeout=600)

    detected = 0
    survived = 0
    for line in result.stdout.split("\n"):
        if "DETECTED:" in line:
            detected = int(line.split(":")[1].strip())
        if "SURVIVED:" in line:
            survived = int(line.split(":")[1].strip())
        if "TOTAL RUNS:" in line:
            total = int(line.split(":")[1].strip())

    return {"detected": detected, "survived": survived, "total": detected + survived,
            "score": round(detected / (detected + survived) * 100, 1) if (detected + survived) > 0 else 0}


def main():
    parser = argparse.ArgumentParser(description="Tiered mutation testing")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=["review", "retrospect", "small"], default="review")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = args.project_root
    src_dir = root / "src"
    if not src_dir.exists():
        print("Error: src/ directory not found")
        sys.exit(1)

    python = find_pytest_python()
    mutatest = find_mutatest()
    if not mutatest:
        print("Error: mutatest not found")
        sys.exit(1)
    lines = count_source_lines(src_dir)
    is_small = lines < 200

    if args.mode == "review":
        changed = get_changed_files(root)
        if changed:
            targets = " ".join(str(root / f) for f in changed[:3])  # max 3 files
            print(f"Targeted: {targets}")
            # Run on each changed file, aggregate
            all_results = []
            for f in changed[:3]:
                r = run_mutation(str(root / f), root, 20, mutatest, python)
                all_results.append(r)
            # Merge
            total_detected = sum(r["detected"] for r in all_results)
            total_survived = sum(r["survived"] for r in all_results)
            score = round(total_detected / (total_detected + total_survived) * 100, 1) if (total_detected + total_survived) > 0 else 0
            result = {"mode": "review", "targeted": True, "files": changed[:3],
                      "detected": total_detected, "survived": total_survived, "score": score}
        else:
            # No changed Python files — skip
            result = {"mode": "review", "targeted": True, "files": [], "score": None,
                      "note": "No changed Python files to mutate"}
    elif args.mode == "small" or (args.mode == "review" and is_small):
        # Small project: run ALL mutants, no sampling
        result = run_mutation(str(src_dir), root, 100, mutatest, python)
        result["mode"] = "small_full"
    else:
        # Retrospect: full run
        result = run_mutation(str(src_dir), root, 30, python)
        result["mode"] = "retrospect"

    result["source_lines"] = lines
    result["timestamp"] = datetime.now().isoformat()

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result.get("score") is not None:
            print(f"Mutation score: {result['score']}% ({result['detected']}/{result['total']})")
        else:
            print(f"Mode: {result['mode']} — {result.get('note', 'no changes')}")


if __name__ == "__main__":
    main()
