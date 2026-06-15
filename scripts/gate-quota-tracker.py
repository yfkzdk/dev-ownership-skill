#!/usr/bin/env python3
"""gate-quota-tracker.py — Feynman Gate quota management.

Tracks:
- How many gate skips remain in the current project
- Carries over unspent skips from previous project
- Flags when a project has zero skips available

Usage: python gate-quota-tracker.py [--project-id <name>] [--skip <gate_name>] [--status]

State file: .claude/gate-quota.json (per-project)
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


STATE_DIR = Path.home() / ".claude" / "gate-quota"
STATE_DIR.mkdir(parents=True, exist_ok=True)

GLOBAL_STATE = STATE_DIR / "global.json"

# Config
DESIGN_GATES = ["spec", "design"]  # never skippable
CODE_GATES = ["tdd", "review", "retrospect"]  # quota = 1 per project
QUOTA_PER_PROJECT = 1


def load_json(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2))


def get_project_state(project_id: str) -> dict[str, Any]:
    path = STATE_DIR / f"{project_id}.json"
    if not path.exists():
        return {
            "project_id": project_id,
            "quota_remaining": QUOTA_PER_PROJECT,
            "quota_carried_from_prev": 0,
            "skipped": [],
            "completed": [],
            "design_gates_frozen": False,
        }
    return load_json(path)


def get_global_state() -> dict[str, Any]:
    return load_json(GLOBAL_STATE)


def cmd_status(project_id: str) -> None:
    state = get_project_state(project_id)
    print(f"Project: {project_id}")
    print(f"Quota remaining: {state['quota_remaining']}")
    if state["quota_carried_from_prev"] < 0:
        print(f"Carried debt: {state['quota_carried_from_prev']} (must repay)")
    print(f"Skipped: {', '.join(state['skipped']) if state['skipped'] else 'none'}")
    print(f"Completed: {', '.join(state['completed']) if state['completed'] else 'none'}")

    if state["skipped"]:
        print()
        print("⚠  Skipped gates must be completed before Retrospect.")
        print("   They will carry over to the next project as quota debt.")

    if state["quota_remaining"] < 0:
        print()
        print("🔴 NO SKIPS AVAILABLE — previous debt must be repaid first.")


def cmd_skip(project_id: str, gate_name: str) -> None:
    state = get_project_state(project_id)

    if gate_name in DESIGN_GATES:
        print(f"🔴 Design gate '{gate_name}' CANNOT be skipped.")
        print("   Design/architecture decisions are review-pass mandatory.")
        return

    if gate_name not in CODE_GATES:
        print(f"⚠  Unknown gate '{gate_name}'. Known code gates: {CODE_GATES}")
        return

    if gate_name in state["skipped"]:
        print(f"⚠  Gate '{gate_name}' already skipped in this project.")
        return

    if state["quota_remaining"] <= 0:
        print(f"🔴 Cannot skip '{gate_name}' — quota exhausted.")
        print(f"   Remaining: {state['quota_remaining']}")
        print(f"   Carried debt: {state['quota_carried_from_prev']}")
        print(f"   You must complete previous skipped gates first.")
        return

    state["skipped"].append(gate_name)
    state["quota_remaining"] -= 1
    state["last_updated"] = datetime.now().isoformat()
    path = STATE_DIR / f"{project_id}.json"
    save_json(path, state)
    print(f"Skipped '{gate_name}'. Remaining quota: {state['quota_remaining']}")


def cmd_complete(project_id: str, gate_name: str) -> None:
    state = get_project_state(project_id)

    if gate_name not in state["skipped"] and gate_name not in CODE_GATES + DESIGN_GATES:
        print(f"⚠  Unknown gate '{gate_name}'.")
        return

    if gate_name not in state["completed"]:
        state["completed"].append(gate_name)

    # Remove from skipped if it was there
    if gate_name in state["skipped"]:
        state["skipped"].remove(gate_name)
        state["quota_remaining"] += 1  # reclaim if completed within same project

    state["last_updated"] = datetime.now().isoformat()
    path = STATE_DIR / f"{project_id}.json"
    save_json(path, state)
    print(f"Completed '{gate_name}'.")


def cmd_close_project(project_id: str) -> None:
    """Close project: carry over uncompleted skipped gates to next project."""
    state = get_project_state(project_id)
    global_state = get_global_state()

    debt = len(state["skipped"])  # gates skipped but not completed

    # Carry to next project
    global_state["carried_debt"] = global_state.get("carried_debt", 0) + debt
    global_state["last_project"] = project_id
    global_state["last_updated"] = datetime.now().isoformat()
    save_json(GLOBAL_STATE, global_state)

    state["closed"] = True
    state["final_debt"] = debt
    state["last_updated"] = datetime.now().isoformat()
    path = STATE_DIR / f"{project_id}.json"
    save_json(path, state)

    print(f"Project '{project_id}' closed.")
    print(f"Uncompleted gates carried to next project: {debt}")
    print(f"Next project quota: {QUOTA_PER_PROJECT - debt}")
    if QUOTA_PER_PROJECT - debt < 0:
        print(f"🔴 Next project starts with ZERO skips. Repay {abs(QUOTA_PER_PROJECT - debt)} gates first.")


def main():
    parser = argparse.ArgumentParser(description="Feynman Gate Quota Tracker")
    parser.add_argument("--project-id", default="default", help="Project identifier")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Show current quota status")

    skip_p = sub.add_parser("skip", help="Skip a gate")
    skip_p.add_argument("gate", help="Gate name: tdd|review|retrospect")

    complete_p = sub.add_parser("complete", help="Mark a gate as completed")
    complete_p.add_argument("gate", help="Gate name")

    sub.add_parser("close", help="Close project and carry over debt")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args.project_id)
    elif args.command == "skip":
        cmd_skip(args.project_id, args.gate)
    elif args.command == "complete":
        cmd_complete(args.project_id, args.gate)
    elif args.command == "close":
        cmd_close_project(args.project_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
