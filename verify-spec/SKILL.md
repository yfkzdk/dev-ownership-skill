---
name: verify-spec
version: 0.2.1
description: >-
  Code correctness verification against spec/ADR. Extracts verifiable rules
  from natural-language requirements, checks code compliance via LLM reasoning,
  adversarial debunking (Redhound pattern), golden-value spot-checks, and static
  health scans (dead code/over-engineering/redundancy/call loops). Invoke AFTER
  dev-ownership produces spec+ADR+code, BEFORE harden mutation testing.
  Triggers on: "verify code", "check correctness", "validate against spec",
  "代码正确性", "规则验证", "健康检查".
  NOT for: testing coverage (use harden), decision validation (use dev-ownership).
---

## 验证代码正确性 —— 不跑测试

> 规则提取 → 逐条验证 → **对抗去伪** → 金值比对 → 健康扫描。
> 覆盖 10 类代码错误（语法/类型/安全/死代码/冗余/过度设计/调用环/缺失实现/逻辑边界/业务规则值）。

```
dev-ownership 产出 spec/ADR + 代码
        ↓
Step 1: LLM 提取可验证规则 → rules.md (纯英语, ≤30条)
Step 2: Investigator Agent 逐条验证 → PASS/FAIL/UNCERTAIN + 代码行引用
Step 3: Debunker Agent 独立推翻每条 FAIL → 活下来的才是真 bug
Step 4: Golden Value 金值比对 → spec 的已知输入→期望输出，精确匹配
Step 5: 健康扫描 → 死代码/冗余/过度设计/调用环
Step 6: 修正 → FAIL 修正后重跑(≤2次), DISPUTED 你裁决
```

---

## 硬规则

1. **判断依据 = spec/ADR。** 不凭代码质量和最佳实践判断对错
2. **AI 不自审。** 验证和去伪必须用独立 Agent，禁止同一个 Agent 既找 bug 又判定它是假阳性 (Redhound 模式)
3. **金值最优先。** spec 有已知输入→期望输出 → 精确比对，偏差 >0.1% = FAIL，无视 Agent 的判断
4. **每个结论引用证据。** PASS→代码行, FAIL→违反条款+位置, DISPUTED→两个 Agent 的论点

---

## Step 1: 提取可验证规则

|| 内容 |
|------|------|
| **输入** | dev-ownership spec/ADR |
| **AI 提取** | 从自然语言需求中提取可验证规则。纯英语，不转 YAML/JSON (prosecheck 模式) |
| **规则类型** | 触发条件 / 值约束 / 状态转换 / 显式禁止 / **已知金值（输入→期望输出）** |
| **输出** | `rules.md` — 编号规则。`## R1: [描述]` + `#### 约束: [条件]` + `#### 金值: [如果有]` |
| **上限** | ≤30 条 (Zhou et al. 经验比率: 222 需求→75 规则=34%) |

---

## Step 2: Investigator Agent 逐条验证

**独立 Agent 1** — 只负责找证据，不管真假。

|| 结果 | 含义 | 证据要求 |
||------|------|------|
|| **PASS** | 代码遵守此规则 | 引用代码文件:行号，说明如何满足 |
|| **FAIL** | 代码违反此规则 | 引用违反的文件:行号 + 违反的规则条款号 |
|| **UNCERTAIN** | Agent 无法判断 | 说明为什么不确定（spec 模糊？代码间接？） |

**输出**: `rules-verified.md` — 每条规则一行 + 证据
**参考**: semcheck + Zhou et al. (2026) 两阶段验证

---

## Step 3: Debunker Agent 对抗去伪

**独立 Agent 2** — 目标与 Investigator 相反：**证明每个 FAIL 是假阳性。**

|| Investigator 说 | Debunker 判定 | 最终结论 |
||------|------|------|
|| FAIL | "我找到绕过它的方法" | **CONFIRMED** — 真 bug，引用两个 Agent 的论点 |
|| FAIL | "这里有运行时保护，它不会触发" | **OVERRULED** — 假阳性，引用 Debunker 的证据 |
|| FAIL | "我无法判断" | **DISPUTED** — 需要你裁决 |
|| PASS | (不检查) | PASS |
|| UNCERTAIN | (不检查) | 直接给你 |

**为什么**: grep 看到 `on_select` → PASS。但 `filter_brush` 从未被数据流入过。Investigator 可能漏，Debunker 专门查这个。
**参考**: Redhound (Canonical 2026) Debunking Agent — 3 个 CVE 9.1 零天发现

---

## Step 4: Golden Value 金值比对

**不依赖 Agent 判断。** spec/ADR 有已知输入→期望输出的，直接计算比对。

|| 输入 | 期望输出 | 代码输出 | 结论 |
||------|------|------|------|
|| 从 spec 提取 | 从 spec 提取 | 实际执行或 LLM 推算 | 偏差 >0.1% → FAIL |

金值在 Step 1 提取规则时标注。每个关键业务规则至少配一个金值。
**参考**: ApprovalTests golden master + equiv 哲学 (LLM 不唯一审查者)

---

## Step 5: 健康扫描

|| 检查项 | 工具 | 判定标准 |
||------|------|------|
|| 死代码 | Vulture | 从未被调用的函数/类/变量 |
|| 冗余 Type 1-2 | AST 结构相似度 | 两个函数 AST 结构相似 ≥85% |
|| 冗余 Type 3-4 | AST 粗筛(相似≥70%)→ LLM 语义判断 | 语法不同但功能相同的代码块 |
|| 无引用抽象 | AST 查 Factory/Adapter/Generic 类 | 0 外部引用 = FAIL |
|| 框架过重 | LLM 推理 | "引入的框架/库是否能用标准库替代" |
|| 不可测抽象 | mock 依赖分析 | 方法需要 >3 个 mock 才能测试 = FAIL |
|| 过度设计(旧) | AST 模式 | 嵌套 >3 / 参数 >5 / 单文件 >300 行 / 单方法类 |
|| 调用环 | call graph 遍历 | f1→f2→...→f1 形成回路 |

---

## Step 6: 修正

|| 结论 | 操作 | 谁做 |
||------|------|------|
|| **PASS** | 跳过 | — |
|| **CONFIRMED** | AI 提修正方案 → 修 → 重跑 Step 2+3 (≤2次) | **你决定**: 修 / 标记已知限制 / 回退 spec |
|| **DISPUTED** | Agent 1 和 Agent 2 的论点并列 | **你裁决**: 真 bug / 假阳性 / 不确定 → 不确定则标记 UNCERTAIN |
|| **OVERRULED** | 假阳性，记录 Debunker 证据 | 无需修正 |
|| **UNCERTAIN** | 直接给你 | **你判断** |

超过 2 次循环未闭合 → 标记 `TD-[日期]` 写入 known-traps。

---

## 报告

```
rules-verified.md:
  规则总数: N
  PASS: X (Investigator 确认通过)
  CONFIRMED: Y (两个 Agent 都同意是 bug)
  OVERRULED: Z (Debunker 推翻)
  DISPUTED: D (需要你裁决)

健康评分 (0-100):
  规则通过率×0.4 + 金值覆盖×0.3 + 健康检测×0.3
```

---

## 禁止行为

- 禁止验证 spec 没写的规则——范围以 spec/ADR 为准
- **禁止同一个 Agent 同时做 Investigator 和 Debunker** (Redhound 模式核心)
- 禁止只靠 LLM 判断——必须有代码行引用或金值比对作为证据
- 禁止修改代码后不重跑验证
- 禁止跳过 Step 3 (对抗去伪)

---

## 引用索引

| 文件 | 内容 | 何时加载 |
|------|------|---------|
| [../references/feynman-gate.md](../references/feynman-gate.md) | 费曼门禁规范 | 阶段出口 |
| [../references/known-traps.md](../references/known-traps.md) | 已验证陷阱清单 | Step 6 |

## 协议来源

| 机制 | 来源 |
|------|------|
| 规则提取→验证 两阶段 | Zhou et al. (May 2026) + semcheck |
| 纯英语规则 | prosecheck RULES.md |
| 对抗去伪 (Investigator/Debunker 双 Agent) | Redhound (Canonical 2026) |
| 金值优先 | ApprovalTests + equiv 哲学 |
| 健康扫描 | Vulture + AST + Mollify/Drift 信号 |
