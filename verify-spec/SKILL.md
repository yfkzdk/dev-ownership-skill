---
name: verify-spec
version: 0.1.0
description: >-
  Code correctness verification against spec/ADR. Extracts verifiable rules
  from natural-language requirements, checks code compliance via LLM reasoning,
  golden-value spot-checks, and static health scans (dead code/over-engineering/
  redundancy/call loops). Invoke AFTER dev-ownership produces spec+ADR+code,
  BEFORE harden mutation testing. Triggers on: "verify code", "check correctness",
  "validate against spec", "代码正确性", "规则验证", "健康检查".
  NOT for: testing coverage (use harden), decision validation (use dev-ownership).
---

## 验证代码正确性 —— 不跑测试

> 从 spec/ADR 提取可验证规则 → LLM 逐条检查代码是否遵守 → 金值抽查 + 健康扫描兜底。

```
dev-ownership 产出 spec/ADR + 代码
        ↓
Step 1: LLM 提取可验证规则 → rules.md (纯英语, ≤30条)
Step 2: 逐条验证 → PASS/FAIL/UNCERTAIN + 引用代码行
Step 3: 健康扫描 → 死代码/冗余/过度设计/调用环
Step 4: 修正 → FAIL 修正后重跑 (≤2次), UNCERTAIN 你判断
```

---

## 硬规则

1. **判断依据 = spec/ADR。** 不凭代码质量和最佳实践判断对错。spec 写了什么就检查什么
2. **LLM 不唯一审查者。** 金值抽查 + Vulture/AST 兜底 (equiv 哲学)
3. **每个结论引用证据。** PASS→代码行, FAIL→违反条款+位置, UNCERTAIN→说明为什么不确定

---

## Step 1: 提取可验证规则

|| 内容 |
|------|------|
| **输入** | dev-ownership spec/ADR |
| **AI 提取** | 从自然语言需求中提取可验证规则。只用纯英语写，不转 YAML/JSON (prosecheck 模式) |
| **规则类型** | 触发条件 / 值约束 / 状态转换 / 显式禁止 |
| **输出** | `rules.md` — 编号规则列表。结构: `## R1: [描述]` + `#### 约束: [具体条件]` |
| **上限** | ≤30 条。从 222 条需求→75 规则=34% 的经验比率 (Zhou et al.) |

```
示例:
## R4: 折扣率必须在 0-50% 范围内
#### 约束: 函数 calculate_price 的 discount_rate 参数 ∈ [0, 50]
#### 来源: spec 条款 T3 "折扣范围"
```

---

## Step 2: 逐条验证

|| 结果 | 含义 | 证据要求 |
||------|------|------|
|| **PASS** | 代码遵守此规则 | 引用代码文件:行号，说明如何满足 |
|| **FAIL** | 代码违反此规则 | 引用违反的文件:行号 + 违反的规则条款号 |
|| **UNCERTAIN** | LLM 无法判断 | 说明为什么不确定（spec 模糊？代码间接？） |

**金值抽查**: spec/ADR 有已知输入→期望输出的→精确比对实际值。
- 代码偏值 > 0.1% → FAIL，无视其他 PASS。
**输出**: `rules-verified.md` — 每条规则一行 PASS/FAIL/UNCERTAIN + 证据
**参考**: semcheck 两阶段验证 + TRAILS category partitioning

---

## Step 3: 健康扫描

|| 检查项 | 工具 | 判定标准 |
||------|------|------|
|| 死代码 | Vulture | 从未被调用的函数/类/变量 |
|| 冗余 | AST 结构相似度 | 两个函数 AST 结构相似 ≥85% |
|| 过度设计 | AST 模式 | 嵌套 >3 / 参数 >5 / 单文件 >300 行 / 单方法类 |
|| 调用环 | call graph 遍历 | f1→f2→...→f1 形成回路 |

---

## Step 4: 修正

|| 验证结果 | 操作 | 谁做 |
||------|------|------|
|| **PASS** | 跳过 | — |
|| **FAIL** | AI 提修正方案 → 修正 → 重跑 Step 2 ≤2 次 | **你决定**: 修 / 标记"已知限制" / 回退 spec |
|| **UNCERTAIN** | 直接给你 | **你判断**: 是真问题还是 LLM 判断错 |

超过 2 次循环未闭合 → 标记 `TD-[日期]` 写入 known-traps。

---

## 报告

```
rules-verified.md:
  规则通过率: N/M
  FAIL: 违反的规则 + 修正状态
  UNCERTAIN: 需人工判断的条目

健康评分 (0-100):
  规则通过率 × 0.5 + 健康检测 × 0.3 + 金值覆盖 × 0.2
```

---

## 禁止行为

- 禁止验证 spec 没写的规则——范围以 spec/ADR 为准
- 禁止只靠 LLM 判断——必须有代码行引用或金值比对作为证据
- 禁止修改代码后不重跑验证
- 禁止跳过 Step 3（健康扫描）

---

## 引用索引

| 文件 | 内容 | 何时加载 |
|------|------|---------|
| [../dev-ownership/references/feynman-gate.md](../dev-ownership/references/feynman-gate.md) | 费曼门禁规范 | 阶段出口 |
| [../dev-ownership/references/known-traps.md](../dev-ownership/references/known-traps.md) | 已验证陷阱清单 | Step 4 |
