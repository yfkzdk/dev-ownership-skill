#!/usr/bin/env python3
"""Print skill version from VERSION file. Used by self-gate.sh."""
from pathlib import Path

skill_root = Path(__file__).resolve().parent.parent
vf = skill_root / "VERSION"
for line in vf.read_text(encoding="utf-8").split("\n"):
    if line.startswith("version:"):
        print(line.split(":", 1)[1].strip().strip('"'))
        break
