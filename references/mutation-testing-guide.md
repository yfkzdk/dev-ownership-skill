# 突变测试 — 配置与使用指南

> 突变测试（Mutation Testing）是测量**测试质量**的唯一客观方法。
> 行覆盖率说"这行被跑过"，突变测试说"这行的 bug 被测出来过"。

## 原理

```
原始代码:        x = a + b
注入突变:        x = a - b   (将 + 改为 -)
运行测试:        如果测试仍然通过 → 突变存活 → 测试不够好
                如果测试失败     → 突变被杀死 → 测试有效
```

突变存活率 = 被杀死的突变 / 总注入突变。目标 ≥ 70%。

## Python 项目配置 (mutmut)

### 安装

```bash
pip install mutmut
```

### 配置 `pyproject.toml`

```toml
[tool.mutmut]
paths_to_mutate = "src/"
paths_to_exclude = "tests/"
runner = "python -m pytest"
switches = [
    "and_or",        # and ↔ or
    "comparison",    # > ↔ >=, == ↔ !=
    "number",        # 1 → 0, -1 → 1
    "string",        # "foo" → ""
    "slice_index",   # [0] → [1]
    "operator",      # + ↔ -
]
```

### 运行

```bash
# 运行突变测试
mutmut run

# 查看结果
mutmut results

# 生成 HTML 报告
mutmut html
```

## JavaScript/TypeScript 项目配置 (Stryker)

```bash
npx stryker init
# stryker.conf.json:
# {
#   "mutator": "javascript",
#   "packageManager": "npm",
#   "reporters": ["html", "clear-text", "progress"],
#   "testRunner": "jest",
#   "thresholds": { "high": 80, "low": 70, "break": 60 }
# }
```

## Go 项目配置

```bash
# 使用 go-mutesting
go install github.com/zimmski/go-mutesting/cmd/go-mutesting@latest
go-mutesting ./...
```

## 在 dev-ownership 流程中的使用

| 时机 | 动作 | 级别 |
|------|------|:--:|
| 每次 commit | 不跑（太慢，5-30分钟） | — |
| 每个阶段出口 | 运行，记录得分 | 软警告 |
| Review 阶段 | 审查突变报告，评估哪些测试需要加强 | — |
| Retrospect | 突变得分趋势对比 | 指标 |

## 突变得分作为 σ(t) 的输入

```
σ(t) = mutation_score × 0.6 + (1 - ai_rollback_rate) × 0.4
```

突变得分 < 70% 时：
- σ(t) 下降 → SR 下降 → 如果 SR < 2.4 → 门禁冻结
- 必须补强测试直到突变得分回到 70% 以上

## 快速参考

| 语言 | 工具 | 安装 | 运行时间 | 目标 |
|------|------|------|:--:|:--:|
| Python | mutmut | pip install mutmut | 5-20min | ≥70% |
| Java | PIT | Maven/Gradle plugin | 10-30min | ≥70% |
| JS/TS | Stryker | npm install @stryker-mutator/core | 5-30min | ≥70% |
| Go | go-mutesting | go install | 3-15min | ≥70% |
| Rust | cargo-mutants | cargo install | 10-40min | ≥70% |
