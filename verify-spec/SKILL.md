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

> 规则提取 → Spec自检 → 逐条验证 → **对抗去伪** → 金值比对 → 健康扫描。
> 覆盖: 缺失实现/逻辑边界/业务规则值/死代码/冗余/过度设计/调用环。
> 语法/类型/安全 由 pre-commit hook (ruff/mypy/bandit) + harden Step 0.5 负责，不在此 skill 范围内。

```
dev-ownership 产出 spec/ADR + 代码
        ↓
Step 1: LLM 提取可验证规则 → rules.md (纯英语, ≤30条)
Step 1.5: Spec Sanity Check → 检查 spec 自身的矛盾/歧义/缺失分支
Step 2: Investigator Agent 逐条验证 → PASS/FAIL/UNCERTAIN + 代码行引用
Step 3: Debunker Agent 独立审查 PASS + 推翻 FAIL → 活下来的才是真 bug
Step 4: Golden Value 金值比对 → spec 的已知输入→期望输出，精确匹配
Step 5: 健康扫描 → 死代码/冗余/过度设计/调用环
Step 6: 修正 → 修正后重跑 Step 2-5 (≤2次), DISPUTED 你裁决
```

---

## 硬规则

1. **判断依据 = spec/ADR。** 不凭代码质量和最佳实践判断对错
2. **AI 不自审——结构隔离。** Investigator 和 Debunker 必须分别在**独立对话 session** 中执行。信息传递仅通过 `rules-verified.md` 文本文件，禁止共享对话上下文 (pi-adversary private Message[] 模式)
3. **金值最优先。** 每个关键业务规则自动推导 ≥5 组已知输入→期望输出。金值偏差 >0.1% = FAIL，无视任何 Agent 判断。金值为 0 的规则 → UNCERTAIN，不进入 PASS/FAIL 判定
4. **每个结论引用证据。** PASS→代码行, FAIL→违反条款+位置, DISPUTED→两个 Agent 的论点
5. **Debunker 审查全量。** 不只看 FAIL——PASS 抽样 30% + 全部 FAIL + 全部 UNCERTAIN (bug-hunt Skeptic 模式)
6. **修正后全量重跑。** Step 6 修正代码后，必须重跑 Step 2-5 全部，不可只重跑部分 (bug-hunter post-fix re-scan)

---

## Step 1: 提取可验证规则

|| 内容 |
|------|------|
| **输入** | dev-ownership spec/ADR |
| **AI 提取** | 从自然语言需求中提取可验证规则。纯英语，不转 YAML/JSON (prosecheck 模式) |
| **规则类型** | 触发条件 / 值约束 / 状态转换 / 显式禁止 |
| **金值生成（强制）** | 从 **spec 原文**提取已知输入→期望输出对。优先从 T1-T10 等验收条款提取。spec 无显式金值的规则 → LLM 推导一组后→LLM 二次交叉确认偏差 ≤0.1%→通过; 偏差 >0.1% → 标记 UNCERTAIN。金值为 0 的规则 → UNCERTAIN |
| **输出** | `rules.md` — 编号规则 + 约束 + 金值 |
| **上限** | ≤30 条 (Zhou et al. 经验比率: 222 需求→75 规则=34%) |

---

## Step 1.5: Spec Sanity Check（强制）

**在拿 spec 当真理之前，先质疑 spec。**

|| 检查 | 判定 |
||------|------|
|| **矛盾** | 两条规则互斥（如"满100减10" vs "满100减20"）→ ABORT，抛出矛盾条款给开发者 |
|| **歧义** | 规则描述模糊，无法提取具体约束 → 标记 UNCERTAIN，不进入验证 |
|| **缺失分支** | 规则有 if 但没有 else → 记录到 rules.md 的"不确定"字段 |
|| **不可验证** | 规则纯主观（如"界面要好看"）→ 标记为 EXCLUDED，不进入验证 |

发现矛盾或大面积歧义 → **中断执行**，直接报告给开发者，不以错误的 spec 为基准继续。
只对通过 sanity check 的规则进入 Step 2。

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

**独立 Agent 2 — 跨模型执行。** Step 2 完成后暂停, 产出一份审查材料。**标注: "[CROSS-MODEL] 以下是 Investigator 的 rules-verified.md + 代码。请独立判断: ①每个 FAIL 是真 bug 还是假阳性? ②抽样审查 PASS 条目——是否有 Investigator 漏掉的 bug?"** 开发者将此材料交给其他模型(GPT/DeepSeek等)执行审查。

**跨模型审查结果回来后**, AI 合并 Investigator + 跨模型 Debunker 的结果:

**审查范围: 全部。** 不只看 FAIL。PASS 抽样 30% + 全部 FAIL + 全部 UNCERTAIN。

|| Investigator 说 | Debunker 审查 | Debunker 判定 | 最终结论 |
||------|:--:|------|------|
|| FAIL | 全部 | "我找到绕过它的方法" | **CONFIRMED** — 真 bug |
|| FAIL | 全部 | "这里有运行时保护" | **OVERRULED** — 假阳性 |
|| FAIL | 全部 | "我无法判断" | **DISPUTED** — 你裁决 |
|| PASS | 30% 抽样 | "我找到藏着的 Bug" | **FAKE_PASS** — Investigator 漏了 |
|| PASS | 30% 抽样 | "确实没问题" | PASS |
|| UNCERTAIN | 全部 | 审查后重新判定 | UNCERTAIN 或 CONFIRMED |

**为什么必须这样**: Dashboard 项目的 `filter_brush` 死代码——Investigator 看到 `on_select` 就 PASS。Debunker 如果只查 FAIL 就永远看不到这类漏洞。
**参考**: bug-hunt Skeptic 全量审查 + Redhound Debunking Agent

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
|| 框架过重 | LLM 推理 + 规模阈值 | "实现当前 spec 范围所需的最小依赖是什么？代码引入的库是否超过了这个范围？"引用 spec 范围条款作证据 |
|| 不可测抽象 | mock 依赖分析 | 方法需要 >3 个 mock 才能测试 = FAIL |
|| 过度设计(旧) | AST 模式 | 嵌套 >3 / 参数 >5 / 单文件 >300 行 / 单方法类 |
|| 调用环 | call graph 遍历 | f1→f2→...→f1 形成回路 |

---

## Step 6: 修正

|| 结论 | 操作 | 谁做 |
||------|------|------|
|| **PASS** | 跳过 | — |
|| **CONFIRMED** | AI 提修正方案 → 修 → **重跑 Step 2-5 全部** (≤2次)。不可只重跑部分——修正可能引入新 bug 破坏金值或增加死代码 | **你决定**: 修 / 标记已知限制 / 回退 spec |
|| **FAKE_PASS** | 同 CONFIRMED——Investigator 漏了，这是真 bug | 同上 |
|| **DISPUTED** | Agent 1 和 Agent 2 的论点并列 | **你裁决** |
|| **OVERRULED** | 假阳性，记录 Debunker 证据 | 无需修正 |
|| **UNCERTAIN** | 直接给你 | **你判断** |

---

## 评分与门禁

```
总分 = 规则通过率×0.4 + 金值覆盖×0.3 + 健康检测×0.3

硬阻断 (Hard Gates):
  任一规则 CONFIRMED → 总分上限 50
  任一规则 FAKE_PASS → 总分上限 50
  任一金值偏差 >0.1% → 总分上限 50
  金值覆盖 = 0% → 总分上限 60

通过阈值: ≥70 PASS / 50-69 WARN / <50 FAIL
```

**为什么硬阻断**: 健康扫描 100 分不能掩盖业务逻辑全错。金值全挂的代码不应该得 30 分——它应该直接 FAIL。

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
