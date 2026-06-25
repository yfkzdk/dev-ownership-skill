#!/usr/bin/env python3
"""smoke_test.py — Dev-ownership skill self-test (Layer 1: 5 seconds).

Run after every change to verify the skill isn't broken.
Checks: syntax, VERSION consistency, file integrity, importability.

Usage: python smoke_test.py
Exit 0 = all good, Exit 1 = something broken.
"""

from __future__ import annotations

import py_compile
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL_ROOT / "scripts"
CONFIG = SKILL_ROOT / "config"
REFERENCES = SKILL_ROOT / "references"

ERRORS = 0


def check(msg: str, ok: bool) -> None:
    global ERRORS
    if ok:
        print(f"  PASS  {msg}")
    else:
        print(f"  FAIL  {msg}")
        ERRORS += 1


def main() -> int:
    print("=== Smoke Test (L1) ===\n")

    # 1. All scripts compile
    print("1. Script syntax:")
    for sf in sorted(SCRIPTS.glob("*.py")):
        try:
            py_compile.compile(str(sf), doraise=True)
            check(f"  {sf.name}", True)
        except py_compile.PyCompileError as e:
            check(f"  {sf.name}: {e}", False)

    # 2. VERSION file exists and is parseable
    print("\n2. VERSION file:")
    vf = SKILL_ROOT / "VERSION"
    if vf.exists():
        check("VERSION exists", True)
        content = vf.read_text(encoding="utf-8")
        has_version = any(line.startswith("version:") for line in content.split("\n"))
        check("VERSION has version field", has_version)
        has_changelog = "changelog:" in content
        check("VERSION has changelog", has_changelog)
    else:
        check("VERSION exists", False)

    # 3. SKILL.md references exist
    print("\n3. SKILL.md file references:")
    skill_md = SKILL_ROOT / "SKILL.md"
    if skill_md.exists():
        skill_content = skill_md.read_text(encoding="utf-8")
        # Extract referenced files like [references/xxx.md] or scripts/xxx.py
        import re
        # Match markdown links: [text](path) — extract the path part (URL)
        refs = re.findall(r'\]\(([^)]+\.md)\)|scripts/([^\s\]\)]+\.py)', skill_content)
        seen = set()
        for ref in refs:
            path_str = ref[0] or f"scripts/{ref[1]}"
            if path_str in seen:
                continue
            seen.add(path_str)
            target = SKILL_ROOT / path_str
            check(f"  {path_str}", target.exists())
    else:
        check("SKILL.md exists", False)

    # 4. Config files parseable
    print("\n4. Config files:")
    for cf in CONFIG.glob("*.yml"):
        try:
            import yaml
            with open(cf, encoding="utf-8") as f:
                yaml.safe_load(f)
            check(f"  {cf.name}", True)
        except Exception as e:
            check(f"  {cf.name}: {e}", False)

    # 5. install-hooks.py runs --help
    print("\n5. CLI --help:")
    import subprocess
    for sf in sorted(SCRIPTS.glob("*.py")):
        if sf.name.startswith("_") or sf.name in ("smoke_test.py", "test_scripts.py", "commit-msg-check.py"):
            continue
        r = subprocess.run(
            [sys.executable, str(sf), "--help"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10,
        )
        check(f"  {sf.name} --help (exit {r.returncode})", r.returncode == 0)

    print(f"\n{'='*40}")
    if ERRORS == 0:
        print("SMOKE TEST PASSED")
        return 0
    else:
        print(f"SMOKE TEST FAILED — {ERRORS} errors")
        return 1


if __name__ == "__main__":
    sys.exit(main())
