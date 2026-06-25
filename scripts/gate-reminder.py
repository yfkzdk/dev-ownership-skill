#!/usr/bin/env python3
"""gate-reminder.py — Active Feynman gate reminder system.

Writes persistent reminders that survive across commits and sessions.
Pre-commit hook calls this when a gate is missing.
AI memory file loads this at session start.

Usage:
  python gate-reminder.py --project <name> --gate <name> --action add|check|clear
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

REMINDER_FILE = Path.home() / ".claude" / "pending-gates.json"


def load_reminders() -> dict:
    if REMINDER_FILE.exists():
        return json.loads(REMINDER_FILE.read_text())
    return {"projects": {}, "last_checked": None}


def save_reminders(data: dict) -> None:
    REMINDER_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["last_checked"] = datetime.now().isoformat()
    REMINDER_FILE.write_text(json.dumps(data, indent=2))


def add_reminder(project: str, gate: str) -> None:
    data = load_reminders()
    if project not in data["projects"]:
        data["projects"][project] = []
    if gate not in data["projects"][project]:
        data["projects"][project].append(gate)
        save_reminders(data)
        # Print VERY visible reminder
        print("")
        print("=" * 60)
        print("  FEYNMAN GATE REQUIRED")
        print("=" * 60)
        print(f"  Project: {project}")
        print(f"  Gate:    {gate}")
        print(f"  Pending: {', '.join(data['projects'][project])}")
        print("")
        print("  To pass this gate:")
        print(f"  1. Ask AI: 'Feynman {gate} questions'")
        print("  2. Answer the 3 questions")
        print("  3. AI will record your answers")
        print("  4. Re-commit to proceed")
        print("=" * 60)
        print("")


def check_reminders(project: Optional[str] = None) -> dict:
    """Check pending gates. If project is given, check only that project."""
    data = load_reminders()
    if project:
        return {
            "project": project,
            "pending": data["projects"].get(project, []),
        }
    return data


def clear_reminder(project: str, gate: str) -> None:
    data = load_reminders()
    if project in data["projects"] and gate in data["projects"][project]:
        data["projects"][project].remove(gate)
        if not data["projects"][project]:
            del data["projects"][project]
        save_reminders(data)
        print(f"Gate '{gate}' cleared for {project}.")


def main():
    import argparse
    p = argparse.ArgumentParser(description="Feynman gate reminder")
    p.add_argument("--project", required=True)
    p.add_argument("--gate", default="")
    p.add_argument("--action", choices=["add", "check", "clear"], default="check")
    args = p.parse_args()

    if args.action == "add":
        add_reminder(args.project, args.gate)
    elif args.action == "check":
        result = check_reminders(args.project if args.project != "ALL" else None)
        if args.project == "ALL":
            for proj, gates in result.get("projects", {}).items():
                if gates:
                    print(f"  {proj}: {', '.join(gates)}")
            if not any(gates for gates in result.get("projects", {}).values()):
                print("  No pending gates.")
        else:
            pending = result.get("pending", [])
            if pending:
                print(f"  {args.project}: {', '.join(pending)}")
            else:
                print(f"  {args.project}: all gates passed.")
    elif args.action == "clear":
        clear_reminder(args.project, args.gate)


if __name__ == "__main__":
    main()
