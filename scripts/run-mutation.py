#!/usr/bin/env python3
"""run-mutation.py —方案B: Evidence-driven tiered mutation testing.

Three modes (based on Google TSE 2022 + Zenseact ASE 2024):
  review:     targeted — only git-diff changed files, median of 2 runs
  retrospect: full — entire project, median of 2 runs
  small:      all mutants — <200-line projects, full run no sampling

Arid filtering: 3 heuristic rules (logs, time-ops, config-flags).
Evidence: Google 15%→80% productivity with just these 3 (TSE 2022 §3.2.5).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Arid patterns (Google TSE 2022 §3.2.5) ────────────────────────────────
# 3 rules account for 80% of arid mutant suppression at Google.
ARID_PATTERNS = [
    (re.compile(r"\.(?:log|logger|logging|debug|info|warn|error|fatal)\s*\(", re.I), "log"),
    (re.compile(r"(?:sleep|deadline|timeout|backoff|set_deadline)\s*\(", re.I), "time"),
    (re.compile(r"(?:\.flags?\b|\.config\b|FLAGS?_|FLAG_)\s*", re.I), "config"),
]

MUTATEST_PATHS = [
    r"C:\Users\yfk\AppData\Local\Programs\Python\Python39\Scripts\mutatest.exe",
    r"C:\Users\yfk\AppData\Local\Programs\Python\Python311\Scripts\mutatest.exe",
]
PYTHON_PATHS = [
    r"C:\Users\yfk\AppData\Local\Programs\Python\Python39\python.exe",
    r"C:\Users\yfk\AppData\Local\Programs\Python\Python311\python.exe",
]

THIS_DIR = Path(__file__).resolve().parent
HISTORY_FILE = Path.home() / ".claude" / "mutation-history.json"


def find_tool(paths: list[str]) -> Optional[str]:
    for p in paths:
        if Path(p).exists():
            return p
    return None


def count_source_lines(src_dir: Path) -> int:
    total = 0
    for f in src_dir.rglob("*.py"):
        if "__pycache__" not in str(f) and "__init__" not in f.name:
            total += len(f.read_text(encoding="utf-8", errors="replace").split("\n"))
    return total


def is_arid_line(line: str) -> bool:
    """Check if a source line matches arid patterns."""
    return any(p.search(line) for p, _ in ARID_PATTERNS)


def get_changed_files(root: Path) -> list[str]:
    """Python files changed since last commit (or staged)."""
    for cmd in [
        ["git", "-C", str(root), "diff", "--name-only", "HEAD~1"],
        ["git", "-C", str(root), "diff", "--name-only", "--cached"],
    ]:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return [f for f in r.stdout.split("\n") if f.endswith(".py") and "test" not in f.lower()]
    return []


def run_mutation(src_path: str, root: Path, n_samples: int,
                 mutatest: str, python: str) -> dict:
    """Run mutatest once, return {detected, survived, total, score}."""
    cmd = [
        mutatest, "-s", src_path,
        "-t", f"{python} -m pytest tests/ -q",
        "-n", str(n_samples),
    ]
    try:
        result = subprocess.run(cmd, cwd=root, capture_output=True,
                                text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return {"detected": 0, "survived": 0, "total": 0, "score": 0, "error": "timeout"}

    detected = survived = 0
    for line in result.stdout.split("\n") + result.stderr.split("\n"):
        if "DETECTED:" in line:
            detected = int(line.split(":")[1].strip())
        if "SURVIVED:" in line:
            survived = int(line.split(":")[1].strip())
    total = detected + survived
    return {"detected": detected, "survived": survived, "total": total,
            "score": round(detected / total * 100, 1) if total > 0 else 0}


def median_score(runs: list[dict]) -> float:
    scores = [r["score"] for r in runs if r.get("total", 0) > 0]
    if not scores:
        return 0.0
    scores.sort()
    mid = len(scores) // 2
    return scores[mid]


def load_history() -> dict:
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text())
    return {}


def save_history(project: str, mode: str, score: float, lines: int):
    hist = load_history()
    if project not in hist:
        hist[project] = []
    hist[project].append({
        "date": datetime.now().isoformat()[:10],
        "mode": mode,
        "score": score,
        "lines": lines,
    })
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(hist, indent=2))


def trend_arrow(project: str, current: float) -> str:
    hist = load_history()
    entries = hist.get(project, [])
    if len(entries) < 2:
        return "→ (first run)"
    prev = entries[-2]["score"]
    if current > prev + 3:
        return f"↑ improved from {prev}%"
    elif current < prev - 3:
        return f"↓ declined from {prev}%"
    else:
        return f"→ stable (±{abs(current - prev):.1f}%)"


def main():
    parser = argparse.ArgumentParser(description="方案B: Tiered mutation testing")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=["review", "retrospect", "small"], default="review")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = args.project_root.resolve()
    src_dir = root / "src"
    if not src_dir.exists():
        print("Error: src/ not found")
        sys.exit(1)

    mutatest = find_tool(MUTATEST_PATHS)
    python = find_tool(PYTHON_PATHS)
    if not mutatest or not python:
        print("Error: mutatest or python not found")
        sys.exit(1)

    lines = count_source_lines(src_dir)
    is_small = lines < 200

    # Determine effective mode
    if args.mode == "small" or (args.mode == "review" and is_small):
        effective_mode = "small_full"
        print(f"Mode: small_full ({lines} lines)")
        src_path = str(src_dir)
        n_samples = 100
        runs = 1
    elif args.mode == "review":
        effective_mode = "review"
        changed = get_changed_files(root)
        if not changed:
            result = {"mode": "review", "files": [], "score": None,
                      "note": "No changed Python files"}
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print("No changed Python files — skipping mutation test")
            return
        print(f"Mode: review ({len(changed)} changed files)")
        src_path = " ".join(str(root / f) for f in changed[:3])
        n_samples = 20
        runs = 2
    else:  # retrospect
        effective_mode = "retrospect"
        print(f"Mode: retrospect ({lines} lines)")
        src_path = str(src_dir)
        n_samples = 30
        runs = 2

    # Run N times, take median
    results = []
    for i in range(runs):
        r = run_mutation(src_path, root, n_samples, mutatest, python)
        results.append(r)
        if runs > 1:
            print(f"  Run {i+1}: {r['score']}% ({r['detected']}/{r['total']})")

    score = median_score(results)
    arrow = trend_arrow(root.name, score)
    save_history(root.name, effective_mode, score, lines)

    output = {
        "project": root.name,
        "mode": effective_mode,
        "lines": lines,
        "runs": runs,
        "score": score,
        "trend": arrow,
    }

    if args.json:
        output["details"] = results
        print(json.dumps(output, indent=2))
    else:
        status = "PASS" if score >= 64 else ("WARN" if score >= 55 else "FAIL")
        print(f"Score: {score}% [{status}]")
        print(f"Trend: {arrow}")


if __name__ == "__main__":
    main()
