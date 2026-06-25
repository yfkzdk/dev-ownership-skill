# Fixtures — 离线测试数据

## 用途

当外部API不可用时，此目录提供本地离线数据以供测试使用。

## 使用方式

```bash
# 自动检测: API可用→在线 / API不可用→fixture
bash scripts/fallback-test-runner.sh

# 强制使用fixture
USE_FIXTURES=true pytest tests/ -v
```

## Fixture文件规范

每个fixture文件必须包含以下元数据（JSON格式）：

```json
{
    "source_url": "https://api.example.com/v1/data",
    "fetch_date": "2026-06-14",
    "expiry_date": "2026-12-14",
    "description": "E.164 country codes snapshot for offline testing"
}
```

## 目录结构

```
fixtures/
├── README.md              # 本文件
├── country_codes.json     # E.164国家代码离线副本
├── exchange_rates.json    # 汇率离线副本
└── api_responses/         # 预录API响应
    ├── get_rate_200.json
    └── get_rate_429.json
```
