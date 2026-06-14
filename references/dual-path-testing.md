# 双路径测试设计

> [来源: Cpicon/claude-code-plugins#5 — MCP → REST API 自动降级: Phase 0检测→Fallback→Graceful degradation]
> [来源: anthropics/claude-code#21536 — Synthetic Response Injection: BeforeModel hook + mock decision]
> [来源: immunize (PyPI) — 纯本地regex+subprocess匹配, 无需API调用]

## 原则

每个依赖外部资源的测试，必须同时具备：
- **Primary path**: 正常流程（连外部API/服务）
- **Fallback path**: API不可用时的本地fixture路径

## 触发Fallback的条件

以下任一条件满足时，自动切换到Fallback：

| 条件 | 检测方式 |
|------|---------|
| 网络超时 | curl 5秒超时探测 |
| HTTP 429 | Rate Limit响应 |
| HTTP 5xx | 服务端错误 |
| 认证凭证缺失 | 环境变量为空 |
| DNS解析失败 | host命令失败 |

## 三种Fallback实现方式

### 方式1: 本地Fixture（首选）

```
tests/
├── fixtures/
│   ├── country_codes.json     # E.164代码集离线副本
│   ├── exchange_rates.json    # 汇率离线副本（标注抓取日期）
│   └── api_responses/         # 预录的API响应（标注来源URL+抓取日期）
```

Fixture文件必须标注：
- 数据来源URL
- 抓取日期
- 有效期（如有）

### 方式2: Mock决策（Claude Code环境）

```
Hook: BeforeModel
  → 检测API不可用
  → decision: "mock"
  → 返回 syntheticResponse
```

### 方式3: 降级链

```
Primary (实时API) → Secondary (缓存副本) → Guaranteed (本地硬编码最小值)
```

## 运行机制

`scripts/fallback-test-runner.sh`:

```bash
# 1. 探测外部API可用性
# 2. 可用 → export USE_FIXTURES=false → 运行Primary测试
# 3. 不可用 → export USE_FIXTURES=true → 运行Fallback测试
```

## 验证规则

- Fallback路径的测试结果必须与Primary路径**语义等价**（相同输入→相同断言结果）
- Fallback测试必须在CI中**默认启用**（不依赖外部网络即可运行）
- 每个fixture文件标注**数据来源+抓取日期**，防止过期
- fixture过期（超过标注有效期）→ 测试输出WARNING但不失败
