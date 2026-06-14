#!/bin/bash
# Fallback Test Runner
# [来源: Cpicon/claude-code-plugins#5 — MCP→REST API 自动降级模式]
# [来源: anthropics/claude-code#21536 — syntheticResponse mock机制]
# [来源: immunize (PyPI) — 纯本地执行, 无需API]
#
# 先探测外部API可用性。
# 可用 → 运行Primary测试。
# 不可用 → 自动切换到本地fixture运行Fallback测试。

set -e

API_ENDPOINT="${API_HEALTH_CHECK_URL:-https://api.example.com/health}"
FIXTURE_DIR="${FIXTURE_DIR:-tests/fixtures}"

echo "=== Fallback Test Runner ==="
echo ""

# -----------------------------------------------------------
# 探测外部API
# -----------------------------------------------------------
api_available=false

echo "[PROBE] Checking API availability: ${API_ENDPOINT}"
if curl -s --max-time 5 "${API_ENDPOINT}" > /dev/null 2>&1; then
    api_available=true
    echo "[PROBE] API available"
else
    echo "[PROBE] API unavailable (timeout/DNS/connection refused)"
fi

# 检查fixture是否就绪
fixture_ready=false
if [ -d "${FIXTURE_DIR}" ] && [ "$(ls -A "${FIXTURE_DIR}" 2>/dev/null)" ]; then
    fixture_ready=true
    echo "[PROBE] Fixtures found in ${FIXTURE_DIR}"
else
    echo "[PROBE] No fixtures found in ${FIXTURE_DIR}"
fi

# -----------------------------------------------------------
# 运行测试
# -----------------------------------------------------------
if $api_available; then
    echo ""
    echo ">>> Running PRIMARY tests (API available) <<<"
    export USE_FIXTURES=false
    pytest tests/ -v --tb=short "$@"
    exit_code=$?
else
    if $fixture_ready; then
        echo ""
        echo ">>> Running FALLBACK tests (using local fixtures) <<<"
        export USE_FIXTURES=true
        pytest tests/ -v --tb=short --fixture-only "$@"
        exit_code=$?
    else
        echo ""
        echo ">>> ERROR: API unavailable AND no local fixtures <<<"
        echo "Cannot run tests. Either:"
        echo "  1. Restore API connectivity"
        echo "  2. Create fixtures: mkdir -p ${FIXTURE_DIR} && populate with test data"
        exit 2
    fi
fi

echo ""
if [ $exit_code -eq 0 ]; then
    echo "=== Tests PASSED ==="
else
    echo "=== Tests FAILED (exit code: ${exit_code}) ==="
fi

exit $exit_code
