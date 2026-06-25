#!/usr/bin/env bash
# pre-commit-check.sh — Quality Gate Runner (Testing Trophy Layer 0)
# Hard block: fail = commit rejected.
# Usage: bash scripts/pre-commit-check.sh [--skip-slow]

set -euo pipefail
EXIT_CODE=0
SKIP_SLOW="${1:-}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; EXIT_CODE=1; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

echo -e "${BOLD}=== Quality Gates — Layer 0 (Static Analysis) ===${NC}"
echo ""

# ── Cross-phase commit detection ────────────────────────────────────────────

staged=$(git diff --cached --name-only 2>/dev/null || true)
has_spec=$(echo "$staged" | grep -cE 'openspec/|SPEC\.md|DESIGN\.md|proposal\.md' 2>/dev/null || echo 0)
has_src=$(echo "$staged" | grep -cE 'src/|\.py$|\.go$|\.ts$|\.js$|\.java$' 2>/dev/null || echo 0)

if [ "$has_spec" -gt 0 ] && [ "$has_src" -gt 0 ]; then
    log_warn "Cross-phase commit detected (spec + src in same commit)"
    echo "  Consider splitting into separate atomic commits per phase."
    echo "  Rule: docs and code must be in separate commits."
    echo ""
fi

# ── Lint ─────────────────────────────────────────────────────────────────────

echo "--- Lint ---"
LINT_CMD=""
for cmd in ruff eslint golangci-lint; do
    if command -v "$cmd" &>/dev/null; then
        LINT_CMD="$cmd"
        break
    fi
done

if [ -n "$LINT_CMD" ]; then
    case "$LINT_CMD" in
        ruff)
            if ruff check . 2>&1; then
                log_pass "ruff — clean"
            else
                log_fail "ruff — lint errors (fix before commit)"
            fi
            ;;
        eslint)
            if eslint . 2>&1; then
                log_pass "eslint — clean"
            else
                log_fail "eslint — lint errors (fix before commit)"
            fi
            ;;
        golangci-lint)
            if golangci-lint run ./... 2>&1; then
                log_pass "golangci-lint — clean"
            else
                log_fail "golangci-lint — lint errors (fix before commit)"
            fi
            ;;
    esac
else
    log_warn "No linter found (install ruff/eslint/golangci-lint)"
fi

# ── Type Check ───────────────────────────────────────────────────────────────

echo ""
echo "--- Type Check ---"
TYPECHECK_CMD=""
for cmd in mypy tsc gopls; do
    if command -v "$cmd" &>/dev/null; then
        TYPECHECK_CMD="$cmd"
        break
    fi
done

if [ -n "$TYPECHECK_CMD" ]; then
    case "$TYPECHECK_CMD" in
        mypy)
            if [ -d "src" ]; then
                if mypy --strict src/ 2>&1; then
                    log_pass "mypy — type check passed"
                else
                    log_fail "mypy — type errors (fix before commit)"
                fi
            fi
            ;;
        tsc)
            if npx tsc --noEmit 2>&1; then
                log_pass "tsc — type check passed"
            else
                log_fail "tsc — type errors (fix before commit)"
            fi
            ;;
        gopls)
            if go vet ./... 2>&1; then
                log_pass "go vet — clean"
            else
                log_fail "go vet — issues (fix before commit)"
            fi
            ;;
    esac
else
    log_warn "No type checker found"
fi

# ── Security ─────────────────────────────────────────────────────────────────

echo ""
echo "--- Security Scan ---"

if command -v bandit &>/dev/null && [ -d "src" ]; then
    if bandit -r src/ -ll 2>&1; then
        log_pass "bandit — no issues"
    else
        log_fail "bandit — security issues (fix before commit)"
    fi
elif command -v gitleaks &>/dev/null; then
    if gitleaks detect --source . 2>&1; then
        log_pass "gitleaks — no secrets"
    else
        log_fail "gitleaks — secrets found (fix before commit)"
    fi
else
    log_warn "No security scanner found (install bandit/gitleaks)"
fi

# ── Dependency Audit ─────────────────────────────────────────────────────────

if command -v pip-audit &>/dev/null; then
    if pip-audit 2>&1; then
        log_pass "pip-audit — no vulns"
    else
        log_fail "pip-audit — dependency vulnerabilities"
    fi
elif command -v npm &>/dev/null && [ -f "package.json" ]; then
    if npm audit --audit-level=critical 2>&1; then
        log_pass "npm audit — no critical vulns"
    else
        log_fail "npm audit — vulnerabilities"
    fi
fi

# ── Summary ─────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}=== Quality Gates — Layer 1 (Test Suite) ===${NC}"
echo ""

if command -v pytest &>/dev/null; then
    if python -m pytest tests/ --cov=src --cov-branch --cov-fail-under=90 -q 2>&1; then
        log_pass "pytest + coverage ≥90%"
    else
        log_fail "Tests failed or coverage <90%"
    fi
elif command -v go &>/dev/null; then
    if go test -cover ./... 2>&1; then
        log_pass "go test — passed"
    else
        log_fail "go test — failed"
    fi
else
    log_warn "No test runner found"
fi

# ── Final ────────────────────────────────────────────────────────────────────

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}${BOLD}✓ All quality gates passed — commit allowed${NC}"
else
    echo -e "${RED}${BOLD}✗ Quality gates failed — commit blocked${NC}"
    echo "  Fix the issues above and re-commit."
fi

exit $EXIT_CODE
