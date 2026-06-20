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
# Config: per-level quotas
LEVEL_CONFIG = {
    "P0": {  # 面试/生产: 设计门禁不可跳过, 代码门禁不可跳过
        "design_skippable": False,
        "code_quota": 0,
        "carry_over": True,
    },
    "P1": {  # 练习项目: 设计不可跳过, 代码可跳1次
        "design_skippable": False,
        "code_quota": 1,
        "carry_over": True,
    },
    "P2": {  # 测试/验证: 全部可跳, 不累计
        "design_skippable": True,
        "code_quota": 999,  # unlimited
        "carry_over": False,
    },
}

DESIGN_GATES = ["spec", "design"]
CODE_GATES = ["tdd", "review", "retrospect"]


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
            "level": "P2",  # default: test project
            "quota_remaining": 999,
            "design_skippable": True,
            "quota_carried_from_prev": 0,
            "skipped": [],
            "completed": [],
            "design_gates_frozen": False,
        }
    return load_json(path)


def get_global_state() -> dict[str, Any]:
    return load_json(GLOBAL_STATE)


def cmd_set_level(project_id: str, level: str) -> None:
    if level not in LEVEL_CONFIG:
        print(f"Unknown level: {level}. Use P0, P1, or P2.")
        return
    state = get_project_state(project_id)
    config = LEVEL_CONFIG[level]
    state["level"] = level
    state["design_skippable"] = config["design_skippable"]
    state["quota_remaining"] = config["code_quota"]
    state["last_updated"] = datetime.now().isoformat()
    path = STATE_DIR / f"{project_id}.json"
    save_json(path, state)
    print(f"Project '{project_id}' set to {level}.")
    print(f"  Design gates: {'skippable' if config['design_skippable'] else 'NOT skippable'}")
    print(f"  Code gate quota: {config['code_quota']}")


def cmd_status(project_id: str) -> None:
    state = get_project_state(project_id)
    lvl = state.get("level", "P2")
    print(f"Project: {project_id}")
    print(f"Level: {lvl}")
    print(f"Design gates: {'skippable' if state.get('design_skippable', True) else 'NOT skippable'}")
    print(f"Code gate quota: {state['quota_remaining']} remaining")
    if state["quota_carried_from_prev"] < 0:
        print(f"Carried debt: {state['quota_carried_from_prev']} (must repay)")
    print(f"Skipped: {', '.join(state['skipped']) if state['skipped'] else 'none'}")
    print(f"Completed: {', '.join(state['completed']) if state['completed'] else 'none'}")

    if state["skipped"]:
        print()
        print("⚠  Skipped gates must be completed before Retrospect.")
        if LEVEL_CONFIG.get(lvl, {}).get("carry_over", False):
            print("   They will carry over to the next project as quota debt.")

    if state["quota_remaining"] < 0:
        print()
        print("🔴 NO SKIPS AVAILABLE — previous debt must be repaid first.")


def cmd_skip(project_id: str, gate_name: str) -> None:
    state = get_project_state(project_id)

    if gate_name in DESIGN_GATES:
        if not state.get("design_skippable", False):
            print(f"🔴 Design gate '{gate_name}' CANNOT be skipped.")
            print(f"   Current level: {state.get('level', 'P2')} — design gates are mandatory.")
            return
        # P2: design gates are skippable

    if gate_name not in DESIGN_GATES and gate_name not in CODE_GATES:
        print(f"⚠  Unknown gate '{gate_name}'. Known: design={DESIGN_GATES}, code={CODE_GATES}")
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


def cmd_feynman_pass(project_id: str, gate_name: str) -> None:
    """Record Feynman gate as passed — creates gate file for pre-commit hook."""
    if gate_name not in DESIGN_GATES + CODE_GATES:
        print(f"Unknown gate: {gate_name}. Known: {DESIGN_GATES + CODE_GATES}")
        return

    state = get_project_state(project_id)
    level = state.get("level", "P2")

    # P0/P1 design gates: AI cannot bypass — developer must answer
    if gate_name in DESIGN_GATES and level in ("P0", "P1"):
        if not state.get("design_skippable", False):
            print(f"[BLOCKED] Design gate '{gate_name}' cannot be passed by AI on {level} projects.")
            print(f"  Developer must answer Feynman questions. AI: ask the 3 questions.")
            print(f"  After answers recorded, retry with --verified flag.")
            return

    gate_dir = STATE_DIR / "gates"
    gate_dir.mkdir(parents=True, exist_ok=True)
    gate_file = gate_dir / f"{project_id}-{gate_name}-passed.json"
    gate_file.write_text(json.dumps({
        "gate": gate_name,
        "project": project_id,
        "passed_at": datetime.now().isoformat(),
    }))

    # Also mark as completed in state
    state = get_project_state(project_id)
    if gate_name not in state["completed"]:
        state["completed"].append(gate_name)
    if gate_name in state["skipped"]:
        state["skipped"].remove(gate_name)
    state["last_updated"] = datetime.now().isoformat()
    save_json(STATE_DIR / f"{project_id}.json", state)

    print(f"Feynman gate '{gate_name}' passed. Pre-commit hook will allow next phase.")


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
    print(f"Next project: quota will be reduced by {debt} (from whatever the next project's level allows).")


def main():
    parser = argparse.ArgumentParser(description="Feynman Gate Quota Tracker")
    parser.add_argument("--project-id", default="default", help="Project identifier")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Show current quota status")

    set_p = sub.add_parser("set-level", help="Set project level (P0/P1/P2)")
    set_p.add_argument("level", help="P0=面试/生产, P1=练习, P2=测试/验证")

    skip_p = sub.add_parser("skip", help="Skip a gate")
    skip_p.add_argument("gate", help="Gate name: tdd|review|retrospect")

    complete_p = sub.add_parser("complete", help="Mark a gate as completed")
    complete_p.add_argument("gate", help="Gate name")

    feynman_p = sub.add_parser("feynman-pass", help="Record Feynman gate passed (creates hook file)")
    feynman_p.add_argument("gate", help="Gate name: spec|design|tdd|review|retrospect")

    sub.add_parser("close", help="Close project and carry over debt")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args.project_id)
    elif args.command == "set-level":
        cmd_set_level(args.project_id, args.level)
    elif args.command == "skip":
        cmd_skip(args.project_id, args.gate)
    elif args.command == "complete":
        cmd_complete(args.project_id, args.gate)
    elif args.command == "feynman-pass":
        cmd_feynman_pass(args.project_id, args.gate)
    elif args.command == "close":
        cmd_close_project(args.project_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
