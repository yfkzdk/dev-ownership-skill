# 可追溯性审计规范

> [来源: SDD Code Reviewer (mcpmarket.com) — requirement-to-code mapping + scope creep detection + compliance scoring]
> [来源: Traceability Matrix Generator (tessl.io) — bidirectional matrix: forward (REQ→IMPL) + backward (every test→justifying requirement)]
> [来源: Traceability Check (mcpmarket.com) — gap analysis + orphan requirements + rogue/unjustified code detection]
> [来源: Agile-V compliance-auditor — REQ→ART→TC→VER formal traceability chain + Non-Conformance alerting]
> [来源: Nokia SANER 2026 — 5-phase industrial traceability, 94% accuracy, discovered 20+ implementation gaps]

## 时机

项目所有代码完成后，Retrospect阶段第一步执行。
不通过 → 必须修正后才能进入审视报告的其余部分。

## 审计流程

### Step 1: 提取所有 Spec 条款

从 openspec/specs/ 或 SPEC.md 中提取所有带编号的条款（§X.Y格式），形成需求清单。

### Step 2: 提取所有代码单元

从 src/ 下遍历每个 .py 文件的每个公开类、公开方法、公开函数。形成代码单元清单。

### Step 3: 构建双向矩阵

#### 正向矩阵: SPEC → CODE

| Spec条款 | 条款摘要 | 对应文件:行号 | 对应函数/类 | 状态 |
|----------|---------|-------------|-----------|------|
| §1.1 | Money构造: amount为Decimal | money.py:15-28 | `Money.__init__` | 已实现 |
| §1.2 | 加法: 同币种 | money.py:42-50 | `Money.__add__` | 已实现 |
| §X.Y | ... | — | — | **缺失** |

#### 反向矩阵: CODE → SPEC

| 文件:行号 | 函数/类 | 用途摘要 | 对应Spec条款 | 状态 |
|-----------|---------|---------|-------------|------|
| money.py:15-28 | `Money.__init__` | 金额构造+float防御 | §1.1 | 有理由 |
| money.py:52-55 | `Money.round_to_cents` | 分位舍入 | §1.6 | 有理由 |
| src/helpers.py:5 | `format_phone` | 电话号码格式化 | — | **无主代码** |

### Step 4: 分类标记

| 类别 | 定义 | 处置 |
|------|------|------|
| **已实现** | 代码存在且对应spec条款 | 通过 |
| **实现缺失** | Spec条款存在但无对应代码 | 补实现 或 标记spec条款为"未来版本" |
| **无主代码** | 代码存在但无对应spec条款 | 补spec条款 或 删除代码 或 确认为必要的样板代码 |
| **测试缺失** | Spec条款有实现但无对应测试 | 补测试 |

### Step 5: 合规评分

```
正向覆盖率 = 已实现的spec条款数 / 总spec条款数
反向覆盖率 = 有spec依据的代码单元数 / 总代码单元数
测试覆盖率 = 有测试的spec条款数 / 总spec条款数

目标:
  正向覆盖率 = 100%（每条spec必须实现）
  反向覆盖率 ≥ 95%（允许少量样板代码如 __init__.py / __version__ / 类型别名）
  测试覆盖率 ≥ 90%
```

## 输出格式

```markdown
# 可追溯性审计报告

## 合规评分

| 指标 | 值 | 目标 | 状态 |
|------|-----|------|------|
| 正向覆盖率 (SPEC→CODE) | X% | 100% | 通过/不通过 |
| 反向覆盖率 (CODE→SPEC) | X% | ≥95% | 通过/不通过 |
| 测试覆盖率 | X% | ≥90% | 通过/不通过 |

## 实现缺失

| Spec条款 | 要求 | 影响 | 建议 |
|----------|------|------|------|
| §X.Y | ... | 功能不完整 | 立即补实现 |

## 无主代码

| 文件:行号 | 代码片段 | 分析 | 处置建议 |
|-----------|---------|------|---------|
| src/extra.py:5 | `def helper_func()` | 未被任何spec条款引用 | 删除 / 补spec / 确认样板 |

## 测试缺失

| Spec条款 | 实现文件 | 缺失的测试场景 |
|----------|---------|--------------|
| §X.Y | ... | 边界情况未覆盖 |
```

## 硬性规则

- **必须逐个类遍历**，不能抽样。审计报告中必须列出所有类
- 每个代码单元的判定必须引用**实际代码行号**作为证据
- 「无主代码」不能直接删除——先标记，由开发者在中间审查时做处置决策
- 正向覆盖率 < 100% → 必须修正后才能继续Retrospect其余步骤
