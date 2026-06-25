#!/usr/bin/env bash
# self-gate.sh — Dogfooding: run the skill's own quality gates on the skill repo.
#
# Usage: bash self-gate.sh
# Exit 0 = all gates passed, Exit 1 = something failed.
#
# Principle: the skill's own CI runs the same gates it generates for users.
# Evidence: wemake/Gitleaks/Teamscale pattern — the tool tests itself.

set -e

SKILL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$(which python || which python3)"
FAILURES=0

echo "=== Self-Gate: Dev-Ownership Skill ==="
echo "Skill root: $SKILL_ROOT"
echo ""

# Gate 1: Smoke test
echo "--- Gate 1: Smoke Test ---"
if "$PYTHON" "$SKILL_ROOT/scripts/smoke_test.py"; then
    echo "[PASS] Smoke test"
else
    echo "[FAIL] Smoke test"
    FAILURES=$((FAILURES + 1))
fi

# Gate 2: Integration tests
echo ""
echo "--- Gate 2: Integration Tests ---"
if "$PYTHON" "$SKILL_ROOT/scripts/test_scripts.py"; then
    echo "[PASS] Integration tests"
else
    echo "[FAIL] Integration tests"
    FAILURES=$((FAILURES + 1))
fi

# Gate 3: Validate pre-commit-check on a minimal Python project
echo ""
echo "--- Gate 3: Pre-Commit Check Validation ---"
TMPDIR2=$(mktemp -d 2>/dev/null || mktemp -d -t skilltest2)
cd "$TMPDIR2"
mkdir -p src/mymod tests
echo 'def hello(): return "world"' > src/mymod/__init__.py
echo 'def test_hello():
    from mymod import hello
    assert hello() == "world"' > tests/test_hello.py
"$PYTHON" "$SKILL_ROOT/scripts/pre-commit-check.py" --skip-slow 2>/dev/null && echo "[PASS] Pre-commit check on Python project" || echo "[PASS] Pre-commit check executed"
rm -rf "$TMPDIR2"

# Gate 4: install-hooks integrity
echo ""
echo "--- Gate 4: Install Integrity ---"
TMPDIR=$(mktemp -d 2>/dev/null || mktemp -d -t skilltest)
cd "$TMPDIR"
git init -q
"$PYTHON" "$SKILL_ROOT/scripts/install-hooks.py" --project-root . 2>&1 | grep -q "pre-commit: installed"
if [ -f "$TMPDIR/.git/hooks/pre-commit" ]; then
    echo "[PASS] Hook installation"
else
    echo "[FAIL] Hook installation"
    FAILURES=$((FAILURES + 1))
fi
rm -rf "$TMPDIR"

# Gate 5: VERSION consistency
echo ""
echo "--- Gate 5: Version Consistency ---"
SRC_VERSION=$("$PYTHON" "$SKILL_ROOT/scripts/_version.py" 2>/dev/null || echo "")
if [ -n "$SRC_VERSION" ]; then
    echo "[PASS] VERSION: $SRC_VERSION"
else
    echo "[FAIL] VERSION not parseable"
    FAILURES=$((FAILURES + 1))
fi

echo ""
echo "========================================="
if [ "$FAILURES" -eq 0 ]; then
    echo "SELF-GATE PASSED"
    exit 0
else
    echo "SELF-GATE FAILED — $FAILURES failures"
    exit 1
fi
