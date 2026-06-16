#!/usr/bin/env python3
"""install-hooks.py — Install dev-ownership git hooks into a project.

Usage: python install-hooks.py [--project-root .] [--skill-dir ~/.claude/skills/dev-ownership]
"""

from __future__ import annotations

import shutil
import stat
import subprocess
import sys
from pathlib import Path


def find_skill_dir() -> Path:
    candidates = [
        Path.home() / ".claude" / "skills" / "dev-ownership",
        Path.home() / "dev-ownership-skill",
    ]
    for c in candidates:
        if (c / "scripts" / "pre-commit-check.py").exists():
            return c
    # Try relative to this script
    script_dir = Path(__file__).resolve().parent.parent
    if (script_dir / "scripts" / "pre-commit-check.py").exists():
        return script_dir
    print("Error: Cannot find dev-ownership skill directory.")
    print("Pass --skill-dir explicitly.")
    sys.exit(1)


def install_hook(project_root: Path, skill_dir: Path) -> bool:
    hooks_dir = project_root / ".git" / "hooks"
    if not hooks_dir.exists():
        print(f"Error: {project_root} is not a git repository (no .git/hooks/)")
        return False

    hook_path = hooks_dir / "pre-commit"
    checker = skill_dir / "scripts" / "pre-commit-check.py"

    if not checker.exists():
        print(f"Error: pre-commit-check.py not found at {checker}")
        return False

    # Write the hook script
    python = sys.executable
    hook_content = f'''#!/usr/bin/env bash
# Installed by dev-ownership skill (install-hooks.py)
# Runs quality gates before every commit.

exec "{python}" "{checker}" "$@"
'''

    hook_path.write_text(hook_content)

    # Make executable (Unix) or ensure it exists (Windows)
    if hasattr(stat, "S_IXUSR"):
        hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f"Installed: {hook_path}")
    print(f"  → runs: {checker.name}")
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Install dev-ownership git hooks")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--skill-dir", type=Path, default=None)
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    skill_dir = args.skill_dir or find_skill_dir()

    print(f"Project: {project_root}")
    print(f"Skill:   {skill_dir}")

    ok = install_hook(project_root, skill_dir)
    if ok:
        print("\n git commit 时将自动运行 pre-commit-check.py。")
        print(" 跳过(不推荐): git commit --no-verify")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
