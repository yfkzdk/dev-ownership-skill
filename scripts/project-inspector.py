#!/usr/bin/env python3
"""project-inspector.py — Full-lifecycle project health checker.

4-Phase convergence inspection (inspired by production-audit & local-agent-harness):
  Phase 0: Environment — tools, versions, prerequisites
  Phase 1: Structure — CI, openspec, .gitignore, project skeleton
  Phase 2: Quality Gates — run pre-commit-check, CDR/SR tracker
  Phase 3: CI Completeness — audit .github/workflows for missing steps

Convergence: each phase reports findings → fix → re-run until no new findings.

Usage: python project-inspector.py [--project-root .] [--phase all|0|1|2|3] [--json]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BOLD = "\033[1m"
NC = "\033[0m"


def run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def phase_0_environment(root: Path) -> list[dict[str, str]]:
    """Phase 0: Environment readiness check."""
    findings = []

    # Python version
    py_ver = sys.version_info
    if py_ver < (3, 10):
        findings.append({
            "severity": "HIGH", "phase": 0, "check": "python_version",
            "finding": f"Python {py_ver.major}.{py_ver.minor} < 3.10",
            "fix": "Upgrade to Python 3.10+"
        })

    # Required tools
    required = {
        "ruff": "pip install ruff",
        "git": "Install git: https://git-scm.com",
    }

    project_type = "unknown"
    if (root / "manage.py").exists():
        project_type = "django"
        required["python"] = "Install Python 3.10+"
    elif (root / "go.mod").exists():
        project_type = "go"
        required.update({"go": "Install Go 1.21+", "golangci-lint": "go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest"})
    elif (root / "Cargo.toml").exists():
        project_type = "rust"
        required.update({"cargo": "Install Rust: curl https://sh.rustup.rs -sSf | sh"})
    elif (root / "package.json").exists():
        project_type = "node"
        required.update({"node": "Install Node 18+", "eslint": "npm install -D eslint"})

    for tool, install in required.items():
        if shutil.which(tool) is None:
            findings.append({
                "severity": "MEDIUM", "phase": 0, "check": f"tool:{tool}",
                "finding": f"{tool} not installed",
                "fix": install
            })

    print(f"  Project type: {project_type}")
    print(f"  Python: {py_ver.major}.{py_ver.minor}.{py_ver.micro}")
    for tool in required:
        status = f"{GREEN}found{NC}" if shutil.which(tool) else f"{RED}missing{NC}"
        print(f"  {tool}: {status}")

    return findings


def phase_1_structure(root: Path) -> list[dict[str, str]]:
    """Phase 1: Project structure completeness."""
    findings = []

    checks = {
        ".gitignore": ("CRITICAL", "Missing .gitignore — __pycache__/ and .env files may be committed"),
        "openspec/": ("MEDIUM", "Missing openspec/ directory — spec-driven development not configured"),
    }

    # Check for CI config
    ci_dirs = [root / ".github" / "workflows", root / ".gitlab-ci.yml", root / "Jenkinsfile"]
    has_ci = any(d.exists() for d in ci_dirs)
    if not has_ci:
        findings.append({
            "severity": "MEDIUM", "phase": 1, "check": "ci_config",
            "finding": "No CI/CD configuration found",
            "fix": "Add .github/workflows/main.yaml"
        })

    for path, (severity, msg) in checks.items():
        if not (root / path).exists():
            findings.append({
                "severity": severity, "phase": 1, "check": f"file:{path}",
                "finding": msg,
                "fix": f"Create {path}"
            })

    for check_path, (sev, msg) in checks.items():
        exists = (root / check_path).exists()
        status = f"{GREEN}exists{NC}" if exists else f"{RED}missing{NC}"
        print(f"  {check_path}: {status}")

    print(f"  CI config: {f'{GREEN}found{NC}' if has_ci else f'{RED}missing{NC}'}")

    return findings


def phase_2_quality(root: Path, skill_dir: Path) -> list[dict[str, str]]:
    """Phase 2: Run quality gates and CDR tracker."""
    findings = []

    # Try to run pre-commit-check.py
    pre_commit = skill_dir / "scripts" / "pre-commit-check.py"
    if pre_commit.exists():
        print("  Running pre-commit-check.py...")
        code, stdout, stderr = run([sys.executable, str(pre_commit), "--json"], root)
        if code != 0:
            findings.append({
                "severity": "HIGH", "phase": 2, "check": "pre_commit",
                "finding": "Quality gates failed",
                "fix": "Fix lint/type/security/test failures"
            })
        else:
            print(f"  {GREEN}All quality gates passed{NC}")
    else:
        findings.append({
            "severity": "LOW", "phase": 2, "check": "pre_commit",
            "finding": "pre-commit-check.py not found in skill directory",
            "fix": "Ensure dev-ownership skill is installed"
        })

    # CDR/SR tracker
    cdr_tracker = skill_dir / "scripts" / "cdr-sr-tracker.py"
    if cdr_tracker.exists():
        code, stdout, stderr = run(
            [sys.executable, str(cdr_tracker), "--project-root", str(root), "--output", "json"],
            root
        )
        if code == 0:
            try:
                result = json.loads(stdout)
                mode = result.get("mode", "unknown")
                if mode == "cold_start":
                    cdr = result.get("cdr", 1.0)
                    status = "pass" if cdr <= 0.15 else "fail"
                    print(f"  CDR: {cdr:.4f} (threshold ≤0.15) [{status}]")
                    if status == "fail":
                        findings.append({
                            "severity": "HIGH", "phase": 2, "check": "cdr",
                            "finding": f"CDR {cdr:.4f} exceeds 0.15 — too much unverified AI code",
                            "fix": "Run Feynman gates on unverified modules"
                        })
                else:
                    sr = result.get("sr", 0)
                    status = "pass" if sr and sr >= 2.4 else "fail"
                    print(f"  SR: {sr} (threshold ≥2.4) [{status}]")
                    if status == "fail":
                        findings.append({
                            "severity": "HIGH", "phase": 2, "check": "sr",
                            "finding": f"SR {sr} below 2.4 — file stability degraded",
                            "fix": "Reduce churn rate. Avoid re-opening recently touched files."
                        })
            except json.JSONDecodeError:
                pass
    else:
        print(f"  {YELLOW}CDR/SR tracker not found{NC}")

    return findings


def phase_3_ci_audit(root: Path) -> list[dict[str, str]]:
    """Phase 3: CI pipeline completeness audit."""
    findings = []
    workflow_dir = root / ".github" / "workflows"

    if not workflow_dir.exists():
        return findings  # Already flagged in Phase 1

    required_ci_steps = {
        "lint": ["ruff", "eslint", "golangci-lint", "lint"],
        "type_check": ["mypy", "tsc", "go vet", "type_check", "typecheck"],
        "security": ["bandit", "gitleaks", "pip-audit", "security", "sast"],
        "test": ["pytest", "manage.py test", "go test", "npm test", "cargo test"],
        "coverage": ["coverage", "cov", "--cov", "coveralls", "codecov"],
    }

    for wf_file in workflow_dir.rglob("*.yaml"):
        content = wf_file.read_text()
        for step_name, keywords in required_ci_steps.items():
            if not any(kw in content for kw in keywords):
                findings.append({
                    "severity": "MEDIUM", "phase": 3, "check": f"ci_step:{step_name}",
                    "finding": f"CI workflow {wf_file.name} missing '{step_name}' step",
                    "fix": f"Add {step_name} step to CI pipeline"
                })

    for step_name, keywords in required_ci_steps.items():
        has = any(
            any(kw in (root / ".github" / "workflows" / f_name).read_text()
                for f_name in [f.name for f in workflow_dir.rglob("*.yaml")] if (root / ".github" / "workflows" / f_name).exists())
            for kw in keywords
        ) if list(workflow_dir.rglob("*.yaml")) else False
        status = f"{GREEN}present{NC}" if has else f"{RED}missing{NC}"
        print(f"  CI.{step_name}: {status}")

    return findings


def main():
    parser = argparse.ArgumentParser(description="Project Health Inspector")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--skill-dir", type=Path,
                        default=Path.home() / ".claude" / "skills" / "dev-ownership")
    parser.add_argument("--phase", default="all", choices=["all", "0", "1", "2", "3"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = args.project_root.resolve()
    skill_dir = args.skill_dir

    # Auto-detect skill dir
    if not skill_dir.exists():
        for candidate in [
            Path.home() / "dev-ownership-skill",
            root / ".claude" / "skills" / "dev-ownership",
        ]:
            if candidate.exists():
                skill_dir = candidate
                break

    print(f"{BOLD}=== Project Inspector ==={NC}")
    print(f"Project: {root}")
    print(f"Skill:   {skill_dir}")
    print()

    all_findings = []

    phases = [0, 1, 2, 3] if args.phase == "all" else [int(args.phase)]

    for phase in phases:
        phase_name = {0: "Environment", 1: "Structure", 2: "Quality Gates", 3: "CI Audit"}[phase]
        print(f"{BOLD}Phase {phase}: {phase_name}{NC}")

        if phase == 0:
            findings = phase_0_environment(root)
        elif phase == 1:
            findings = phase_1_structure(root)
        elif phase == 2:
            findings = phase_2_quality(root, skill_dir)
        else:
            findings = phase_3_ci_audit(root)

        if findings:
            for f in findings:
                print(f"  {RED}[{f['severity']}]{NC} {f['finding']}")
                print(f"         Fix: {f['fix']}")
        else:
            print(f"  {GREEN}No findings — phase clean{NC}")

        all_findings.extend(findings)
        print()

    # Summary
    total = len(all_findings)
    critical = sum(1 for f in all_findings if f["severity"] == "CRITICAL")
    high = sum(1 for f in all_findings if f["severity"] == "HIGH")
    medium = sum(1 for f in all_findings if f["severity"] == "MEDIUM")
    low = sum(1 for f in all_findings if f["severity"] == "LOW")

    print(f"{BOLD}=== Summary ==={NC}")
    print(f"Total findings: {total}")
    print(f"  Critical: {critical}  High: {high}  Medium: {medium}  Low: {low}")

    if total == 0:
        print(f"{GREEN}{BOLD}Project health check — ALL CLEAN{NC}")

    if args.json:
        print(json.dumps({"total": total, "findings": all_findings}, indent=2, ensure_ascii=False))

    sys.exit(0 if total == 0 else 1)


if __name__ == "__main__":
    main()
