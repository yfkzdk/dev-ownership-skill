---
name: dev-ownership-harden
version: 0.5.0
description: >-
  Test hardening and retrospect for the dev-ownership methodology. Invoke AFTER
  code is written and Decision Audit phase is complete. Runs mutation testing to find
  test blind spots, then iteratively hardens tests until quality gates pass.
  Ends with a retrospect audit tracing every line of code back to spec clauses.
  Triggers on: "run mutation testing", "harden tests", "verify quality",
  "retrospect", "audit code", "淬炼", "复盘", "突变测试".
  NOT for: writing new features, fixing bugs, or general development.
---

## 这个 skill 做什么——一句话

> 代码写完了——测试真的够硬吗？从全量突变出发，找到测试盲区，迭代补测试直到达标，最后做全项目复盘审计。

**前置条件**: 必须先通过 **dev-ownership** 的 Spec→Design→Decision Check→Decision Audit 四个阶段，代码已合并或准备合并。

```
dev-ownership 开发完成
  ↓
Harden: 全量突变 → 分类(等价/可疑/真缺口) → 按优先级补测试 → 再跑 → 循环达标
  ↓ commit(s)
Retrospect: 自评 → AI报实际 → 学到什么 → 可追溯性审计 → 失误记录 → 技能自检
  ↓ commit
```

---

## Session Start（每次对话开始时——不可跳过）

| 步骤 | 谁 | 做什么 |
|------|-----|------|
| **Gate 检查** | AI | 检查 Decision Audit 阶段是否已通过 Feynman 门禁。未通过 → 回到 dev-ownership |
| **认知地图加载** | AI | 加载 `~/.claude/mutation-engine-params.json`——等价阈值、热点盲区、热点算子 |
| **学习目标** | AI 问 | "这一轮淬炼你主要想练什么？读突变报告？补边界测试？还是判断等价？" |

---

## 搜索-推理-逻辑链（所有阶段的公共基础设施）

> **核心原则**: 遇到任何不确定——突变存活原因、等价判断、测试策略、性能瓶颈——AI 必须先搜索后推理，禁止直接用训练数据给答案。

### 两级搜索模型

```
粗调用（每次自动）
  → 3 通道并行搜索，每个通道只返回 ≤10 行摘要 + 可点击链接
  → 交叉验证，控制在 20 行内
  → 合并为 search-decision-brief.md (硬上限 80 行)

细调用（按需触发）
  → 只在需要具体代码、精确数字、论文方法细节时才加载原文
  → 渠道: WebFetch 打开链接 / Agent 读 repo 源码 / 论文原文
```

### 四步循环

| 步骤 | 谁做 | 内容 | 产出物 |
|------|------|------|--------|
| **Step1: 粗搜索** | AI spawn 3 Agent 并行 | 每个 Agent 返回 ≤10 行摘要：①最佳结果(1-2句话) ②链接(3-5个) ③是否有矛盾发现 | 内存，不落盘 |
| **Step2: 交叉验证** | AI 合并比对 | 控制在 20 行内：共识(consensus)、矛盾(contradiction)、空白(gap) | 写入 brief |
| **Step3: 推理链** | AI 输出, 开发者审查 | 搜索到了什么 → 排除了什么 → 为什么选这个方案 → 还有哪里不确定 | 写入 brief |
| **Step4: 应用** | AI 生成, 开发者确认 | 结论转化为补测试方案/突变等价判断/known-trap条目/引擎参数调整 | 阶段交付物 |
| **细调用（按需）** | AI 按需执行 | 需要代码片段/精确数字/方法论细节时，用 WebFetch 或 Agent 深入特定链接或 repo。结果 ≤30 行追加到 brief | `search-deep-dive-*.md`（有才创建） |

### 唯一产出文件: `search-decision-brief.md`（≤80 行硬限制）

```
结构 (固定 5 段):
1. 三通道摘要 (≤30 行) — 每个通道 3-5 句 + 链接
2. 交叉验证 (≤15 行) — 共识 / 矛盾 / 空白
3. 改变的决策 (≤15 行) — 搜索前我倾向___，搜索后我选择___，因为___
4. 不确定 (≤10 行) — 还没搞清楚的事
5. 细调用记录 (≤10 行) — 如果触发了细调用，记录链接和关键发现
```

### 淬炼阶段特有触发条件

AI 在以下情况**必须启动搜索-推理-逻辑链**：

- 突变存活但等价分类不确定 → 搜索该突变模式的已知等价案例
- 补的测试杀不死目标突变 → 搜索"why mutation survives [pattern]"
- 安全扫描告警的真伪无法判断 → 搜索该告警的CVE/真实危害/常见误报
- 循环 2 次后检出率仍不达标 → 搜索"mutation testing stuck"原因
- Retrospect 发现新类型的盲区 → 搜索业界对该盲区类型的已知解决方案
- 元循环参数调优 → 搜索最新的突变测试研究校准阈值

### 强制执行

1. **入口**: AI 在每个阶段开始产出前，检查"这件事我是否需要外部证据？" → 需要 → 粗搜索
2. **出口**: pre-commit hook 检查 `search-decision-brief.md` 存在且 ≤80 行
3. **去噪**: 三通道结果存在技术冲突时，禁止调和包装。必须用 `[渠道A结论] VS [渠道B结论]` 对立格式，开发者裁决
4. **禁止**: AI 说"据我所知..."而没有任何搜索记录——开发者追问"你搜了吗？"
5. **共享基础设施**: 与 dev-ownership 共用同一套搜索代理

---

## 硬规则（继承自 dev-ownership + 淬炼特有）

1. **永远不自动提交。** 每次 git 操作必须开发者在当前轮次明确请求。
2. **永远不发明值。** 文件路径、环境变量、ID、函数名——不确定就停下来问。
3. **遇到不确定就搜索，禁止直接给答案。** 三通道(GitHub/Web/论文) → 交叉验证 → 推理链 → 应用。覆盖 Harden 和 Retrospect 两个阶段。
4. **一个阶段至少一个commit。**
5. **阶段出口必须过Feynman门禁。**
6. **AI 不替开发者写测试断言。** 引擎不知道 "0.045" 才是正确值——断言必须开发者确认。
7. **Harden 最多循环 3 次。** 超过 → 表征测试锁死当前行为 → 标记 `TD-[日期]` 技术债 → 允许流程推进。该技术债条目在下轮 Session Start 加载。
8. **Retrospect 的"学到了什么"必须开发者自己写。** AI 不准替。

## 角色定义（淬炼阶段）

| 职责 | 你（开发者） | AI |
|------|------------|-----|
| 判断等价 | **你**——决定存活突变是真缺口还是等价 | 自动分类+提供依据 |
| 补测试 | **你**——决定补什么、写断言 | 生成测试骨架+提示盲区类型 |
| 复盘总结 | **你**——判断学到了什么 | 报数字+对照自评+追问 |

---

## 阶段5: Harden（测试淬炼）

> **证据**: Stay Green Workflow 将突变测试作为 Gate 3；Google 在 24,000+ 开发者中验证了 diff-scoped 增量突变；PicPay 通过突变驱动的迭代将覆盖率从 54%→80%。

| 项目 | 内容 |
|------|------|
| **入口条件** | Review阶段通过，代码已合并或准备合并 |
| **AI角色** | **测量者+教练**——跑全量突变→报告盲区→**搜索修复方案→生成测试骨架→让你确认断言**→循环直到达标。不替开发者写断言，但必须基于搜索证据生成骨架。 |
| **认知负荷** | 外包：跑突变、分类等价、生成建议 / 必须做：判断哪些缺口值得补、补什么测试、写断言 |

### Step 0.5: 静态检查（强制）
**在跑突变之前**先过 lint + type check。代码有低级语法/类型错误时突变结果全是噪音。
- `ruff check .` → 0 errors
- `mypy .` → 0 errors
- 不通过 → 修，不浪费突变引擎时间
- 通过 → 进入 Step 1

### Step 1: 全量突变
引擎跑全量突变（`--mode f`），不抽样。报告所有存活突变及其位置、类型、等价分类。
**时间预算**: P0 ≤ 30min, P1 ≤ 15min, P2 ≤ 5min。

### Step 2: 优先级排序
按以下顺序排列存活突变：
1. 核心业务逻辑（计费/权限/汇率）
2. 高复杂度函数
3. API 入口点
4. 其他

只显示前 7 个——Stuttgart 研究证明开发者只会修 ~30% 的伪测试方法。
**搜索触发**: 等价分类不确定时 → 搜索 GitHub 上同类突变的处理方式（是补测试还是标记等价）。

### Step 3: 搜索→生成→确认→验证（强制闭环）

每个存活突变走完整四步，不可跳过：

|| 子步骤 | 谁做 | 内容 |
||------|------|------|
|| **3a: 搜索** | AI 强制 | 三通道搜索该突变类型的已知修复方案。必须产出搜索证据（≤10行摘要+链接），禁止凭训练数据直接给答案 |
|| **3b: 推理** | AI 输出 | 基于搜索证据 → 推断需要什么测试参数、边界值、断言。写入推理链："搜到了X→排除了Y→选择Z→不确定什么" |
|| **3c: 生成** | AI 生成 | 用搜索到的模式生成具体测试骨架（含参数值、边界值）。断言必须开发者确认——引擎不知道"0.045"才是正确值 |
|| **3d: 验证** | AI 跑, 开发者审 | 增量突变确认新测试杀死了目标突变，且没有引入新盲区 |

**强制执行**: 如果 AI 跳过搜索直接生成测试骨架 → 开发者追问"搜索证据在哪？"

### Step 4: 再跑验证
只对修改过的文件重跑突变（增量模式）。验证新测试杀死了目标突变，且没有引入新盲区。

### Step 5: 循环判定
检出率 ≥ 阈值 → 通过。否则回到 Step 3。
**阈值**: P0 ≥ 85%, P1 ≥ 70%, P2 ≥ 50%。
**最多循环 3 次**——超过则触发降级通道：
1. 对未杀死的突变运行表征测试（固定当前行为）
2. 标记为 `TD-[日期]` 写入 known-traps
3. 流程正常推进到 Retrospect，标注"X 突变降级为技术债"

### Step 6: 反馈归档
本轮淬炼的缺口类型写入 `~/.claude/mutation-equivalence-memory.json`，供下一个项目使用。

### AI自检
①全量突变覆盖所有源文件？②等价分类准确率合理？③循环次数≤3？④新缺口类型应记录？

### 出口标准
检出率达标（或循环 3 次后接受） + commit(s) + 反馈归档

### 解释门禁
开发者一句话："本轮淬炼补的最重要的一个测试是什么？它保护了什么之前没被保护的东西？"

### Feynman问题
①本轮补了哪些测试？最重要的保护了什么盲区？②循环了几次？第一次补的测试为什么不够？③发现的盲区类型——下一个项目在 Design 阶段你会先考虑哪种盲区？

---

## 阶段6: Retrospect（项目审视）

| 项目 | 内容 |
|------|------|
| **入口条件** | Harden阶段通过（或跳过），所有代码已合并 |
| **AI角色** | **支持者**——综合学习成果，确认成长。禁止替开发者总结"学到了什么"。 |
| **认知负荷** | 外包：数字汇总、known-traps 对照 / 必须做：判断"学到了什么"、决定下次策略 |

### Step 0: 你先自评（元认知矫正）
**在 AI 报任何数字之前**，开发者先自评：
①"你觉得你理解了这个项目的百分之多少？"
②"核心概念你能用自己的话讲清楚几个？"

### Step 1: AI 报实际 + 对照
AI 报数字（测试数/覆盖率/突变评分/CDR/Feynman 门禁数）+ 对照开发者的自评。

### Step 2: 你学到了什么
开发者写两句话：
①这个项目你学到的一个新概念是什么？
②下一个项目你会先做什么不一样的事？
**AI 不准替开发者写。**

### Step 3: 可追溯性审计
正向 SPEC→CODE 矩阵 + 反向 CODE→SPEC 矩阵 + 合规评分（详见 traceability-audit.md）

### Step 4: 失误记录 + known-traps复查
AI 打开上次项目的 known-traps.md，逐条检查当前项目是否复发。
**搜索触发**: 发现新类型陷阱 → 搜索该陷阱在业界的名称/标准解决方案，补充到 known-traps 时附上外部引用。

### Step 5: AI辅助降级检查
≥3 个项目周期 → AI 主动降低下一轮辅助程度："下一轮我会少给直接答案，多问苏格拉底式问题。"

### Step 6: Start/Stop/Continue + 新陷阱候选

### Step 7: 技能自检（元循环）
AI 分析本轮 Harden 阶段引擎表现，自动调优参数写入 `~/.claude/mutation-engine-params.json`：
- **等价误判率** >20% → 降低等价阈值 (-0.02)；全等价无真缺口 → 提高阈值 (+0.02)
- **算子存活率** → 记录"热点算子"，下一轮优先补对应测试
- **盲区模式** → 最高频模式写入"热点盲区"，下一轮 Design 主动建议
- **循环效率** >2 轮 → 建议下一轮 Review 跑更大样本

### AI自检
①审计逐类遍历？②失误追溯到根因？③新陷阱应加入 known-traps？④自评vs实际 gap 已记录？⑤技能自检 4 项都检查了？

### 出口标准
审视报告完成 + commit + Feynman门禁通过

### 解释门禁
开发者一句话："这个项目你学到的一个新概念是什么？"

### Feynman问题
①自评理解程度 vs 实际突变存活——gap 在哪？②最大失误是什么？引用文件:行号和根因。③下次类似项目，Spec 阶段会先做什么不一样的事？

---

## 元循环：技能自优化

每个项目结束后，引擎从本轮淬炼中学习，自动调优参数供下一轮使用。

```
项目 A Retrospect → 技能自检 → 调优参数
  ↓
项目 B Session Start → 加载优化参数 → 等价阈值更准、热点盲区预警
  ↓
项目 B Harden → 引擎表现更好 → Retrospect → 再次调优 → ...
```

| 参数 | 调整逻辑 | 初始值 | 调整幅度 |
|------|---------|--------|---------|
| `equiv_threshold` | 等价误判率>20% → -0.02；全等价无真缺口 → +0.02 | 0.98 | ±0.02/轮 |
| `hot_operators` | 哪种算子存活率最高 → 记录为热点 | — | 每轮更新 |
| `hot_gap_patterns` | 哪种盲区类型占比最高 → 记录为热点 | — | 每轮更新 |
| `avg_harden_cycles` | 平均几次淬炼达标 → 指导 Review 抽样量 | — | 移动平均 |

---

## 禁止行为

- 禁止 AI 替开发者写测试断言
- 禁止 AI 替开发者总结"学到了什么"
- **禁止 AI 不搜索直接给答案**——遇到不确定必须先走搜索-推理-逻辑链
- 禁止 Harden 循环超过 3 次不记录 known-traps
- 禁止跳过自评直接报数字（Retrospect Step 0）
- 禁止在 Feynman 门禁未通过时结束阶段
- 禁止跳过全量突变直接用增量模式

---

## 引用索引

| 文件 | 内容 | 何时加载 |
|------|------|---------|
| [../references/traceability-audit.md](../references/traceability-audit.md) | 可追溯性审计规范 | Retrospect Step 3 |
| [../references/mutation-testing-guide.md](../references/mutation-testing-guide.md) | 突变测试配置指南 | Harden 阶段 |
| [../references/mutation-fix-guide.md](../references/mutation-fix-guide.md) | 突变修复指南 | Harden Step 3 |
| [../references/known-traps.md](../references/known-traps.md) | 已验证陷阱清单 | Retrospect Step 4 |
| [../references/measurement-pyramid.md](../references/measurement-pyramid.md) | 个人测量金字塔 | 全流程度量 |
| [../references/project-classification.md](../references/project-classification.md) | 项目分级 P0/P1/P2 | 入口判定 |
| [../references/feynman-gate.md](../references/feynman-gate.md) | 费曼门禁规范 | 阶段出口 |
| [../references/characterization-test-protocol.md](../references/characterization-test-protocol.md) | 表征测试协议 | Harden出口 |
| [../scripts/mutation-engine.py](../scripts/mutation-engine.py) | 突变测试引擎 | Harden Step 1+4 |
| [../scripts/dev-ownership.py](../scripts/dev-ownership.py) | 中央编排器 | 全流程 |
| [../templates/retrospect-template.md](../templates/retrospect-template.md) | 项目审视模板 | Retrospect |
