#!/usr/bin/env python3
"""dev-ownership.py — Central orchestrator (nervous system) for the dev-ownership skill.

Pattern: Just (CLI shell) + doit (DAG brain) + Burr (state machine tracking).
Based on: VMAO Plan-Execute-Verify-Replan loop, EBuddy FSM recipes,
Nadeem & Malik centralized orchestration (5-6x faster debugging).

Usage:
  python dev-ownership.py status              # Show current pipeline state
  python dev-ownership.py check               # Run quality gates (pre-commit)
  python dev-ownership.py harden [--full]    # Run mutation testing
  python dev-ownership.py install             # Install git hooks
  python dev-ownership.py self-test           # Run smoke + integration + self-gate
  python dev-ownership.py sync                # Sync scripts to canonical
  python dev-ownership.py rollback [VERSION]  # Rollback to previous version

State: All phase state tracked in .dev-ownership/state.json within the project.
Each phase validates the previous phase before executing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

SKILL_ROOT = Path(__file__).resolve().parent.parent  # scripts/ -> skill root
SCRIPTS = SKILL_ROOT / "scripts"
CANONICAL = Path.home() / ".claude" / "skills" / "dev-ownership"

# Phase dependency DAG (doit pattern)
PHASE_ORDER = ["init", "spec", "design", "tdd", "review", "harden", "retrospect"]
REQUIRES = {
    "spec": [],
    "design": ["spec"],
    "tdd": ["design"],
    "review": ["tdd"],
    "harden": ["review"],
    "retrospect": ["harden"],
}


# ── Shared state (Burr pattern) ─────────────────────────────────────────────

def _state_dir(project_root: Path) -> Path:
    d = project_root / ".dev-ownership"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_state(project_root: Path) -> dict:
    sf = _state_dir(project_root) / "state.json"
    if sf.exists():
        return json.loads(sf.read_text(encoding="utf-8"))
    return {
        "project": str(project_root.name),
        "phases": {},
        "session_count": 0,
        "created": datetime.now().isoformat(),
    }


def _save_state(project_root: Path, state: dict) -> None:
    state["updated"] = datetime.now().isoformat()
    sf = _state_dir(project_root) / "state.json"
    sf.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _phase_done(project_root: Path, phase: str, details: dict | None = None) -> None:
    """Mark a phase as completed in the state file."""
    state = _load_state(project_root)
    state["phases"][phase] = {
        "status": "done",
        "completed_at": datetime.now().isoformat(),
        "details": details or {},
    }
    _save_state(project_root, state)


def _check_prereqs(project_root: Path, phase: str) -> bool:
    """Check that all prerequisite phases are done. Returns True if OK."""
    state = _load_state(project_root)
    missing = []
    for prereq in REQUIRES.get(phase, []):
        if prereq not in state.get("phases", {}) or state["phases"][prereq].get("status") != "done":
            missing.append(prereq)
    if missing:
        print(f"[BLOCKED] Phase '{phase}' requires: {', '.join(missing)}")
        print(f"  Run 'python dev-ownership.py status' to see pipeline state.")
        return False
    return True


# ── Command runners (Just pattern) ──────────────────────────────────────────

def _run_script(name: str, *args: str, cwd: Path | None = None, timeout: int = 300) -> int:
    """Run a skill script and return its exit code."""
    script = SCRIPTS / name
    cmd = [sys.executable, str(script)] + list(args)
    r = subprocess.run(cmd, cwd=str(cwd) if cwd else str(SKILL_ROOT), timeout=timeout)
    return r.returncode


def cmd_status(project_root: Path) -> None:
    """Show current pipeline state — which phases are done, which are pending."""
    state = _load_state(project_root)
    print(f"Project: {state['project']}")
    print(f"Sessions: {state.get('session_count', 0)}")
    print()

    for phase in PHASE_ORDER:
        info = state.get("phases", {}).get(phase, {})
        status = info.get("status", "pending")
        icon = {"done": "[OK]", "pending": "[  ]", "failed": "[XX]"}.get(status, "[??]")
        detail = ""
        if info.get("completed_at"):
            detail = f" — {info['completed_at'][:19]}"
        print(f"  {icon} {phase:12s}{detail}")

    # Show meta-state
    print()
    print(f"Skill version: {_skill_version()}")
    print(f"Installed hooks: {'yes' if (project_root / '.git' / 'hooks' / 'pre-commit').exists() else 'no'}")


def cmd_check(project_root: Path) -> int:
    """Run quality gates (pre-commit-check)."""
    print("Running quality gates...")
    return _run_script("pre-commit-check.py", "--skip-slow", cwd=project_root)


def cmd_harden(project_root: Path, full: bool = False) -> int:
    """Run mutation testing (Harden phase)."""
    if not _check_prereqs(project_root, "harden"):
        return 1

    src_dir = project_root / "src"
    if not src_dir.exists():
        # Try to find source directory
        candidates = list(project_root.glob("src/*"))
        if candidates:
            src_dir = candidates[0].parent
        else:
            print("[ERROR] No src/ directory found")
            return 1

    mode = "f" if full else "s"
    n = 50 if full else 20
    print(f"Running mutation testing ({mode} mode, n={n})...")
    exit_code = _run_script(
        "mutation-engine.py",
        "--src", str(src_dir),
        "--test-cmd", f"{sys.executable} -m pytest tests/ -q",
        "--n", str(n), "--mode", mode, "--json",
        cwd=project_root, timeout=600,
    )
    if exit_code in (0, 1):  # 0=clean, 1=mutants found, both OK
        _phase_done(project_root, "harden")
        return 0
    return exit_code


def cmd_install(project_root: Path) -> int:
    """Install git hooks into project."""
    print("Installing dev-ownership hooks...")
    return _run_script("install-hooks.py", "--project-root", str(project_root), cwd=SKILL_ROOT)


def cmd_self_test() -> int:
    """Run smoke + integration + self-gate (dogfooding)."""
    print("=== Self-Test Pipeline ===\n")

    # L1: Smoke
    print("[L1] Smoke test...")
    r = _run_script("smoke_test.py", cwd=SKILL_ROOT)
    if r != 0:
        print("[FAIL] Smoke test failed")
        return 1
    print("[PASS] Smoke test\n")

    # L2: Integration
    print("[L2] Integration tests...")
    r = _run_script("test_scripts.py", cwd=SKILL_ROOT)
    if r != 0:
        print("[FAIL] Integration tests failed")
        return 1
    print("[PASS] Integration tests\n")

    # L3: Self-gate
    print("[L3] Self-gate...")
    gate_script = SCRIPTS / "self-gate.sh"
    if gate_script.exists():
        r = subprocess.run(["bash", str(gate_script)], cwd=str(SKILL_ROOT)).returncode
        if r != 0:
            print("[FAIL] Self-gate failed")
            return 1
        print("[PASS] Self-gate")

    print("\n=== Self-Test PASSED ===")
    return 0


def cmd_sync() -> int:
    """Sync scripts from source to canonical location."""
    print("Syncing scripts...")
    return _run_script("install-hooks.py", "--sync-only", cwd=SKILL_ROOT)


def cmd_rollback(version: str | None = None) -> int:
    """Rollback to a previous script version."""
    args = ["--rollback"]
    if version:
        args.append(version)
    return _run_script("install-hooks.py", *args, cwd=SKILL_ROOT)


def cmd_watch() -> int:
    """Start file watcher for auto-self-test."""
    print("Starting file watcher (Ctrl+C to stop)...")
    return _run_script("watch_gate.py", cwd=SKILL_ROOT)


def _skill_version() -> str:
    vf = SKILL_ROOT / "VERSION"
    if vf.exists():
        for line in vf.read_text(encoding="utf-8").split("\n"):
            if line.startswith("version:"):
                return line.split(":", 1)[1].strip().strip('"')
    return "unknown"


def cmd_bump(level: str) -> int:
    """Bump version number atomically across VERSION + SKILL.md.

    Based on bump-my-version / Commitizen pattern: single command updates
    all version-bearing files atomically, no manual sync.

    Levels: patch (0.4.1→0.4.2), minor (0.4.1→0.5.0), major (0.4.1→1.0.0)
    """
    import yaml
    import re
    from datetime import date

    if level not in ("patch", "minor", "major"):
        print(f"[ERROR] Unknown bump level: {level}. Use: patch, minor, major")
        return 1

    # Parse current version
    vf = SKILL_ROOT / "VERSION"
    if not vf.exists():
        print("[ERROR] VERSION file not found")
        return 1

    data = yaml.safe_load(vf.read_text(encoding="utf-8"))
    current = str(data["version"])
    parts = [int(x) for x in current.split(".")]
    if len(parts) != 3:
        print(f"[ERROR] Version '{current}' is not semver (MAJOR.MINOR.PATCH)")
        return 1

    # Bump
    if level == "patch":
        parts[2] += 1
    elif level == "minor":
        parts[1] += 1
        parts[2] = 0
    elif level == "major":
        parts[0] += 1
        parts[1] = 0
        parts[2] = 0
    new_version = f"{parts[0]}.{parts[1]}.{parts[2]}"
    today = date.today().isoformat()

    # 1. Update VERSION
    data["version"] = new_version
    data["last_updated"] = today
    data["changelog"].insert(0, {
        "version": new_version,
        "date": today,
        "changes": ["(fill in changes before committing)"],
    })
    vf.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False,
                            sort_keys=False), encoding="utf-8")

    # 2. Update SKILL.md frontmatter
    skill_md = SKILL_ROOT / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")
    content = re.sub(
        r'^version:\s*[\d.]+',
        f'version: {new_version}',
        content, count=1, flags=re.MULTILINE
    )
    skill_md.write_text(content, encoding="utf-8")

    print(f"Bumped: {current} → {new_version} ({level})")
    print(f"  Updated: VERSION, SKILL.md")
    print(f"  Next: fill in changelog, then git commit + tag v{new_version}")
    return 0


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Dev-Ownership Orchestrator — central nervous system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  status         Show pipeline state (which phases done/pending)
  check          Run quality gates (pre-commit)
  harden         Run mutation testing (Harden phase)
  install        Install git hooks into project
  self-test      Run smoke + integration + self-gate
  sync           Sync scripts to canonical location
  rollback [VER] Rollback to previous version
  watch          Auto-run self-test on file save
  bump [LEVEL]   Bump version (patch|minor|major), updates VERSION+SKILL.md atomically
        """,
    )
    parser.add_argument("command", nargs="?", default="status",
                        choices=["status", "check", "harden", "install",
                                 "self-test", "sync", "rollback", "watch", "bump"])
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--full", action="store_true", help="Full mode (harden)")
    parser.add_argument("--version", type=str, help="Version for rollback")
    parser.add_argument("--level", type=str, choices=["patch", "minor", "major"],
                        default="patch", help="Bump level (bump command)")
    args = parser.parse_args()

    project_root = args.project_root.resolve()

    commands = {
        "status": lambda: cmd_status(project_root),
        "check": lambda: cmd_check(project_root),
        "harden": lambda: cmd_harden(project_root, args.full),
        "install": lambda: cmd_install(project_root),
        "self-test": cmd_self_test,
        "sync": cmd_sync,
        "rollback": lambda: cmd_rollback(args.version),
        "watch": cmd_watch,
        "bump": lambda: cmd_bump(args.level),
    }

    fn = commands.get(args.command)
    if fn:
        result = fn()
        return result if isinstance(result, int) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
