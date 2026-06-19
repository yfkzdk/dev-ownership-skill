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
    """Run mutatest once, return {detected, survived, total, score, survivors: [...]}."""
    import os
    env = os.environ.copy()
    src_path_abs = str(root / "src")
    env["PYTHONPATH"] = src_path_abs
    cmd = [
        mutatest, "-s", src_path,
        "-t", f"{python} -m pytest tests/ -q",
        "-n", str(n_samples),
    ]
    try:
        result = subprocess.run(cmd, cwd=root, capture_output=True,
                                text=True, timeout=600, env=env)
    except subprocess.TimeoutExpired:
        return {"detected": 0, "survived": 0, "total": 0, "score": 0, "error": "timeout"}

    detected = survived = 0
    survivors = []
    in_survivor_section = False
    for line in result.stdout.split("\n") + result.stderr.split("\n"):
        if "DETECTED:" in line:
            detected = int(line.split(":")[1].strip())
        if "SURVIVED:" in line:
            survived = int(line.split(":")[1].strip())
        # Track section boundaries
        if line.strip() == "SURVIVED":
            in_survivor_section = True
            continue
        if in_survivor_section and line.strip().startswith("---"):
            continue  # separator line, still in survivor section
        if in_survivor_section and line.strip().startswith("- src"):
            # Format: " - src\file.py: (l: N, c: N) - mutation from X to Y"
            parts = line.strip().split(" - ", 1)
            location = parts[0].strip("- ")
            mutation = parts[1] if len(parts) > 1 else ""
            survivors.append({"location": location, "mutation": mutation})
        if in_survivor_section and line.strip() == "":
            # Empty line may end the section
            pass
        # Detect end of SURVIVED section (next major timestamp line)
        if in_survivor_section and "RUN DATETIME" in line:
            in_survivor_section = False
    total = detected + survived
    return {"detected": detected, "survived": survived, "total": total,
            "score": round(detected / total * 100, 1) if total > 0 else 0,
            "survivors": survivors}


# ── Classification (mutation-fix-guide.md 三类修复模式) ─────────────────

CLASSIFY_RULES = [
    # 算术运算符
    (re.compile(r"Add|Sub|Mult|Div|Mod|Pow|FloorDiv"), "arithmetic"),
    # 比较边界
    (re.compile(r"Eq|Gt|Lt|GtE|LtE|NotEq"), "boundary"),
    # 布尔逻辑
    (re.compile(r"Or\b|And\b|Not\b|If_Statement"), "boolean"),
    # 值替换
    (re.compile(r"None to|to None|True to False|False to True"), "value"),
]

EXEMPT_PATTERNS = [
    re.compile(r"__main__"),     # CLI entry
    re.compile(r"Slice|Unbound"), # Python equivalent
]


def classify_survivor(s: dict) -> str:
    """Classify a survivor dict into one of the fix pattern categories."""
    text = f"{s.get('location', '')} {s.get('mutation', '')}"
    for pat, _ in ARID_PATTERNS:
        if pat.search(text):
            return "exempt"  # arid node
    for pat, _ in EXEMPT_PATTERNS:
        if pat.search(text):
            return "exempt"
    for pat, category in CLASSIFY_RULES:
        if pat.search(text):
            return category
    return "other"

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


def _write_fixes_report(path: Path, project: str, score: float,
                        needs_fix: list, exempt: list) -> None:
    """Auto-generate mutation-fixes.md with classified survivors."""
    FIX_SUGGESTIONS = {
        "arithmetic": "**改精确值断言**: 将方向性断言(如 `assert result > 0`)替换为精确计算期望值",
        "boundary": "**加边界输入**: 添加恰好等于阈值的测试输入",
        "boolean": "**加不对称输入**: 添加一个条件为True、另一个为False的输入组合",
        "value": "**检查返回值类型**: 确认断言同时检查值和类型",
    }
    status = "PASS" if score >= 64 else ("WARN" if score >= 55 else "FAIL")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# 突变修复建议 — {project} Review\n\n")
        f.write(f"> 自动生成: 方案B 突变测试 | 得分: {score}%\n\n")
        f.write(f"## 需要修复 ({len(needs_fix)})\n\n")
        if needs_fix:
            f.write("| # | 位置 | 类型 | 修复建议 |\n")
            f.write("|:--:|------|------|------|\n")
            for i, s in enumerate(needs_fix[:15], 1):
                cat = s.get("category", "other")
                suggestion = FIX_SUGGESTIONS.get(cat, "手动分析")
                f.write(f"| {i} | {s['location']} | {cat} | {suggestion} |\n")
        else:
            f.write("无。所有幸存突变体均已豁免。\n")
        if exempt:
            f.write(f"\n## 豁免 ({len(exempt)})\n\n")
            f.write("| 位置 | 原因 |\n")
            f.write("|------|------|\n")
            for s in exempt[:10]:
                f.write(f"| {s['location']} | arid节点/等价突变/CLI入口 |\n")
        f.write(f"\n## 修复优先级\n\n")
        cats = {}
        for s in needs_fix:
            c = s.get("category", "other")
            cats[c] = cats.get(c, 0) + 1
        for c, n in sorted(cats.items(), key=lambda x: -x[1]):
            f.write(f"- **{c}**: {n} 个\n")
        f.write("\n修复顺序: 算术 > 布尔 > 边界 > 值替换\n")


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

    # Collect and classify all survivors from the runs
    all_survivors = {}
    for r in results:
        for s in r.get("survivors", []):
            key = f"{s['location']}: {s['mutation']}"
            if key not in all_survivors:
                s["category"] = classify_survivor(s)
                all_survivors[key] = s

    needs_fix = [s for s in all_survivors.values() if s.get("category") != "exempt"]
    exempt = [s for s in all_survivors.values() if s.get("category") == "exempt"]

    # Auto-generate mutation-fixes.md
    fixes_path = root / "openspec" / "changes" / "mutation-fixes.md"
    fixes_path.parent.mkdir(parents=True, exist_ok=True)
    _write_fixes_report(fixes_path, root.name, score, needs_fix, exempt)
    print(f"Fix report: {fixes_path}")

    if args.json:
        output["needs_fix"] = len(needs_fix)
        output["exempt"] = len(exempt)
        output["categories"] = {s["category"] for s in all_survivors.values()}
        print(json.dumps(output, indent=2))
    else:
        status = "PASS" if score >= 64 else ("WARN" if score >= 55 else "FAIL")
        print(f"Score: {score}% [{status}]")
        print(f"Trend: {arrow}")
        print(f"Needs fix: {len(needs_fix)} | Exempt: {len(exempt)}")
        cats = {}
        for s in needs_fix:
            c = s.get("category", "other")
            cats[c] = cats.get(c, 0) + 1
        for c, n in sorted(cats.items(), key=lambda x: -x[1]):
            print(f"  {c}: {n}")
        print(f"Fix report written to: {fixes_path}")


if __name__ == "__main__":
    main()
