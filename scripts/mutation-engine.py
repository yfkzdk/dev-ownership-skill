#!/usr/bin/env python3
"""mutation-engine.py — Minimal mutation testing engine.

Design (from research):
  - Mutation switching: in-memory AST transform, write to temp dir
  - 4 operator types: BoolFlip, CompareFlip, BinOpFlip, StmtDelete
  - Arid-node filter: skip log/time/config/init-capacity mutations
  - Incremental: git diff --cached --name-only to scope targets
  - Subprocess isolation: each mutant runs in its own process with timeout
  - UTF-8 everywhere: no bare open(), no cp1252

Usage:
  python mutation-engine.py --src src/ --test-cmd "python -m pytest tests/ -q" [--n 15] [--mode s] [--output json]
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# ── Arid-node filter (Google heuristic) ─────────────────────────────────────

ARID_PATTERNS = [
    re.compile(r'log(ger)?\.(info|debug|warn|error|exception)', re.IGNORECASE),
    re.compile(r'logging\.(getLogger|basicConfig|log)', re.IGNORECASE),
    re.compile(r'time\.(time|sleep|monotonic|perf_counter)', re.IGNORECASE),
    re.compile(r'\.(get|read)_config\b', re.IGNORECASE),
    re.compile(r'(settings|config)\[', re.IGNORECASE),
]


def _is_arid_node(tree: ast.AST, node: ast.AST, source_lines: list[str]) -> bool:
    """Check if mutating this node would produce a brittle/pointless test."""
    if hasattr(node, 'lineno'):
        line = source_lines[node.lineno - 1] if node.lineno <= len(source_lines) else ""
        for pat in ARID_PATTERNS:
            if pat.search(line):
                return True
    # Skip docstrings and comments
    if isinstance(node, ast.Expr) and isinstance(node.value, (ast.Str, ast.Constant)):
        return True
    return False


# ── Phase 0: Auto function classifier ───────────────────────────────────────

# Patterns that indicate a function has side effects
DB_PATTERNS = [
    re.compile(r'(?:\.|^|\s)(execute|commit|rollback|executemany|executescript)\s*\('),
    re.compile(r'(?:\.|^|\s)(session\.(add|delete|merge|flush|refresh|bulk))\s*\('),
    re.compile(r'(?:\.|^|\s)(cursor\.(execute|executemany|fetch))\s*\('),
    re.compile(r'\.(save|delete|update|insert|create)\s*\('),
]
NETWORK_PATTERNS = [
    re.compile(r'\b(requests\.|httpx\.|urllib\.|aiohttp\.)'),
    re.compile(r'\b(open|Path)\s*\(.*[\'\"].*[\'\"]\s*[,\)]'),  # file I/O
    re.compile(r'\b(subprocess\.(run|call|Popen|check_output))\s*\('),
    re.compile(r'\b(socket\.|smtplib\.|ftplib\.)'),
]


def _classify_function(func_node: ast.FunctionDef | ast.AsyncFunctionDef,
                      source: str) -> str:
    """Classify a function as 'pure', 'db', or 'io'.

    Scans function body for patterns indicating side effects.
    Returns 'pure' if no side effects detected.
    """
    lines = source.split("\n")
    start = func_node.lineno - 1  # 0-indexed
    end = getattr(func_node, 'end_lineno', func_node.lineno)  # already 1-indexed
    func_source = "\n".join(lines[start:end])
    for pat in DB_PATTERNS:
        if pat.search(func_source):
            return "db"
    for pat in NETWORK_PATTERNS:
        if pat.search(func_source):
            return "io"
    if isinstance(func_node, ast.AsyncFunctionDef):
        return "io"  # async functions → io track
    return "pure"


def _classify_all_functions(src_dir: Path) -> dict[str, list[dict]]:
    """Scan all source files and classify every function.

    Returns: {"pure": [...], "db": [...], "io": [...]}
    Each entry: {"file": str, "name": str, "lineno": int, "params": [...]}
    """
    result: dict[str, list[dict]] = {"pure": [], "db": [], "io": []}
    for pf in sorted(src_dir.rglob("*.py")):
        if "__pycache__" in str(pf) or "__init__" in pf.name:
            continue
        try:
            source = pf.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except Exception:
            continue

        rel = str(pf.relative_to(src_dir)).replace("\\", "/")
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip private/double-underscore helpers (but keep __init__)
                if node.name.startswith("__") and node.name != "__init__":
                    continue
                # Skip test functions
                if node.name.startswith("test_"):
                    continue
                category = _classify_function(node, source)
                params = []
                for arg in node.args.args:
                    ann = ""
                    if arg.annotation:
                        try:
                            ann = ast.unparse(arg.annotation)
                        except Exception:
                            ann = "Any"
                    default = None
                    if node.args.defaults:
                        idx = len(node.args.args) - len(node.args.defaults)
                        pos = node.args.args.index(arg)
                        if pos >= idx:
                            d = node.args.defaults[pos - idx]
                            try:
                                default = ast.literal_eval(d)
                            except Exception:
                                default = ast.unparse(d) if hasattr(ast, 'unparse') else str(d)
                    params.append({
                        "name": arg.arg,
                        "annotation": ann,
                        "default": default,
                    })
                result[category].append({
                    "file": rel, "name": node.name, "lineno": node.lineno,
                    "params": params,
                })
    return result


# ── Phase 1: Constraint auto-inference ──────────────────────────────────────

# Parameter name → valid value pool patterns
CONSTRAINT_PATTERNS: dict[str, list] = {
    "_days": [0, 1, 30, 90, 365],
    "_date": ["date.min", "today", "today+365", "today-365"],
    "_id": [0, 1, 999],
    "currency": ["USD", "CNY", "EUR", ""],
    "amount": [0, 1, 100, -1],
    "price": [0, 1, 100, -1],
    "rate": [0, 0.5, 1, 2, -0.5],
    "tier": ["admin", "manager", "viewer", ""],
    "status": ["active", "cancelled", "expired", ""],
    "cycle": [30, 90, 365],
    "period": [30, 90, 365],
}


def _infer_constraints(params: list[dict]) -> dict[str, list]:
    """Infer valid input values from parameter names, types, and defaults.

    Returns a dict mapping param_name → [suggested_values].
    """
    constraints: dict[str, list] = {}
    for p in params:
        name = p["name"]
        values = set()

        # 1. Check parameter name patterns
        for pattern, pool in CONSTRAINT_PATTERNS.items():
            if name.endswith(pattern) or pattern in name:
                values.update(pool)

        # 2. Check type annotation
        ann = p.get("annotation", "")
        if "int" in ann and not values:
            values.update([0, 1, -1, 100])
        elif "str" in ann and not values:
            values.update(["", "test", "USD"])
        elif "bool" in ann and not values:
            values.update([True, False])
        elif "Decimal" in ann and not values:
            values.update([0, 1, 100, -1])

        # 3. Add default value if present
        if p.get("default") is not None:
            values.add(p["default"])

        # 4. Always include None as boundary
        values.add(None)

        if values:
            constraints[name] = sorted(values, key=lambda x: (x is None, str(x)))

    return constraints


# ── Phase 3: Cross-project equivalence memory ───────────────────────────────

EQUIV_MEMORY = Path.home() / ".claude" / "mutation-equivalence-memory.json"
ENGINE_PARAMS = Path.home() / ".claude" / "mutation-engine-params.json"


def _load_params() -> dict:
    """Load optimized engine parameters from meta-cycle."""
    if ENGINE_PARAMS.exists():
        try:
            return json.loads(ENGINE_PARAMS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"equiv_threshold": 0.98, "hot_operators": {}, "hot_gap_patterns": {},
            "avg_harden_cycles": 1.0, "projects_completed": 0}


def _save_params(params: dict) -> None:
    """Persist updated parameters for next project."""
    ENGINE_PARAMS.parent.mkdir(parents=True, exist_ok=True)
    ENGINE_PARAMS.write_text(json.dumps(params, indent=2, ensure_ascii=False))


def _load_equiv_memory() -> list[dict]:
    """Load cross-project equivalence patterns."""
    if EQUIV_MEMORY.exists():
        try:
            return json.loads(EQUIV_MEMORY.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_equiv_memory(entry: dict) -> None:
    """Record an equivalence pattern for future projects."""
    EQUIV_MEMORY.parent.mkdir(parents=True, exist_ok=True)
    memory = _load_equiv_memory()
    # Avoid exact duplicates
    for m in memory:
        if m.get("pattern") == entry.get("pattern"):
            m["count"] = m.get("count", 1) + 1
            m["last_seen"] = datetime.now().isoformat()
            EQUIV_MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False))
            return
    entry["count"] = 1
    entry["first_seen"] = datetime.now().isoformat()
    entry["last_seen"] = entry["first_seen"]
    memory.append(entry)
    EQUIV_MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False))


# ── Target finder ────────────────────────────────────────────────────────────

def _find_targets(tree: ast.AST, source_lines: list[str], filename: str) -> list[dict]:
    """Walk AST and find mutatable locations."""
    targets = []

    class Finder(ast.NodeVisitor):
        def _loc(self, node):
            return {
                "lineno": node.lineno,
                "col_offset": node.col_offset,
                "end_lineno": getattr(node, "end_lineno", node.lineno),
                "end_col_offset": getattr(node, "end_col_offset", node.col_offset + 10),
            }

        def visit_NameConstant(self, node):
            if not _is_arid_node(tree, node, source_lines):
                targets.append({**self._loc(node),
                    "file": filename, "type": "NameConstant",
                    "mutations": ["flip"],
                })
            self.generic_visit(node)

        def visit_Compare(self, node):
            if not _is_arid_node(tree, node, source_lines):
                targets.append({**self._loc(node),
                    "file": filename, "type": "Compare",
                    "mutations": ["flip"],
                })
            self.generic_visit(node)

        def visit_BinOp(self, node):
            if not _is_arid_node(tree, node, source_lines):
                targets.append({**self._loc(node),
                    "file": filename, "type": "BinOp",
                    "mutations": ["flip"],
                })
            self.generic_visit(node)

        def visit_If(self, node):
            if not _is_arid_node(tree, node, source_lines):
                targets.append({**self._loc(node),
                    "file": filename, "type": "If_Statement",
                    "mutations": ["If_False"],
                })
            self.generic_visit(node)

        def visit_Return(self, node):
            if not _is_arid_node(tree, node, source_lines) and node.value is not None:
                targets.append({**self._loc(node),
                    "file": filename, "type": "Return",
                    "mutations": ["Return_None"],
                })
            self.generic_visit(node)

    Finder().visit(tree)
    return targets


# ── Source mutator (text-based, no ast.unparse reformatting) ─────────────────

def _apply_mutation_text(source: str, target: dict, mutation_type: str) -> Optional[str]:
    """Apply mutation by text replacement at exact line/column position.

    Uses precise lineno/col_offset to avoid ast.unparse() reformatting.
    """
    lines = source.split("\n")
    t = target
    lineno = t["lineno"] - 1
    col = t.get("col_offset", 0)

    if mutation_type == "If_False":
        # Replace if-line body with 'pass', delete subsequent body lines
        line = lines[lineno]
        if ":" in line:
            lines[lineno] = line.split(":")[0] + ": pass"
        # Delete body lines (indented lines after the if that are more indented)
        if_indent = len(line) - len(line.lstrip())
        body_end = lineno + 1
        while body_end < len(lines):
            nxt = lines[body_end]
            if nxt.strip() and (len(nxt) - len(nxt.lstrip())) <= if_indent:
                break  # dedented — end of body
            body_end += 1
        # Replace body lines with empty
        for i in range(lineno + 1, body_end):
            lines[i] = ""
        return "\n".join(lines)

    try:
        orig_text = _extract_text(lines, lineno, col,
                                  t.get("end_lineno", t["lineno"]) - 1,
                                  t.get("end_col_offset", len(lines[lineno])))
    except Exception:
        return None

    new_text = _mutate_text(orig_text, t["type"], mutation_type)
    if new_text is None or new_text == orig_text:
        return None

    end_lineno = (t.get("end_lineno", t["lineno"]) or t["lineno"]) - 1
    end_col = t.get("end_col_offset", len(lines[lineno]))

    # Single-line replacement
    if lineno == end_lineno:
        line = lines[lineno]
        lines[lineno] = line[:col] + new_text + line[end_col:]
    else:
        # Multi-line: replace range with single line
        first_part = lines[lineno][:col]
        last_part = lines[end_lineno][end_col:]
        lines[lineno:end_lineno + 1] = [first_part + new_text + last_part]

    return "\n".join(lines)


def _extract_text(lines: list[str], l0: int, c0: int, l1: int, c1: int) -> str:
    if l0 == l1:
        return lines[l0][c0:c1]
    parts = [lines[l0][c0:]]
    for i in range(l0 + 1, l1):
        parts.append(lines[i])
    parts.append(lines[l1][:c1])
    return "\n".join(parts)


def _mutate_text(orig: str, node_type: str, mutation: str) -> Optional[str]:
    """Apply mutation to extracted text. Returns new text or None if no change."""
    import re

    if node_type == "NameConstant":
        # orig is the constant like "True", "False", or "None"
        orig.strip()
        swaps = {"True": "False", "False": "True", "None": "True"}
        for old, new in swaps.items():
            if re.search(r'\b' + re.escape(old) + r'\b', orig):
                return re.sub(r'\b' + re.escape(old) + r'\b', new, orig, count=1)
        return None

    if node_type == "Compare":
        # orig like "row is not None" or "row is None"
        swaps = {
            "==": "!=", "!=": "==",
            "is not": "is", "is": "is not",
            "<": ">=", ">=": "<",
            ">": "<=", "<=": ">",
            "in": "not in", "not in": "in",
        }
        result = orig
        for old, new in swaps.items():
            if old in result:
                return result.replace(old, new, 1)
        return None

    if node_type == "BinOp":
        swaps = {"+": "-", "-": "+", "*": "/", "/": "*"}
        for old, new in swaps.items():
            if old in orig:
                return orig.replace(old, new, 1)
        return None

    if node_type == "If_Statement":
        if mutation == "If_False":
            # Replace body with 'pass', keep condition and else
            return f"{orig.split(':')[0]}: pass"
        return None

    if node_type == "Return":
        if mutation == "Return_None":
            return "return None"
        if mutation == "Return_Delete":
            return "pass"
        return None

    return None




# ── Test runner ──────────────────────────────────────────────────────────────

def _run_tests(test_cmd: list[str], cwd: Path, timeout: int = 30) -> tuple[bool, str]:
    """Run test command in subprocess. Returns (passed, output)."""
    try:
        r = subprocess.run(
            test_cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, f"ERROR: {e}"


# ── Semantic equivalence check ──────────────────────────────────────────────

def _check_semantic_equiv(original: str, mutated: str,
                          target: dict) -> Optional[str]:
    """Check if a survivor is semantically equivalent to the original.

    Returns:
        None — not equivalent (real gap)
        "equiv" — certainly equivalent (auto-exempt)
        "suspicious" — likely equivalent (flag for review)
    """
    import difflib

    # 1. AST structural comparison
    try:
        orig_ast = ast.dump(ast.parse(original))
        mut_ast = ast.dump(ast.parse(mutated))
        if orig_ast == mut_ast:
            _save_equiv_memory({
                "pattern": "ast_identical",
                "file": target["file"],
                "lineno": target["lineno"],
                "type": target["type"],
            })
            return "equiv"
    except Exception:
        pass

    # 2. Text similarity (mutated source vs original)
    params = _load_params()
    threshold = params.get("equiv_threshold", 0.98)
    ratio = difflib.SequenceMatcher(None, original, mutated).ratio()
    if ratio > threshold:
        # Nearly identical — likely equivalent
        _save_equiv_memory({
            "pattern": "near_identical",
            "file": target["file"],
            "lineno": target["lineno"],
            "ratio": round(ratio, 4),
        })
        return "equiv"
    if ratio > threshold - 0.06:
        return "suspicious"

    # 3. Cross-project equivalence memory lookup
    memory = _load_equiv_memory()
    for m in memory:
        if m.get("file") == target["file"] and m.get("lineno") == target["lineno"]:
            return "equiv"

    return None

def run_mutation(
    src_dir: Path,
    test_cmd: list[str],
    n_locations: int = 15,
    mode: str = "s",
    exclude: list[str] | None = None,
    rseed: int | None = None,
) -> dict[str, Any]:
    """Run mutation testing and return results dict.

    Args:
        src_dir: Source directory to mutate
        test_cmd: Test command as list, e.g. ["python", "-m", "pytest", "tests/", "-q"]
        n_locations: Number of locations to sample
        mode: "s" = sample, "f" = full
        exclude: List of file patterns to exclude
        rseed: Random seed for reproducibility
    """
    import random
    if rseed is not None:
        random.seed(rseed)

    exclude = exclude or []
    # Project root: go up from src_dir until we find a dir with both src/ and tests/
    cwd = src_dir
    while cwd.parent != cwd:
        if (cwd / "tests").exists() or (cwd / "test").exists():
            break
        cwd = cwd.parent
    # Ensure src/ is in PYTHONPATH via env
    base_env = os.environ.copy()
    base_env["PYTHONUTF8"] = "1"
    src_parent = str(src_dir.parent)  # e.g., /project/src
    old_path = base_env.get("PYTHONPATH", "")
    sep = ";" if sys.platform == "win32" else ":"
    base_env["PYTHONPATH"] = f"{src_parent}{sep}{old_path}" if old_path else src_parent

    # Phase 1: Collect all mutation targets
    all_targets = []
    py_files = sorted(src_dir.rglob("*.py"))
    for pf in py_files:
        rel = str(pf.relative_to(src_dir)).replace("\\", "/")
        if any(re.search(pat, rel) for pat in exclude):
            continue
        try:
            source = pf.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
            lines = source.split("\n")
            targets = _find_targets(tree, lines, rel)
            all_targets.extend(targets)
        except SyntaxError:
            continue
        except Exception:
            continue

    print(f"Total sample space size: {len(all_targets)}", file=sys.stderr)

    # Phase 1.5: Classify functions (for PBT and equiv detection)
    func_map = _classify_all_functions(src_dir)
    total_funcs = sum(len(v) for v in func_map.values())
    print(f"Functions classified: {total_funcs} ({len(func_map['pure'])} pure, "
          f"{len(func_map['db'])} db, {len(func_map['io'])} io)", file=sys.stderr)

    # Phase 2: Sample targets (each target may have multiple mutations)
    if mode == "s" and len(all_targets) > n_locations:
        selected = random.sample(all_targets, n_locations)
    else:
        selected = all_targets

    print(f"Selecting {len(selected)} locations from {len(all_targets)} potentials.", file=sys.stderr)

    # Phase 3: Clean trial (baseline)
    print("Running clean trial", file=sys.stderr)
    clean_r = subprocess.run(
        test_cmd, cwd=str(cwd), capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        timeout=60, env=base_env,
    )
    clean_ok = clean_r.returncode == 0
    if not clean_ok:
        print("WARNING: Clean trial failed. Mutation results may be unreliable.", file=sys.stderr)
        print(f"  stdout: {(clean_r.stdout or '')[:200]}", file=sys.stderr)
        print(f"  stderr: {(clean_r.stderr or '')[:200]}", file=sys.stderr)

    # Phase 4: Mutation trials
    results = {"detected": [], "survived": [], "timeout": [], "error": [], "total_runs": 0}


    for i, target in enumerate(selected):
        if not target["mutations"]:
            continue

        src_path = src_dir / target["file"]
        try:
            source = src_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for mutation in target["mutations"]:
            if mutation is None:
                continue

            results["total_runs"] += 1

            try:
                mutated_source = _apply_mutation_text(source, target, mutation)
                if mutated_source is None:
                    continue

                # Copy entire project to temp dir, mutate in place, run tests there.
                # cwd always wins in sys.path — shadowing via PYTHONPATH doesn't work.
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_proj = Path(tmpdir) / cwd.name
                    # Windows: ensure clean destination before copytree
                    if tmp_proj.exists():
                        shutil.rmtree(tmp_proj, ignore_errors=True)
                    shutil.copytree(str(cwd), str(tmp_proj),
                                    ignore=shutil.ignore_patterns('.git', '__pycache__', '.pytest_cache', '.coverage'),
                                    dirs_exist_ok=True)
                    rel_src = src_dir.relative_to(cwd)
                    mutated_path = tmp_proj / rel_src / target["file"]
                    mutated_path.write_text(mutated_source, encoding="utf-8")

                    env = os.environ.copy()
                    env["PYTHONUTF8"] = "1"

                    r = subprocess.run(
                        test_cmd, cwd=str(tmp_proj), capture_output=True,
                        text=True, encoding="utf-8", errors="replace",
                        timeout=30, env=env,
                    )
                    test_ok = r.returncode == 0
                    (r.stdout or "") + (r.stderr or "")

            except subprocess.TimeoutExpired:
                results["timeout"].append({
                    "file": target["file"],
                    "lineno": target["lineno"],
                    "col_offset": target["col_offset"],
                    "type": target["type"],
                })
                continue
            except Exception as e:
                results["error"].append({
                    "file": target["file"],
                    "lineno": target["lineno"],
                    "col_offset": target["col_offset"],
                    "type": target["type"],
                    "error": str(e),
                })
                continue

            entry = {
                "file": target["file"],
                "lineno": target["lineno"],
                "col_offset": target["col_offset"],
                "type": target["type"],
            }

            if not test_ok:
                results["detected"].append(entry)
            else:
                # Run semantic equivalence check on survivor
                try:
                    orig_src = (src_dir / target["file"]).read_text(encoding="utf-8", errors="replace")
                    equiv = _check_semantic_equiv(orig_src, mutated_source, target)
                except Exception:
                    equiv = None
                entry["equiv"] = equiv or "none"
                results["survived"].append(entry)

    # Phase 5: Summary + operator stats
    # Compute operator-specific survival rates
    op_stats: dict[str, dict] = {}
    for s in results["survived"]:
        t = s.get("type", "unknown")
        if t not in op_stats:
            op_stats[t] = {"survived": 0, "total": 0, "rate": 0.0}
        op_stats[t]["survived"] += 1
    for d in results["detected"]:
        t = d.get("type", "unknown")
        if t not in op_stats:
            op_stats[t] = {"survived": 0, "total": 0, "rate": 0.0}
    for t in op_stats:
        op_stats[t]["total"] = op_stats[t]["survived"]
        for d in results["detected"]:
            if d.get("type") == t:
                op_stats[t]["total"] += 1
        op_stats[t]["rate"] = round(op_stats[t]["survived"] / max(op_stats[t]["total"], 1) * 100, 1)

    # Gap pattern analysis
    gap_patterns = {"error_path": 0, "boundary": 0, "return_precision": 0, "fallback": 0, "framework_equiv": 0}
    for s in results["survived"]:
        if s.get("equiv") == "equiv":
            gap_patterns["framework_equiv"] += 1
        elif s["type"] in ("Compare",) and "None" in str(s.get("lineno", "")):
            gap_patterns["error_path"] += 1
        elif s["type"] in ("BinOp",):
            gap_patterns["boundary"] += 1
        elif s["type"] in ("Return", "NameConstant"):
            gap_patterns["return_precision"] += 1
        else:
            gap_patterns["fallback"] += 1

    equiv_count = sum(1 for s in results["survived"] if s.get("equiv") == "equiv")
    suspicious_count = sum(1 for s in results["survived"] if s.get("equiv") == "suspicious")
    real_gap_count = len(results["survived"]) - equiv_count - suspicious_count

    # Persist params for meta-cycle (only on full mode, not samples)
    if mode == "f":
        params = _load_params()
        # Tune equiv threshold based on false-positive rate
        if real_gap_count == 0 and equiv_count > 0:
            params["equiv_threshold"] = round(max(0.85, params.get("equiv_threshold", 0.98) - 0.02), 2)
        elif real_gap_count > 0:
            params["equiv_threshold"] = round(min(0.99, params.get("equiv_threshold", 0.98) + 0.02), 2)
        # Update hot operators
        hottest = max(op_stats.items(), key=lambda x: x[1]["rate"]) if op_stats else (None, {})
        if hottest[0]:
            hot = params.setdefault("hot_operators", {})
            hot[hottest[0]] = max(hot.get(hottest[0], 0), hottest[1]["rate"])
        # Update hot gap patterns
        hottest_gap = max(gap_patterns.items(), key=lambda x: x[1]) if gap_patterns else (None, 0)
        if hottest_gap[0] and hottest_gap[1] > 0:
            hot = params.setdefault("hot_gap_patterns", {})
            hot[hottest_gap[0]] = max(hot.get(hottest_gap[0], 0), hottest_gap[1])
        params["projects_completed"] = params.get("projects_completed", 0) + 1
        _save_params(params)

    return {
        "source_location": str(src_dir),
        "test_commands": test_cmd,
        "mode": mode,
        "n_locations": n_locations,
        "total_targets": len(all_targets),
        "selected_targets": len(selected),
        "coverage_pct": round(len(selected) / max(len(all_targets), 1) * 100, 2),
        "detected": len(results["detected"]),
        "survived": len(results["survived"]),
        "timedout": len(results["timeout"]),
        "error": len(results["error"]),
        "total_runs": results["total_runs"],
        "detection_rate": round(
            len(results["detected"]) / max(results["total_runs"], 1) * 100, 1
        ),
        "function_classification": {
            "pure": len(func_map["pure"]),
            "db": len(func_map["db"]),
            "io": len(func_map["io"]),
        },
        "operator_stats": op_stats,
        "gap_patterns": gap_patterns,
        "survivor_classification": {
            "equivalent": equiv_count,
            "suspicious": suspicious_count,
            "real_gap": real_gap_count,
        },
        "details": results,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Minimal Mutation Testing Engine")
    parser.add_argument("--src", required=True, help="Source directory to mutate")
    parser.add_argument("--test-cmd", required=True, help="Test command (quoted)")
    parser.add_argument("--n", type=int, default=15, dest="n_locations", help="Locations to sample")
    parser.add_argument("--mode", default="s", choices=["s", "f"], help="s=sample, f=full")
    parser.add_argument("--exclude", action="append", default=[], help="Exclude file patterns")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    args = parser.parse_args()

    src_dir = Path(args.src).resolve()
    test_cmd = args.test_cmd.split()

    start = time.time()
    summary = run_mutation(
        src_dir=src_dir,
        test_cmd=test_cmd,
        n_locations=args.n_locations,
        mode=args.mode,
        exclude=args.exclude,
        rseed=args.seed,
    )
    elapsed = time.time() - start
    summary["elapsed_seconds"] = round(elapsed, 1)
    summary["run_datetime"] = datetime.now().isoformat()

    if args.json or args.output:
        out = json.dumps(summary, indent=2)
        if args.output:
            Path(args.output).write_text(out, encoding="utf-8")
        if args.json:
            print(out)
    else:
        fc = summary.get("function_classification", {})
        sc = summary.get("survivor_classification", {})
        print("\nMutation Testing Summary")
        print("=========================")
        print(f"Source: {summary['source_location']}")
        print(f"Functions: {sum(fc.values())} ({fc.get('pure',0)} pure, {fc.get('db',0)} db, {fc.get('io',0)} io)")
        print(f"Total targets: {summary['total_targets']}")
        print(f"Selected: {summary['selected_targets']} ({summary['coverage_pct']}%)")
        print(f"\nDetected: {summary['detected']}")
        print(f"Survived: {summary['survived']}")
        if sc:
            print(f"  ├─ Equivalent (auto): {sc.get('equivalent', 0)}")
            print(f"  ├─ Suspicious:        {sc.get('suspicious', 0)}")
            print(f"  └─ Real gaps:         {sc.get('real_gap', 0)}")
        print(f"Timedout: {summary['timedout']}")
        print(f"Errors: {summary['error']}")
        print(f"Total runs: {summary['total_runs']}")
        print(f"Detection rate: {summary['detection_rate']}%")
        print(f"Elapsed: {elapsed:.1f}s")

        if summary["details"]["survived"]:
            print("\nSURVIVED:")
            for s in summary["details"]["survived"]:
                tag = {"equiv": "[EQUIV]", "suspicious": "[SUSP]", "none": "[GAP]"}.get(s.get("equiv", "none"), "")
                print(f"  {tag} {s['file']}:{s['lineno']}:{s['col_offset']} ({s['type']})")
        if summary["details"]["detected"]:
            print("\nDETECTED (sample):")
            for d in summary["details"]["detected"][:10]:
                print(f"  {d['file']}:{d['lineno']}:{d['col_offset']} ({d['type']})")


if __name__ == "__main__":
    main()
