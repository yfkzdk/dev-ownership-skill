#!/usr/bin/env python3
"""install-hooks.py — Install dev-ownership git hooks into a project.

Usage:
  python install-hooks.py [--project-root .]
  python install-hooks.py --sync-only          # sync scripts, auto-backup old version
  python install-hooks.py --rollback           # restore latest backup
  python install-hooks.py --rollback v0.2.0   # restore specific version

Single source of truth: scripts are copied FROM the skill source directory
TO ~/.claude/skills/dev-ownership/scripts/. The pre-commit hook always
references the canonical install location.

Backup: Before overwriting old scripts, the current version is backed up
to CANONICAL/.backups/<version>/. Use --rollback to restore.

Versioning: VERSION file in source root is compared against installed VERSION.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CANONICAL = Path.home() / ".claude" / "skills" / "dev-ownership"
BACKUPS = CANONICAL / ".backups"


def _load_version(p: Path) -> str | None:
    vf = p / "VERSION"
    if not vf.exists():
        return None
    for line in vf.read_text(encoding="utf-8").split(chr(10)):
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip().strip('"')
    return None


def find_skill_source() -> Path:
    """Find the skill source directory (where this script lives)."""
    script_dir = Path(__file__).resolve().parent.parent
    if (script_dir / "scripts" / "pre-commit-check.py").exists():
        return script_dir
    # Fallback: check known locations
    candidates = [
        Path.home() / ".claude" / "skills" / "dev-ownership",
    ]
    for c in candidates:
        if (c / "scripts" / "pre-commit-check.py").exists():
            return c
    print("Error: Cannot find dev-ownership skill source directory.")
    print("Ensure pre-commit-check.py exists in one of the known locations.")
    sys.exit(1)


def sync_scripts(source: Path) -> bool:
    """Copy all scripts from source to canonical install location.

    Returns True if any files were updated.
    """
    src_scripts = source / "scripts"
    dst_scripts = CANONICAL / "scripts"

    if not src_scripts.exists():
        print(f"Error: Source scripts not found at {src_scripts}")
        return False

    dst_scripts.mkdir(parents=True, exist_ok=True)
    updated = False

    for src_file in src_scripts.iterdir():
        if src_file.suffix != ".py":
            continue
        dst_file = dst_scripts / src_file.name

        if dst_file.exists():
            src_mtime = src_file.stat().st_mtime
            dst_mtime = dst_file.stat().st_mtime
            if src_mtime <= dst_mtime:
                continue  # already up to date

        shutil.copy2(src_file, dst_file)
        print(f"  synced: {src_file.name}")
        updated = True

    # Also sync config
    src_config = source / "config"
    dst_config = CANONICAL / "config"
    if src_config.exists():
        dst_config.mkdir(parents=True, exist_ok=True)
        for f in src_config.iterdir():
            dst_f = dst_config / f.name
            if not dst_f.exists() or f.stat().st_mtime > dst_f.stat().st_mtime:
                shutil.copy2(f, dst_f)
                updated = True

    # Sync VERSION file
    src_version = source / "VERSION"
    if src_version.exists():
        shutil.copy2(src_version, CANONICAL / "VERSION")

    return updated


def _backup_current() -> str | None:
    """Backup current installed scripts before overwriting.
    Returns the backed-up version string, or None if nothing to back up."""
    version = _load_version(CANONICAL)
    if version is None:
        return None
    scripts = CANONICAL / "scripts"
    if not scripts.exists() or not list(scripts.glob("*.py")):
        return None

    backup_dir = BACKUPS / f"v{version}"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Copy scripts
    (backup_dir / "scripts").mkdir(exist_ok=True)
    for f in scripts.glob("*.py"):
        shutil.copy2(f, backup_dir / "scripts" / f.name)

    # Copy config
    config = CANONICAL / "config"
    if config.exists():
        (backup_dir / "config").mkdir(exist_ok=True)
        for f in config.iterdir():
            if f.is_file():
                shutil.copy2(f, backup_dir / "config" / f.name)

    # Copy VERSION
    vf = CANONICAL / "VERSION"
    if vf.exists():
        shutil.copy2(vf, backup_dir / "VERSION")

    # Write backup metadata
    (backup_dir / "backup.json").write_text(
        __import__('json').dumps({
            "version": version,
            "backed_up_at": datetime.now().isoformat(),
        }, indent=2)
    )

    print(f"  backed up: v{version} -> {backup_dir}")
    return version


def _list_backups() -> list[Path]:
    """List available backups, newest first."""
    if not BACKUPS.exists():
        return []
    backups = sorted(BACKUPS.iterdir(), key=lambda p: p.name, reverse=True)
    return [b for b in backups if b.is_dir()]


def _rollback(version: str | None = None, dry_run: bool = False) -> bool:
    """Restore a backed-up version. If version is None, restore latest.

    Based on pipu-cli pattern: --dry-run previews without executing.
    """
    backups = _list_backups()
    if not backups:
        print("No backups available.")
        return False

    if version:
        target = BACKUPS / version if version.startswith("v") else BACKUPS / f"v{version}"
        if not target.exists():
            print(f"Backup '{version}' not found. Available:")
            for b in backups:
                print(f"  {b.name}")
            return False
    else:
        target = backups[0]

    if dry_run:
        print(f"[DRY RUN] Would restore: {target.name}")
        src_scripts = target / "scripts"
        if src_scripts.exists():
            for f in sorted(src_scripts.glob("*.py")):
                print(f"  + {f.name}")
        return True

    # Restore scripts
    src_scripts = target / "scripts"
    dst_scripts = CANONICAL / "scripts"
    if src_scripts.exists():
        if dst_scripts.exists():
            shutil.rmtree(dst_scripts)
        shutil.copytree(str(src_scripts), str(dst_scripts))

    # Restore config
    src_config = target / "config"
    dst_config = CANONICAL / "config"
    if src_config.exists():
        if dst_config.exists():
            shutil.rmtree(dst_config)
        shutil.copytree(str(src_config), str(dst_config))

    # Restore VERSION
    vf = target / "VERSION"
    if vf.exists():
        shutil.copy2(vf, CANONICAL / "VERSION")

    meta = target / "backup.json"
    restored_version = target.name
    if meta.exists():
        import json
        data = json.loads(meta.read_text(encoding="utf-8"))
        restored_version = f"v{data['version']}"

    print(f"Rolled back to {restored_version}")
    print(f"Backed up at: {meta.read_text(encoding='utf-8') if meta.exists() else 'unknown'}")
    return True


def install_hook(project_root: Path) -> bool:
    hooks_dir = project_root / ".git" / "hooks"
    if not hooks_dir.exists():
        print(f"Error: {project_root} is not a git repository (no .git/hooks/)")
        return False

    python = sys.executable
    checker = CANONICAL / "scripts" / "pre-commit-check.py"

    if not checker.exists():
        print(f"Error: pre-commit-check.py not found at {checker}")
        print("Run with --sync-only first, or ensure the skill is installed.")
        return False

    pre_commit = hooks_dir / "pre-commit"
    pre_commit.write_text(
        f"""#!/usr/bin/env bash
exec "{python}" "{checker}" "$@"
"""
    )
    if hasattr(os, "chmod"):
        os.chmod(pre_commit, pre_commit.stat().st_mode | 0o111)
    print(f"  pre-commit: installed -> {checker}")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Install dev-ownership git hooks")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--sync-only", action="store_true", help="Sync scripts only, skip hook install")
    parser.add_argument("--rollback", nargs="?", const="__LATEST__", default=None, metavar="VERSION",
                        help="Rollback to a previous version (latest if no version given)")
    parser.add_argument("--dry-run", action="store_true", help="Preview rollback without executing")
    parser.add_argument("--list-backups", action="store_true", help="List available backups")
    args = parser.parse_args()

    # --list-backups
    if args.list_backups:
        backups = _list_backups()
        if backups:
            print("Available backups:")
            for b in backups:
                meta = b / "backup.json"
                if meta.exists():
                    import json
                    data = json.loads(meta.read_text(encoding="utf-8"))
                    print(f"  {b.name} — backed up {data['backed_up_at']}")
                else:
                    print(f"  {b.name}")
        else:
            print("No backups available.")
        return

    # --rollback
    if args.rollback is not None:
        ver = None if args.rollback == "__LATEST__" else args.rollback
        ok = _rollback(ver, dry_run=args.dry_run)
        if not ok:
            sys.exit(1)
        return

    source = find_skill_source()
    print(f"Source:  {source}")
    print(f"Install: {CANONICAL}")

    # Show version info and auto-backup
    src_ver = _load_version(source)
    installed_ver = _load_version(CANONICAL)
    if src_ver:
        suffix = f" (installed: {installed_ver})" if installed_ver and installed_ver != src_ver else ""
        print(f"Version: {src_ver}{suffix}")
    if installed_ver and src_ver and installed_ver != src_ver:
        print(f"  Upgrading: {installed_ver} -> {src_ver}")
        _backup_current()

    updated = sync_scripts(source)
    if updated:
        print("Scripts synced to canonical location.")
    else:
        print("Scripts already up to date.")

    if args.sync_only:
        return

    project_root = args.project_root.resolve()
    print(f"\nProject: {project_root}")

    ok = install_hook(project_root)
    if ok:
        print("\ngit commit 时将自动运行 pre-commit-check.py。")
        print("跳过(不推荐): git commit --no-verify")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
