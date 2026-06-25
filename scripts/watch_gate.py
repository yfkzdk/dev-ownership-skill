#!/usr/bin/env python3
"""watch_gate.py — Auto-trigger self-gate on file save (Problem 2: CI auto-run).

Based on: Watchexec + pytest-watcher + Pipelight patterns.
Runs smoke test + self-gate whenever a skill script changes.

Usage:
  python watch_gate.py              # watch skill scripts, run self-gate on change
  python watch_gate.py --once       # run once and exit
  python watch_gate.py --debounce 3 # wait 3 seconds after last change (default: 2)
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL_ROOT / "scripts"
WATCH_EXTS = {".py", ".sh", ".yml", ".md"}


def run_self_gate() -> bool:
    """Run the full self-gate pipeline. Returns True if passed."""
    gate_script = SCRIPTS / "self-gate.sh"
    if not gate_script.exists():
        print("[WATCH] self-gate.sh not found")
        return False

    r = subprocess.run(
        ["bash", str(gate_script)],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        timeout=120,
    )
    passed = r.returncode == 0
    # Print last 3 lines
    lines = (r.stdout or "").split("\n")
    for line in lines[-5:]:
        if line.strip():
            print(f"  {line.strip()}")
    return passed


def watch(debounce: float = 2.0) -> None:
    """Watch skill scripts for changes, run self-gate on save."""
    print(f"[WATCH] Watching {SCRIPTS} for changes...")
    print(f"[WATCH] Debounce: {debounce}s. Press Ctrl+C to stop.")
    print()

    # Build initial snapshot
    snapshots: dict[Path, float] = {}
    for ext in WATCH_EXTS:
        for f in SKILL_ROOT.rglob(f"*{ext}"):
            if "__pycache__" in str(f) or ".git" in str(f) or ".backups" in str(f):
                continue
            snapshots[f] = f.stat().st_mtime

    last_run = 0.0

    while True:
        changed = False
        for ext in WATCH_EXTS:
            for f in SKILL_ROOT.rglob(f"*{ext}"):
                if "__pycache__" in str(f) or ".git" in str(f) or ".backups" in str(f):
                    continue
                try:
                    mtime = f.stat().st_mtime
                except OSError:
                    continue
                prev = snapshots.get(f, 0)
                if mtime > prev:
                    snapshots[f] = mtime
                    changed = True

        if changed:
            now = time.time()
            if now - last_run >= debounce:
                print(f"\n[WATCH] Change detected at {time.strftime('%H:%M:%S')}")
                passed = run_self_gate()
                status = "PASS" if passed else "FAIL"
                print(f"[WATCH] Self-gate: {status}\n")
                last_run = now

        time.sleep(0.5)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Auto-trigger self-gate on file save")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--debounce", type=float, default=2.0, help="Debounce seconds")
    args = parser.parse_args()

    if args.once:
        passed = run_self_gate()
        print(f"\nSelf-gate: {'PASS' if passed else 'FAIL'}")
        sys.exit(0 if passed else 1)
    else:
        watch(args.debounce)


if __name__ == "__main__":
    main()
