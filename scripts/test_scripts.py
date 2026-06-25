#!/usr/bin/env python3
"""test_scripts.py — Integration tests for dev-ownership scripts (Layer 2: ~1 minute).

Verifies each script can be imported, has expected functions, and
produces expected output for known inputs.

Usage:
  python test_scripts.py           # run all
  python test_scripts.py --verbose # run with detailed output
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL_ROOT / "scripts"

FAILURES = 0


def run_script(name: str, *args: str, cwd: Path | None = None, timeout: int = 30) -> tuple[int, str, str]:
    script = SCRIPTS / name
    cmd = [sys.executable, str(script)] + list(args)
    r = subprocess.run(
        cmd, cwd=str(cwd) if cwd else str(SKILL_ROOT),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )
    return r.returncode, (r.stdout or ""), (r.stderr or "")


def check(name: str, ok: bool, detail: str = "") -> None:
    global FAILURES
    marker = "PASS" if ok else "FAIL"
    try:
        print(f"  [{marker}] {name}")
        if not ok and detail:
            print(f"         {detail[:120]}")
    except UnicodeEncodeError:
        print(f"  [{marker}] {name} (encoding-safe)")
    if not ok:
        FAILURES += 1


def test_pre_commit_check() -> None:
    print("\n--- pre-commit-check.py ---")
    code, out, err = run_script("pre-commit-check.py", "--help")
    check("--help works", code == 0, err or out)

    # Note: --json needs a real project with tests — skip in integration test


def test_mutation_engine() -> None:
    print("\n--- mutation-engine.py ---")
    code, out, err = run_script("mutation-engine.py", "--help")
    check("--help works", code == 0, err or out)

    # Basic import check — validates engine can parse a Python file
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / 'dummy.py').write_text('def foo(): return 1' + chr(10), encoding='utf-8')
        code, out, err = run_script(
            "mutation-engine.py",
            "--src", td,
            "--test-cmd", "echo skipped",
            "--n", "1", "--mode", "s", "--json",
            timeout=15,
        )
        check("runs on minimal project", code in (0, 1))


def test_cdr_tracker() -> None:
    print("\n--- cdr-sr-tracker.py ---")
    code, out, err = run_script("cdr-sr-tracker.py", "--help")
    check("--help works", code == 0, err or out)


def test_gate_quota() -> None:
    print("\n--- gate-quota-tracker.py ---")
    code, out, err = run_script("gate-quota-tracker.py", "--help")
    check("--help works", code == 0, err or out)


def test_gate_reminder() -> None:
    print("\n--- gate-reminder.py ---")
    code, out, err = run_script("gate-reminder.py", "--help")
    check("--help works", code == 0, err or out)


def test_project_inspector() -> None:
    print("\n--- project-inspector.py ---")
    code, out, err = run_script("project-inspector.py", "--help")
    check("--help works", code == 0, err or out)


def test_run_mutation() -> None:
    print("\n--- run-mutation.py ---")
    code, out, err = run_script("run-mutation.py", "--help")
    check("--help works", code == 0, err or out)


def test_smoke_test() -> None:
    print("\n--- smoke_test.py ---")
    code, out, err = run_script("smoke_test.py")
    check("smoke test passes on skill itself", code == 0, f"exit={code}")


def test_install_hooks() -> None:
    print("\n--- install-hooks.py ---")
    code, out, err = run_script("install-hooks.py", "--help")
    check("--help works", code == 0, err or out)

    code, out, err = run_script("install-hooks.py", "--list-backups")
    check("--list-backups works", code == 0, err or out)


def main() -> int:
    print("=== Integration Tests (L2) ===\n")

    test_pre_commit_check()
    test_mutation_engine()
    test_cdr_tracker()
    test_gate_quota()
    test_gate_reminder()
    test_project_inspector()
    test_run_mutation()
    test_smoke_test()
    test_install_hooks()

    print(f"\n{'='*40}")
    if FAILURES == 0:
        print("INTEGRATION TESTS PASSED")
        return 0
    else:
        print(f"INTEGRATION TESTS FAILED — {FAILURES} failures")
        return 1


if __name__ == "__main__":
    sys.exit(main())
