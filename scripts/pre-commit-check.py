#!/usr/bin/env python3
"""pre-commit-check.py — Quality Gate Runner v2 (Python).

Improvements over v1 (.sh):
- Reads quality-gates.yml (single source of truth for thresholds)
- Auto-detects project framework (Django, Go, Node, Rust, Python)
- Pre-requisite detection with install suggestions
- UTF-8 safe on Windows

Usage: python pre-commit-check.py [--skip-slow] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BOLD = "\033[1m"
NC = "\033[0m"

EXIT_CODE = 0


def run(cmd: list[str], cwd: Path, env: dict | None = None) -> tuple[int, str, str]:
    """Run command with UTF-8, safe on Windows GBK environments."""
    import os
    kwargs = dict(cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if env is not None:
        kwargs["env"] = env
    r = subprocess.run(cmd, **kwargs)
    return r.returncode, (r.stdout or ""), (r.stderr or "")


def find_root() -> Path:
    code, out, _ = run(["git", "rev-parse", "--show-toplevel"], Path.cwd())
    return Path(out.strip()) if code == 0 and out.strip() else Path.cwd()


def load_config(root: Path) -> dict:
    """Load quality-gates.yml from known locations, fall back to defaults."""
    candidates = [
        root / "config" / "quality-gates.yml",
        root / ".claude" / "skills" / "dev-ownership" / "config" / "quality-gates.yml",
    ]
    for p in [root] + list(root.parents)[:3]:
        for c in candidates:
            if c.exists():
                import yaml
                with open(c, encoding="utf-8") as f:
                    return yaml.safe_load(f)
    return {"gates": {}}


def detect_type(root: Path) -> str:
    """Autodetect project framework."""
    if (root / "manage.py").exists():     return "django"
    if (root / "go.mod").exists():         return "go"
    if (root / "Cargo.toml").exists():     return "rust"
    if (root / "package.json").exists():   return "node"
    if (root / "pyproject.toml").exists() or list(root.rglob("*.py")):
        return "python"
    return "unknown"


def prereqs(project_type: str) -> list[str]:
    """Return list of missing tool names."""
    missing = []
    tools = {
        "django": ["ruff", "mypy"],
        "python": ["ruff", "mypy"],
        "go":     ["golangci-lint"],
        "rust":   ["cargo"],
        "node":   ["eslint"],
    }
    for t in tools.get(project_type, []):
        if shutil.which(t) is None:
            missing.append(t)
    return missing


INSTALL_HINTS = {
    "ruff": "pip install ruff",
    "mypy": "pip install mypy",
    "bandit": "pip install bandit",
    "golangci-lint": "go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest",
    "eslint": "npm install -D eslint",
    "cargo": "curl https://sh.rustup.rs -sSf | sh",
}


# ── Gate runners ──────────────────────────────────────────────────────────

def gate_lint(root: Path, pt: str) -> bool:
    cmds = {
        "django": ["ruff", "check", "."],
        "python": ["ruff", "check", "."],
        "go":     ["golangci-lint", "run", "./..."],
        "node":   ["npx", "eslint", "."],
        "rust":   ["cargo", "clippy", "--", "-D", "warnings"],
    }
    cmd = cmds.get(pt)
    if not cmd: return True
    if shutil.which(cmd[0].split()[0]) is None:
        print(f"{YELLOW}[WARN]{NC} {cmd[0]} not installed")
        return False
    code, out, err = run(cmd, root)
    if code == 0:
        print(f"{GREEN}[PASS]{NC} lint ({cmd[0]}) — clean")
        return True
    print(f"{RED}[FAIL]{NC} lint ({cmd[0]}) — errors")
    print((err or out)[:400])
    return False


def gate_typecheck(root: Path, pt: str) -> bool:
    cmds = {
        "python": (["mypy", "--strict", "."], "mypy"),
        "django": (["mypy", "."], "mypy"),
        "go":     (["go", "vet", "./..."], "go"),
        "node":   (["npx", "tsc", "--noEmit"], "tsc"),
    }
    entry = cmds.get(pt)
    if not entry: return True
    cmd, tool = entry
    if shutil.which(tool) is None:
        print(f"{YELLOW}[WARN]{NC} {tool} not installed")
        return False
    code, out, err = run(cmd, root)
    if code == 0:
        print(f"{GREEN}[PASS]{NC} type check ({tool}) — clean")
        return True
    print(f"{RED}[FAIL]{NC} type check ({tool}) — errors")
    print((err or out)[:400])
    return False


def gate_security(root: Path, pt: str) -> bool:
    if pt in ("python", "django") and shutil.which("bandit"):
        code, out, err = run(["bandit", "-r", ".", "-ll", "-x", "*/migrations/*,*/tests/*"], root)
        if code == 0:
            print(f"{GREEN}[PASS]{NC} bandit — clean")
            return True
        print(f"{RED}[FAIL]{NC} bandit — issues")
        return False
    elif pt in ("python", "django"):
        print(f"{YELLOW}[WARN]{NC} bandit not installed ({INSTALL_HINTS['bandit']})")
    return True


def gate_tests(root: Path, pt: str, skip_slow: bool) -> tuple[bool, Optional[float]]:
    cmds = {
        "django": ["python", "manage.py", "test", "--verbosity=1"],
        "python": [sys.executable, "-m", "pytest", "--cov=.", "--cov-branch", "--cov-report=term", "-q"],
        "go":     ["go", "test", "-cover", "./..."],
        "node":   ["npm", "test"],
        "rust":   ["cargo", "test"],
    }
    cmd = cmds.get(pt)
    if not cmd:
        print(f"{YELLOW}[WARN]{NC} Unknown project type, skipping tests")
        return True, None

    # Auto-detect PYTHONPATH: if src/ exists, prepend it
    env = None
    if pt in ("python", "django") and (root / "src").is_dir():
        import os
        env = os.environ.copy()
        existing = env.get("PYTHONPATH", "")
        src_path = str(root / "src")
        env["PYTHONPATH"] = f"{src_path}{os.pathsep}{existing}" if existing else src_path

    print(f"  {(' '.join(cmd)[:80])}")
    code, out, err = run(cmd, root)
    coverage = None
    for line in (out + err).split("\n"):
        if "TOTAL" in line and "%" in line:
            for p in line.split():
                if "%" in p:
                    try: coverage = float(p.replace("%", ""))
                    except ValueError: pass

    if code == 0:
        print(f"  {GREEN}Tests: PASS{NC}")
        if coverage: print(f"  Coverage: {coverage}%")
        return True, coverage
    print(f"{RED}[FAIL]{NC} Tests failed")
    print((err or out)[-400:])
    return False, coverage


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    global EXIT_CODE
    parser = argparse.ArgumentParser(description="Quality Gate Runner v2")
    parser.add_argument("--skip-slow", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = find_root()
    config = load_config(root)
    pt = detect_type(root)
    results: dict[str, Any] = {"project_type": pt, "gates": {}}

    # Record every pre-commit run for --no-verify tracking
    import json as _json
    from pathlib import Path as _Path
    record_file = _Path.home() / ".claude" / "commit-records.json"
    record_file.parent.mkdir(parents=True, exist_ok=True)
    records = _json.loads(record_file.read_text()) if record_file.exists() else {"runs": []}
    records["runs"].append({
        "timestamp": __import__('datetime').datetime.now().isoformat(),
        "project": str(root.name),
        "cwd": str(root),
    })
    record_file.write_text(_json.dumps(records, indent=2))

    print(f"{BOLD}=== Quality Gates — {pt.upper()} ==={NC}")
    print(f"Root: {root}\n")

    # Phase 0: Prerequisites
    missing = prereqs(pt)
    if missing:
        print(f"{YELLOW}[PREREQ] Missing:{NC}")
        for t in missing:
            print(f"  - {t}: {INSTALL_HINTS.get(t, 'install ' + t)}")
        print()

    # Cross-phase detection
    code, staged, _ = run(["git", "diff", "--cached", "--name-only"], root)
    if staged:
        has_spec = any(k in staged for k in ["openspec/", "SPEC.md", "DESIGN.md"])
        has_src = any(staged.endswith(e) for e in [".py",".go",".ts",".js",".java",".rs"])
        if has_spec and has_src:
            print(f"{YELLOW}[WARN]{NC} Cross-phase: spec + src in same commit\n")

        # Search agent enforcement: proposal.md requires search-summary.md + cross-reference
        if "proposal.md" in staged or "design.md" in staged:
            summary = root / "openspec" / "changes" / "search-summary.md"
            cross_ref = root / "openspec" / "changes" / "search-cross-reference.md"
            if not summary.exists():
                print(f"{RED}[FAIL]{NC} search-summary.md missing: {summary}")
                print("  Spec/Design commit requires three-channel search first.")
                print("  Run: search agents (GitHub + Web + Papers) → search-summary.md")
                EXIT_CODE = 1
            if not cross_ref.exists():
                print(f"{RED}[FAIL]{NC} search-cross-reference.md missing: {cross_ref}")
                print("  AI must perform Phase 4 cross-referencing after agents complete.")
                print("  Read all 3 search reports, find contradictions/consensus/gaps, write cross-reference.")
                EXIT_CODE = 1
            elif "proposal.md" in staged:
                import os as _os2
                try:
                    s_mtime = _os2.path.getmtime(str(summary))
                    p_mtime = _os2.path.getmtime(str(root / "openspec" / "changes" / "proposal.md"))
                    if s_mtime < p_mtime:
                        print(f"{YELLOW}[WARN]{NC} search-summary.md older than proposal.md — re-run search?")
                except OSError:
                    pass

    # Feynman gate chain: each phase commit requires previous gate passed
    gate_dir = Path.home() / ".claude" / "gate-quota" / "gates"
    project_name = root.name
    if "design.md" in staged:
        gf = gate_dir / f"{project_name}-spec-passed.json"
        if not gf.exists():
            print(f"{RED}[FAIL]{NC} Feynman gate 'spec' not passed.")
            print(f"  To pass: ask AI 'Feynman spec questions' → answer 3 questions.")
            print(f"  After: AI records your answers and runs feynman-pass spec.")
            subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "gate-reminder.py"),
                          "--project", project_name, "--gate", "spec", "--action", "add"],
                         capture_output=True)
            EXIT_CODE = 1
    if any(f.endswith(".py") for f in staged.split("\n")):
        gf = gate_dir / f"{project_name}-design-passed.json"
        if not gf.exists():
            print(f"{YELLOW}[WARN]{NC} Feynman gate 'design' not recorded.")
            subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "gate-reminder.py"),
                          "--project", project_name, "--gate", "design", "--action", "add"],
                         capture_output=True)

    # Test quantity gate (Retrospect audit)
    if "retrospect" in staged.lower() if isinstance(staged, str) else False:
        # Count actual tests
        test_count = 0
        for f in root.rglob("tests/**/*.py"):
            test_count += f.read_text(encoding="utf-8", errors="replace").count("def test_")
        # Get threshold and level from gate state
        level = "P1"
        try:
            gs_file = Path.home()/".claude"/"gate-quota"/"gates"/f"{project_name}.json"
            if gs_file.exists():
                gs = _json.loads(gs_file.read_text())
                level = gs.get("level","P1")
        except: pass
        thresholds = {"P0":20,"P1":12,"P2":0}
        minimum = thresholds.get(level, 12)
        if test_count < minimum:
            print(f"{RED}[FAIL]{NC} Test count {test_count} < minimum {minimum} (level: {level})")
            print(f"  Add {minimum - test_count} more tests before Retrospect commit.")
            EXIT_CODE = 1
        else:
            print(f"{GREEN}[TEST COUNT]{NC} {test_count} tests >= {minimum} minimum")

        # Characterization test C1/C2/C3 gate
        char_log = root / "openspec" / "changes" / "char-test-log.json"
        c1 = c2 = c3 = 0
        if char_log.exists():
            try:
                log_data = _json.loads(char_log.read_text())
                for entry in log_data.get("entries", []):
                    if entry.get("level") == "C1": c1 += 1
                    elif entry.get("level") == "C2": c2 += 1
                    elif entry.get("level") == "C3": c3 += 1
            except: pass
        char_thresholds = {"P0":{"C1":3,"C2":2,"C3":1},"P1":{"C1":2,"C2":1,"C3":1},"P2":{"C1":0,"C2":0,"C3":0}}
        ct = char_thresholds.get(level, {"C1":0,"C2":0,"C3":0})
        missing = []
        if c1 < ct["C1"]: missing.append(f"C1({c1}/{ct['C1']})")
        if c2 < ct["C2"]: missing.append(f"C2({c2}/{ct['C2']})")
        if c3 < ct["C3"]: missing.append(f"C3({c3}/{ct['C3']})")
        if missing:
            print(f"{RED}[FAIL]{NC} Characterization tests incomplete: {', '.join(missing)}")
            print(f"  Complete required C1/C2/C3 sessions before Retrospect commit.")
            EXIT_CODE = 1
        else:
            print(f"{GREEN}[CHAR TEST]{NC} C1={c1}/{ct['C1']} C2={c2}/{ct['C2']} C3={c3}/{ct['C3']}")
    if "design.md" not in staged and "proposal.md" not in staged:
        # Not spec/design — check if we're in Review phase
        if any("test_" in f or f.endswith(".py") for f in staged.split("\n")):
            mutation_fixes = root / "openspec" / "changes" / "mutation-fixes.md"
            # Only warn — don't block (mutation test may have no survivors)
            if mutation_fixes.exists():
                import os as _os3
                mtime = _os3.path.getmtime(str(mutation_fixes))
                age_hours = (__import__('time').time() - mtime) / 3600
                if age_hours > 24:
                    print(f"{YELLOW}[WARN]{NC} mutation-fixes.md is {age_hours:.0f}h old — may need refresh")

    # Rule 11: Format vs Logic mix detection
    if pt in ("python", "django", "go", "rust"):
        _, staged_diff, _ = run(["git", "diff", "--cached", "--unified=0"], root)
        if staged_diff:
            has_format_only = False
            has_logic = False
            for line in staged_diff.split("\n"):
                if (line.startswith("+") or line.startswith("-")) and not line.startswith("+++") and not line.startswith("---"):
                    stripped = line[1:].strip()
                    original = line[1:]
                    if stripped == original.strip() and stripped != original:
                        has_format_only = True
                    elif stripped and not stripped.startswith("#"):
                        has_logic = True
            if has_format_only and has_logic:
                print(f"{YELLOW}[FAIL]{NC} Rule 11: Formatting and logic changes mixed in same commit.")
                print("  Split: style(scope): ruff fix → feat(scope): logic change")
                EXIT_CODE = 1

    # Rule 10: Code move vs modify detection
    if pt in ("python", "django", "go", "rust"):
        _, rename_lines, _ = run(["git", "diff", "--cached", "--name-status"], root)
        for rline in rename_lines.split("\n"):
            if rline.startswith("R"):
                parts = rline.split("\t")
                if len(parts) >= 3:
                    old_f, new_f = parts[1], parts[2]
                    _, rename_diff, _ = run(["git", "diff", "--cached", "--", new_f], root)
                    added = [l for l in rename_diff.split("\n") if l.startswith("+") and not l.startswith("+++")]
                    removed = [l for l in rename_diff.split("\n") if l.startswith("-") and not l.startswith("---")]
                    if added and removed:
                        print(f"{YELLOW}[WARN]{NC} Rule 10: {old_f} → {new_f} has move AND modify.")
                        print("  Consider: 1st commit = pure move, 2nd commit = modifications")

    # Gates
    for gate_name, gate_fn in [
        ("lint", lambda: gate_lint(root, pt)),
        ("type", lambda: gate_typecheck(root, pt)),
        ("security", lambda: gate_security(root, pt)),
    ]:
        print(f"{BOLD}--- {gate_name} ---{NC}")
        ok = gate_fn()
        if not ok: EXIT_CODE = 1
        results["gates"][gate_name] = "pass" if ok else "fail"
        print()

    # Tests
    print(f"{BOLD}--- tests ---{NC}")
    test_ok, cov = gate_tests(root, pt, args.skip_slow)
    if not test_ok: EXIT_CODE = 1
    results["gates"]["tests"] = "pass" if test_ok else "fail"
    if cov is not None:
        threshold = config.get("gates", {}).get("test_suite", {}).get("branch_coverage", {}).get("threshold", 0.90)
        results["gates"]["coverage"] = cov
        if cov < threshold * 100:
            print(f"{RED}[FAIL]{NC} Coverage {cov}% < {threshold*100}%")
            EXIT_CODE = 1

    # Cognitive Debt Ratio — auto-run from measurement pyramid
    cdr_threshold = config.get("gates", {}).get("cognitive_tracking", {}).get("cdr", {}).get("threshold", 0.15)
    cdr_script = root.parent / ".claude" / "skills" / "dev-ownership" / "scripts" / "cdr-sr-tracker.py"
    if not cdr_script.exists():
        # Try skill repo location
        import os as _os
        for candidate in [
            Path(_os.path.expanduser("~/.claude/skills/dev-ownership/scripts/cdr-sr-tracker.py")),
            Path(_os.path.expanduser("~/dev-ownership-skill/scripts/cdr-sr-tracker.py")),
        ]:
            if candidate.exists():
                cdr_script = candidate
                break
    if cdr_script.exists():
        code, out, err = run([sys.executable, str(cdr_script), "--project-root", str(root), "--output", "json"], root)
        if code == 0:
            try:
                cdr_data = json.loads(out)
                cdr = cdr_data.get("cdr", 0.0)
                if cdr > cdr_threshold:
                    print(f"{YELLOW}[CDR] {cdr:.2%}{NC} (threshold ≤{cdr_threshold:.0%}) — cognitive debt exceeds limit")
                else:
                    print(f"{GREEN}[CDR] {cdr:.2%}{NC} — within threshold")
            except json.JSONDecodeError:
                pass
    else:
        pass  # CDR tracker not available — skip silently

    if args.json:
        print(json.dumps(results, indent=2))

    print(f"\n{BOLD}{GREEN if EXIT_CODE == 0 else RED}{'PASS' if EXIT_CODE == 0 else 'FAIL'}{NC}")
    sys.exit(EXIT_CODE)


if __name__ == "__main__":
    main()
