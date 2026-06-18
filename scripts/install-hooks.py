#!/usr/bin/env python3
"""install-hooks.py — Install dev-ownership git hooks into a project.

Usage: python install-hooks.py [--project-root .] [--skill-dir ~/.claude/skills/dev-ownership]
"""

from __future__ import annotations

import os
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

    python = sys.executable
    installed = 0

    # pre-commit hook — quality gates
    pre_commit = hooks_dir / "pre-commit"
    checker = skill_dir / "scripts" / "pre-commit-check.py"
    if checker.exists():
        pre_commit.write_text(f'''#!/usr/bin/env bash
exec "{python}" "{checker}" "$@"
''')
        if hasattr(os, "chmod"):
            os.chmod(pre_commit, pre_commit.stat().st_mode | 0o111)
        print(f"  pre-commit: installed")
        installed += 1

    # commit-msg hook — message validation
    commit_msg = hooks_dir / "commit-msg"
    msg_checker = skill_dir / "scripts" / "commit-msg-check.py"
    if msg_checker.exists():
        commit_msg.write_text(f'''#!/usr/bin/env bash
exec "{python}" "{msg_checker}" "$@"
''')
        if hasattr(os, "chmod"):
            os.chmod(commit_msg, commit_msg.stat().st_mode | 0o111)
        print(f"  commit-msg: installed")
        installed += 1

    if installed == 0:
        print("Error: no checkers found")
        return False

    print(f"\n git commit 时将自动运行 pre-commit + commit-msg 检查。")
    print(" 跳过(不推荐): git commit --no-verify")
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
