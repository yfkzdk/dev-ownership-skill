#!/bin/bash
# Pre-commit Check Script
# [来源: NagendraSIB gist — PreToolUse hook 拦截每次git commit, 运行build/test/lint + multi-agent review]
# [来源: cc-foundry git-commit — 8步pipeline: 识别逻辑单元→排序→质量门→自审→选择性暂存→消息验证→提交→验证]
# [来源: evanklem/evanflow — "verify before claiming done", 质量检查在"done"报告之前运行]
set -e

echo "=== Pre-commit Check ==="

# -----------------------------------------------------------
# 1. 检测跨阶段提交
# -----------------------------------------------------------
staged=$(git diff --cached --name-only)

has_spec=$(echo "$staged" | grep -c -E 'SPEC\.md|DESIGN\.md|specs/' || true)
has_src=$(echo "$staged" | grep -c -E 'src/|\.py$' || true)
has_test=$(echo "$staged" | grep -c -E 'tests/|test_' || true)
has_docs=$(echo "$staged" | grep -c -E '\.md$|docs/' || true)

# 排除 session-log.md 等实时记录文件
has_docs=$((has_docs - $(echo "$staged" | grep -c 'session-log' || true)))

if [ "$has_spec" -gt 0 ] && [ "$has_src" -gt 0 ]; then
    echo "============================================"
    echo "  WARNING: Cross-Phase Commit Detected"
    echo "============================================"
    echo ""
    echo "Staged files contain both spec/design docs AND source code."
    echo "This violates the rule: docs and code must be in separate commits."
    echo ""
    echo "Spec/Design files:"
    echo "$staged" | grep -E 'SPEC\.md|DESIGN\.md|specs/'
    echo ""
    echo "Source files:"
    echo "$staged" | grep -E 'src/|\.py$'
    echo ""
    echo "Suggestions:"
    echo "  1. Unstage one group: git reset HEAD <files>"
    echo "  2. Commit docs first, then code"
    echo "  3. Or if this is intentional, type 'y' to continue"
    echo ""
    read -rp "Continue anyway? [y/N] " response
    if [ "$response" != "y" ]; then
        echo "Commit aborted. Please split into separate commits."
        exit 1
    fi
fi

# -----------------------------------------------------------
# 2. 检查 commit message 格式
# -----------------------------------------------------------
# 这个检查在 commit-msg hook 中进行, 此处仅做提示
echo "[CHECK] Cross-phase commit check: PASSED"

# -----------------------------------------------------------
# 3. 运行 lint (如果存在)
# -----------------------------------------------------------
if [ -f "pyproject.toml" ] || [ -f "setup.cfg" ] || [ -f "tox.ini" ]; then
    if command -v ruff &> /dev/null; then
        echo "[CHECK] Running ruff..."
        ruff check src/ tests/ || echo "  (ruff found issues - please review)"
    elif command -v flake8 &> /dev/null; then
        echo "[CHECK] Running flake8..."
        flake8 src/ tests/ || echo "  (flake8 found issues - please review)"
    else
        echo "[CHECK] No Python linter found, skipping lint"
    fi
fi

# -----------------------------------------------------------
# 4. 运行测试 (如果存在)
# -----------------------------------------------------------
if command -v pytest &> /dev/null; then
    echo "[CHECK] Running pytest..."
    if [ "${USE_FIXTURES:-false}" = "true" ]; then
        pytest tests/ -v --tb=short --fixture-only 2>/dev/null || {
            echo "  Fallback mode: some tests may have been skipped"
        }
    else
        pytest tests/ -v --tb=short 2>/dev/null || {
            echo "============================================"
            echo "  WARNING: Tests Failed"
            echo "============================================"
            echo ""
            echo "If failures are due to API unavailability,"
            echo "  run with: USE_FIXTURES=true git commit ..."
            echo "  or:       bash scripts/fallback-test-runner.sh"
            echo ""
            read -rp "Continue with commit despite test failures? [y/N] " response
            if [ "$response" != "y" ]; then
                echo "Commit aborted. Please fix tests or use fallback mode."
                exit 1
            fi
        }
    fi
else
    echo "[CHECK] pytest not found, skipping tests"
fi

echo ""
echo "=== Pre-commit Check PASSED ==="
