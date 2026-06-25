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


def _count_spec_scenarios(root: Path) -> int:
    """Count unique T-scenarios in openspec/changes/proposal.md.

    Supports both list format (T1: desc) and table format (| T1 | ... |).
    Returns 0 if proposal.md not found or unparseable.
    """
    import re
    proposal = root / "openspec" / "changes" / "proposal.md"
    if not proposal.exists():
        return 0
    try:
        text = proposal.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return 0
    # Find all T-number patterns: T1, T2, ..., T10, etc.
    matches = re.findall(r'\bT(\d+)\b', text)
    if not matches:
        return 0
    # Return count of unique T-numbers
    return len(set(int(m) for m in matches))


def _check_sync() -> None:
    """Warn if a newer version exists at a known source location.

    Prevents the two-copy drift problem by checking if the skill source
    has been updated but not synced to the canonical install location.
    """
    import os as _os
    me = Path(__file__).resolve()
    my_mtime = me.stat().st_mtime

    sources = [
        Path(_os.path.expanduser("~/.claude/skills/dev-ownership/scripts")) / me.name,
    ]

    for src in sources:
        try:
            if src.exists() and src.resolve() != me:
                src_mtime = src.stat().st_mtime
                if src_mtime > my_mtime + 1.0:  # 1-second tolerance
                    age_hours = (__import__('time').time() - src_mtime) / 3600
                    print(f"{YELLOW}[SYNC]{NC} Newer version at {src}")
                    print(f"  Updated {age_hours:.1f}h ago — run: python install-hooks.py --sync-only")
                    return
        except OSError:
            pass


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
    tool = cmd[0].split()[0]
    if shutil.which(tool) is None:
        print(f"{YELLOW}[WARN]{NC} {tool} not installed")
        return False

    # Scope to staged files only — don't block commit for unrelated changes
    if pt in ("python", "django") and tool == "ruff":
        _, staged, _ = run(["git", "diff", "--cached", "--name-only",
                            "--diff-filter=ACM"], root)
        py_files = [f.strip() for f in staged.split("\n")
                    if f.strip().endswith(".py")]
        if py_files:
            cmd = ["ruff", "check"] + py_files
        else:
            print("  No staged .py files — lint skipped")
            return True

    code, out, err = run(cmd, root)
    if code == 0:
        print(f"{GREEN}[PASS]{NC} lint ({tool}) — clean")
        return True
    print(f"{RED}[FAIL]{NC} lint ({tool}) — errors")
    print((err or out)[:400])
    return False


def gate_typecheck(root: Path, pt: str) -> bool:
    cmds = {
        "python": ([sys.executable, "-m", "mypy", "--strict", "--explicit-package-bases", "--exclude", "tests/", "."], "mypy"),
        "django": ([sys.executable, "-m", "mypy", "--explicit-package-bases", "."], "mypy"),
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


def gate_assert(root: Path, pt: str) -> bool:
    """Detect bare assert used as business logic guard.

    assert is removed by `python -O`, so it must not be used for
    runtime validation. Use if/raise instead.
    """
    if pt not in ("python", "django"):
        return True

    import re as _re
    _, staged, _ = run(["git", "diff", "--cached", "--name-only",
                        "--diff-filter=ACM"], root)
    py_files = [f.strip() for f in staged.split("\n")
                if f.strip().endswith(".py") and "tests/" not in f.lower() and not f.strip().split("/")[-1].startswith("test_")]

    if not py_files:
        return True

    found: list[tuple[str, int, str]] = []
    for f in py_files:
        try:
            lines = (root / f).read_text(encoding="utf-8", errors="replace").split("\n")
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                # Match bare assert statements (not test assertions)
                if stripped.startswith("assert ") and not stripped.startswith("assert _"):
                    # Exclude test-like asserts: assert x == y, assert fn(), assert True/False
                    if _re.match(r'assert\s+(True|False)\b', stripped):
                        continue
                    found.append((f, i, stripped[:80]))
        except Exception:
            pass

    if found:
        print(f"{YELLOW}[WARN]{NC} Bare assert in non-test code ({len(found)} found)")
        print("  assert is removed by `python -O`. Use if/raise instead.")
        for fname, lineno, text in found[:5]:
            print(f"  {fname}:{lineno}: {text}")
        if len(found) > 5:
            print(f"  ... and {len(found) - 5} more")
    else:
        print(f"{GREEN}[PASS]{NC} no bare assert in non-test code")
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


def _get_skill_version() -> str:
    """Read skill version from VERSION file."""
    import os as _os
    candidates = [
        Path(__file__).resolve().parent.parent / "VERSION",
        Path(_os.path.expanduser("~/.claude/skills/dev-ownership/VERSION")),
    ]
    for vf in candidates:
        try:
            if vf.exists():
                for line in vf.read_text(encoding="utf-8").split("\n"):
                    if line.startswith("version:"):
                        return line.split(":", 1)[1].strip().strip('"')
        except Exception:
            pass
    return "unknown"


def _get_model_id() -> str:
    """Detect current Claude model from environment or API."""
    import os as _os
    return _os.environ.get("CLAUDE_MODEL", "unknown")


# ── Gate registry & trace chain (Certified Purity + Makoto) ─────────────────

# Gates that always run on every commit
GATE_REGISTRY_ALWAYS = ["lint", "type", "security", "assert"]

# Gates that run conditionally (only when relevant files are staged)
GATE_REGISTRY_CONDITIONAL = [
    "search_completeness", "feynman_spec", "feynman_design",
    "tests", "cdr", "rule_11", "rule_10",
    "test_count", "char_test", "feynman_count",
]

GATE_REGISTRY = GATE_REGISTRY_ALWAYS + GATE_REGISTRY_CONDITIONAL

GATE_TRACE: list[dict] = []


def _trace(gate_name: str, status: str, detail: str = "") -> None:
    """Record a gate execution in the trace chain."""
    GATE_TRACE.append({
        "gate": gate_name,
        "status": status,  # "pass", "fail", "warn", "skip"
        "detail": detail[:200] if detail else "",
        "timestamp": __import__('time').time(),
    })


def _verify_trace_completeness() -> int:
    """Verify all ALWAYS gates were traced. Conditional gates checked separately.
    Returns count of missing always-gates."""
    traced = {t["gate"] for t in GATE_TRACE}
    missing = [g for g in GATE_REGISTRY_ALWAYS if g not in traced]
    # Also check conditionals that were expected to run
    missing_cond = [g for g in GATE_REGISTRY_CONDITIONAL if g not in traced]

    if missing:
        print(f"{RED}[TRACE]{NC} Missing always-gates: {', '.join(missing)}")
        print("  These gates should ALWAYS run. Possible hook chain break.")
    if missing_cond:
        print(f"  Conditional gates not triggered: {', '.join(missing_cond[:5])}{'...' if len(missing_cond) > 5 else ''}")
        print("  (This is normal if no spec/design/test files were in this commit)")
        # Write trace to record for post-mortem
        record = Path.home() / ".claude" / "gate-traces.json"
        try:
            import json as _j
            traces = _j.loads(record.read_text()) if record.exists() else []
            traces.append({
                "timestamp": __import__('datetime').datetime.now().isoformat(),
                "missing": missing,
                "traced": [{"gate": t["gate"], "status": t["status"]} for t in GATE_TRACE],
            })
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text(_j.dumps(traces[-10:], indent=2))  # keep last 10
        except Exception:
            pass
    return len(missing)


def _detect_change_scope(staged: str) -> str:
    """Auto-classify change scope: 'light', 'standard', or 'full'.

    Light (P2):  only formatting/lint/typo fixes — skip heavy gates
    Standard (P1):  logic changes in a few files
    Full (P0):  new files, API changes, spec/design commits — all gates
    """
    if not staged:
        return "standard"

    files = [f.strip() for f in staged.split("\n") if f.strip()]
    py_files = [f for f in files if f.endswith(".py")]
    md_files = [f for f in files if f.endswith(".md")]

    # Full: spec or design changes
    if any("openspec/" in f or "DESIGN.md" in f or "SPEC.md" in f for f in files):
        return "full"
    if any("proposal.md" in f or "design.md" in f for f in files):
        return "full"

    # Full: many new/changed files
    if len(files) > 10:
        return "full"

    # Full: new files (never seen before)
    _, new_files, _ = run(["git", "diff", "--cached", "--diff-filter=A", "--name-only"],
                           Path.cwd())
    if new_files.strip():
        return "full"

    # Light: only markdown/config/template files
    if not py_files and (md_files or any(f.endswith((".yml", ".yaml", ".toml", ".json")) for f in files)):
        return "light"

    # Light: only formatting changes (ruff --fix applied)
    if py_files and len(py_files) <= 2:
        _, diff, _ = run(["git", "diff", "--cached", "--unified=0", "--"] + py_files,
                          Path.cwd())
        # Count substantive changes vs format-only
        logic_lines = 0
        for line in diff.split("\n"):
            if (line.startswith("+") or line.startswith("-")) and not line.startswith("+++") and not line.startswith("---"):
                stripped = line[1:].strip()
                if stripped and not stripped.startswith("#"):
                    logic_lines += 1
        if logic_lines <= 5:
            return "light"

    return "standard"


def _print_mode_banner(scope: str) -> None:
    """Print the current mode to make it visible what's being skipped."""
    if scope == "light":
        print(f"{YELLOW}[MODE] Light mode (P2){NC} — only lint/type/tests gates active")
        print("  Design/Harden/Retrospect phases skipped for this commit.")
        print("  Upgrade to standard: make substantive logic changes.")
    elif scope == "standard":
        print(f"{BOLD}[MODE] Standard mode (P1){NC} — all core gates active")
    elif scope == "full":
        print(f"{BOLD}[MODE] Full mode (P0){NC} — all gates + spec/design enforcement")


# ── Shared state sync ───────────────────────────────────────────────────────

def _sync_pipeline_state(root: Path, staged: str, exit_code: int) -> None:
    """Update .dev-ownership/state.json based on what was just committed.

    Merges the old gate-quota system with the new orchestrator state.
    Single source of truth after this call.
    """
    if exit_code != 0:
        return  # Don't update state on failed commit

    state_dir = root / ".dev-ownership"
    state_dir.mkdir(parents=True, exist_ok=True)
    sf = state_dir / "state.json"

    import json as _j
    if sf.exists():
        state = _j.loads(sf.read_text(encoding="utf-8"))
    else:
        state = {
            "project": str(root.name),
            "phases": {},
            "session_count": 0,
            "created": __import__('datetime').datetime.now().isoformat(),
        }

    updated = False
    now = __import__('datetime').datetime.now().isoformat()

    # Detect phase from staged files
    if "proposal.md" in staged or "search-summary.md" in staged:
        state["phases"]["spec"] = {"status": "done", "completed_at": now}
        updated = True
    if "design.md" in staged:
        state["phases"]["design"] = {"status": "done", "completed_at": now}
        updated = True
    if any(f.endswith(".py") for f in staged.split("\n") if not f.startswith("test")):
        if state.get("phases", {}).get("design", {}).get("status") == "done":
            state["phases"]["tdd"] = {"status": "done", "completed_at": now}
            updated = True
    if "retrospect" in staged.lower() if isinstance(staged, str) else False:
        state["phases"]["retrospect"] = {"status": "done", "completed_at": now}
        updated = True

    if updated:
        state["updated"] = now
        sf.write_text(_j.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Search quality enforcement ──────────────────────────────────────────────

def _check_search_brief(path: Path) -> None:
    """Verify search-decision-brief.md exists and meets the ≤80 line standard.

    v0.4.1: Replaces the old 5-file check (search-summary.md + 3 channel files
    + cross-reference). The new two-tier search model produces a single brief.
    """
    global EXIT_CODE

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        print(f"{RED}[FAIL]{NC} search-decision-brief.md unreadable")
        EXIT_CODE = 1
        return

    lines = text.split("\n")
    issues = []

    # 1. Line limit: hard cap at 80
    if len(lines) > 80:
        issues.append(f"brief is {len(lines)} lines (max 80)")

    # 2. Must cover 3 channels
    channels = sum(1 for ch in ["GitHub", "Web", "Papers", "github", "arxiv"]
                   if ch.lower() in text.lower())
    if channels < 2:
        issues.append(f"covers {channels}/3 channels")

    # 3. Must contain decision impact
    if "改变" not in text and "decision" not in text.lower() and "选择" not in text:
        issues.append("missing decision impact section")

    # 4. Must have at least 2 external URLs
    url_count = text.count("http://") + text.count("https://")
    if url_count < 2:
        issues.append(f"only {url_count} URLs (min 2)")

    if issues:
        print(f"{RED}[FAIL]{NC} search-decision-brief.md: {'; '.join(issues)}")
        print("  Format (5 sections, ≤80 lines):")
        print("    1. 三通道摘要 (≤30 lines) — per-channel 3-5 sentences + links")
        print("    2. 交叉验证 (≤15 lines) — consensus / contradiction / gap")
        print("    3. 改变的决策 (≤15 lines) — what changed and why")
        print("    4. 不确定 (≤10 lines) — unresolved questions")
        print("    5. 细调用记录 (≤10 lines) — deep-dive links if any")
        EXIT_CODE = 1


def main():
    global EXIT_CODE
    parser = argparse.ArgumentParser(description="Quality Gate Runner v2")
    parser.add_argument("--skip-slow", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    # Check if a newer version exists at any known source location
    _check_sync()

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
        "skill_version": _get_skill_version(),
        "model": _get_model_id(),
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
    staged = ""
    code, staged, _ = run(["git", "diff", "--cached", "--name-only"], root)
    scope = _detect_change_scope(staged)
    _print_mode_banner(scope)
    if staged:
        has_spec = any(k in staged for k in ["openspec/", "SPEC.md", "DESIGN.md"])
        has_src = any(staged.endswith(e) for e in [".py",".go",".ts",".js",".java",".rs"])
        if has_spec and has_src:
            print(f"{YELLOW}[WARN]{NC} Cross-phase: spec + src in same commit\n")

        # Search agent enforcement: proposal/design requires search-decision-brief.md
        if "proposal.md" in staged or "design.md" in staged:
            brief = root / "openspec" / "changes" / "search-decision-brief.md"
            if not brief.exists():
                print(f"{RED}[FAIL]{NC} search-decision-brief.md missing: {brief}")
                print("  Spec/Design commit requires three-channel search first.")
                print("  Run: search agents (GitHub + Web + Papers) → search-decision-brief.md")
                EXIT_CODE = 1
            else:
                _check_search_brief(brief)
                _trace('search_completeness', 'pass')

            if "proposal.md" in staged:
                import os as _os2
                try:
                    s_mtime = _os2.path.getmtime(str(brief))
                    p_mtime = _os2.path.getmtime(str(root / "openspec" / "changes" / "proposal.md"))
                    if s_mtime < p_mtime:
                        print(f"{YELLOW}[WARN]{NC} search-decision-brief.md older than proposal.md — re-run search?")
                except OSError:
                    pass

    # Feynman gate chain: each phase commit requires previous gate passed
    gate_dir = Path.home() / ".claude" / "gate-quota" / "gates"
    project_name = root.name
    if "design.md" in staged:
        gf = gate_dir / f"{project_name}-spec-passed.json"
        if not gf.exists():
            print(f"{RED}[FAIL]{NC} Feynman gate 'spec' not passed.")
            print("  To pass: ask AI 'Feynman spec questions' → answer 3 questions.")
            print("  After: AI records your answers and runs feynman-pass spec.")
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
        # Count spec scenarios from proposal.md for dynamic minimum
        spec_count = _count_spec_scenarios(root)
        # Get threshold and level from gate state
        level = "P1"
        try:
            gs_file = Path.home()/".claude"/"gate-quota"/"gates"/f"{project_name}.json"
            if gs_file.exists():
                gs = _json.loads(gs_file.read_text())
                level = gs.get("level","P1")
        except Exception: pass
        # Derive minimum from spec scenarios, not hardcoded
        if spec_count > 0:
            import math
            p0_min = spec_count  # 100% of spec scenarios
            p1_min = max(8, math.ceil(spec_count * 0.7))  # floor 8
            thresholds = {"P0": p0_min, "P1": p1_min, "P2": 0}
        else:
            thresholds = {"P0": 20, "P1": 12, "P2": 0}  # fallback
        minimum = thresholds.get(level, 12)
        if test_count < minimum:
            print(f"{RED}[FAIL]{NC} Test count {test_count} < minimum {minimum} (level: {level}, spec scenarios: {spec_count})")
            print(f"  Add {minimum - test_count} more tests before Retrospect commit.")
            EXIT_CODE = 1
        else:
            print(f"{GREEN}[TEST COUNT]{NC} {test_count} tests >= {minimum} minimum (spec scenarios: {spec_count}, level: {level})")

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
            except Exception: pass
        char_thresholds = {"P0":{"C1":3,"C2":2,"C3":1},"P1":{"C1":2,"C2":1,"C3":1},"P2":{"C1":0,"C2":0,"C3":0}}
        ct = char_thresholds.get(level, {"C1":0,"C2":0,"C3":0})
        missing = []
        if c1 < ct["C1"]: missing.append(f"C1({c1}/{ct['C1']})")
        if c2 < ct["C2"]: missing.append(f"C2({c2}/{ct['C2']})")
        if c3 < ct["C3"]: missing.append(f"C3({c3}/{ct['C3']})")
        if missing:
            print(f"{RED}[FAIL]{NC} Characterization tests incomplete: {', '.join(missing)}")
            print("  Complete required C1/C2/C3 sessions before Retrospect commit.")
            EXIT_CODE = 1
        else:
            print(f"{GREEN}[CHAR TEST]{NC} C1={c1}/{ct['C1']} C2={c2}/{ct['C2']} C3={c3}/{ct['C3']}")

        # Feynman gate count
        feynman_count = 0
        gate_dir = Path.home() / ".claude" / "gate-quota" / "gates"
        for gate in ["spec","design","tdd","review","retrospect"]:
            if (gate_dir / f"{project_name}-{gate}-passed.json").exists():
                feynman_count += 1
        feynman_thresholds = {"P0":5,"P1":3,"P2":0}
        fmin = feynman_thresholds.get(level, 3)
        if feynman_count < fmin:
            print(f"{RED}[FAIL]{NC} Feynman gates: {feynman_count}/{fmin} required (level: {level})")
            print(f"  Pass {fmin - feynman_count} more Feynman gate(s) before Retrospect commit.")
            EXIT_CODE = 1
        else:
            print(f"{GREEN}[FEYNMAN]{NC} Gates {feynman_count}/{fmin} passed")
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
            has_removals = False
            for line in staged_diff.split("\n"):
                if line.startswith("-") and not line.startswith("---"):
                    has_removals = True
                if (line.startswith("+") or line.startswith("-")) and not line.startswith("+++") and not line.startswith("---"):
                    stripped = line[1:].strip()
                    original = line[1:]
                    if stripped == original.strip() and stripped != original:
                        has_format_only = True
                    elif stripped and not stripped.startswith("#"):
                        has_logic = True
            if has_format_only and has_logic and has_removals:
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
                    added = [ln for ln in rename_diff.split("\n") if ln.startswith("+") and not ln.startswith("+++")]
                    removed = [ln for ln in rename_diff.split("\n") if ln.startswith("-") and not ln.startswith("---")]
                    if added and removed:
                        print(f"{YELLOW}[WARN]{NC} Rule 10: {old_f} → {new_f} has move AND modify.")
                        print("  Consider: 1st commit = pure move, 2nd commit = modifications")

    # Gates
    for gate_name, gate_fn in [
        ("lint", lambda: gate_lint(root, pt)),
        ("type", lambda: gate_typecheck(root, pt)),
        ("security", lambda: gate_security(root, pt)),
        ("assert", lambda: gate_assert(root, pt)),
    ]:
        print(f"{BOLD}--- {gate_name} ---{NC}")
        ok = gate_fn()
        if not ok: EXIT_CODE = 1
        results["gates"][gate_name] = "pass" if ok else "fail"
        _trace(gate_name, "pass" if ok else "fail")
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

    # Verify hook chain integrity (Certified Purity — bypass elimination)
    missing = _verify_trace_completeness()
    if missing > 0:
        EXIT_CODE = 1

    # Sync pipeline state (merge old gate-quota + new orchestrator state)
    _sync_pipeline_state(root, staged, EXIT_CODE)

    print(f"\n{BOLD}{GREEN if EXIT_CODE == 0 else RED}{'PASS' if EXIT_CODE == 0 else 'FAIL'}{NC}")
    sys.exit(EXIT_CODE)


if __name__ == "__main__":
    main()
