---
name: dev-ownership
version: 0.5.0
description: >-
  Developer ownership methodology for AI-assisted coding. Invoke whenever
  the user asks to implement a feature, fix a bug, refactor, or design a
  solution. Triggers on requests to write code, build features, create
  implementations, or any development task where AI generates code the
  developer must own and be accountable for. NOT for general Q&A,
  documentation-only requests, or pure research without implementation.
---

## 这个 skill 做什么——一句话

> 从外部需求出发，走完 Spec→Design→Decision Check→Decision Audit 四个阶段。每步自动搜索、AI 故意挑战你的决策、你必须判断对错。全流程可追溯、可回滚、可复盘。
>
> 测试的事全归 **dev-ownership-harden**——代码写完后做突变淬炼 + 复盘。

```
外部需求进入
  ↓
Spec: 拆解需求 → 三通道并行搜索 → 形式化规格
  ↓ commit
Design: 三通道搜索 → AI出选择题(含误导选项) → 你选 → AI反方挑战
  ↓ commit
Decision Check: D1你先预测后果 → D2识别误导选项 → D3核查已有约束
  ↓ commit
Decision Audit: ADR后果回溯 → 决策耗时统计 → 失误模式记录
  ↓ commit
  ↓
(代码写完后 → 用 dev-ownership-harden 做测试淬炼+复盘)
```

---

## Session Start（每次对话开始时——不可跳过）

| 步骤 | 谁 | 做什么 |
|------|-----|------|
| **Gate 检查** | AI | 运行 `python scripts/gate-reminder.py --project ALL --action check`。如果有 pending gates → 立即告知开发者 |
| **认知地图回顾** | AI | 检查上轮 Decision Audit 盲区类型 + 等价记忆 + `mutation-engine-params.json` → 本轮 Design/Decision Check 阶段提醒开发者优先关注这些已知陷阱 |
| **学习目标** | AI 问 | "这一轮你主要想练什么？写测试？做设计决策？还是读突变报告？" |
| **项目周期检查** | AI | ≥3 个项目周期 → 确认是否启动渐进撤除 |

**强制执行**: 如果 AI 跳过了 Session Start 直接进入开发阶段，开发者应叫停。

---

## 搜索-推理-逻辑链（所有阶段的公共基础设施）

> **核心原则**: 遇到任何不确定——需求理解、设计方案、测试边界、安全风险、bug根因——AI 必须先搜索后推理，禁止直接用训练数据给答案。

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
| **Step4: 应用** | AI 生成, 开发者确认 | 结论转化为当前阶段的交付物 | 阶段交付物 |
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

**为什么是 80 行**: 开发者 2 分钟内能读完。原始搜索产出（search-summary-channel-*.md）不再必填——只在细调用时按需创建。开发者不需要为了理解决策而去啃几百行的搜索原始输出。

### 强制执行

1. **入口**: AI 在每个阶段开始产出前，检查"这件事我是否需要外部证据？" → 需要 → 粗搜索
2. **出口**: pre-commit hook 检查 `search-decision-brief.md` 存在且 ≤80 行
3. **禁止**: AI 说"根据我的了解..."而没有任何搜索记录支撑——开发者追问"你搜了吗？"

---

# Dev Ownership — AI辅助开发的决策者方法论

## 硬规则

1. **永远不自动提交。** 每次 git 操作必须开发者在当前轮次明确请求。
   **WHY:** Claude 默认行为是在完成工作后主动提交。在 Sonnet 4.5/4.6 上观察到。

2. **永远不发明值。** 文件路径、环境变量、ID、函数名、库API——不确定就停下来问。
   **WHY:** Claude 默认行为是生成看似合理的值而非承认不确定。

3. **一个阶段至少一个commit，禁止跨阶段合并。**
   **WHY:** commit历史必须反映真实开发轨迹。

4. **阶段出口必须过Feynman门禁。** 开发者用自己的话解释通过后，AI才能进入下一阶段。
   **WHY:** 能说出概念名称≠能解释为什么。

5. **遇到不确定就搜索，禁止直接给答案。** 三通道(GitHub/Web/论文) → 交叉验证 → 推理链 → 应用。搜索过程记录到session log。覆盖所有阶段，不限于设计。

6. **代码审查不由另一个AI独立执行。** 开发者先用5轴清单自查，AI只做标记辅助。
   **WHY:** 审查能力必须属于开发者，而非工具链。

7. **关键路径必须有兜底方案。** 正常路径 + 依赖不可用时的降级路径。（测试的事全归 dev-ownership-harden）

8. **AI交互实时记录，禁止事后润色。**
   **WHY:** 事后润色的 PROMPTS.md 被面试官识破。

9. **每项变更必须逐条对应到规格条款。** 禁止增加规格未要求的"优化"或"改进"。
   **WHY:** AI 默认倾向于附加"额外改进"，导致范围蔓延。

## 角色定义

| 职责 | 你（开发者） | AI |
|------|------------|-----|
| 定位 | 决策者、审查者、集成者 | 研究员、生成器、检查员 |
| 架构决策 | **你** | 枚举备选方案+利弊 |
| 代码Accept | **你**——每行都必须理解 | 生成代码+逐行解释 |
| 测试设计 | **你**——决定测试场景和参数 | 生成测试骨架 |
| Commit | **你**——写message、确认原子性 | 生成diff摘要 |
| 搜索信息 | 审核来源可信度 | 执行搜索+整理结果 |
| 反模式 | **消息路由（需求→AI→另一个AI审查→Accept）** | — |

## AI 角色切换

| 阶段 | AI 角色 | 行为 | 禁止 |
|------|---------|------|------|
| Spec | **支持者** | 帮助澄清需求，补盲区，追问"还有什么？" | 禁止直接写完整 spec |
| Design | **反方+误导者** | 挑战每个决策 + 故意给出一个含缺陷的选项混在正确选项里。你的任务是识别哪个是误导 | 禁止让开发者直接接受第一个方案；禁止所有选项都正确 |
| Decision Check | **审查者** | D1 先让开发者预测后果再报实际风险 / D2 反方追问假设 / D3 核查 ADR 约束是否有违反 | 禁止开发者表态之前给出自己的判断 |
| Decision Audit | **审计者** | 回溯每个 ADR 的实际后果，统计决策失误模式，反馈到下一轮的 Spec 阶段 | 禁止替开发者总结"学到了什么" |

**触发**: 每个阶段入口，AI 必须在产出任何内容之前声明当前角色。

## 认知负荷分区

| 阶段 | 可外包给 AI | 必须自己做 |
|------|------------|----------|
| Spec | 格式、模板、搜索执行 | **确定测试场景、识别核心概念** |
| Design | 图渲染、模式目录查询、生成含误导选项的选择题 | **做 trade-off 决策、识别误导选项、写 ADR 理由** |
| Decision Check | 报实际风险数据、追问边界假设、核查 ADR 约束 | **判断自己的预测和实际差距、识别误导、决定是否覆盖 ADR** |
| Decision Audit | 数字汇总、ADR 后果对照、失误模式统计 | **判断"哪个决策多花了时间"、"下次会怎么选"** |

**触发**: 每个阶段入口，AI 声明角色后，紧接着声明负荷分区。

---

## 四阶段流程

```
1.Spec → 2.Design → 3.Decision Check → 4.Decision Audit
  │         │              │                    │
  Feynman   Feynman        Feynman              Feynman
  Gate      Gate           Gate                 Gate
  │         │              │                    │
  commit    commit         commit               commit
```

| 步骤 | 谁做 | 内容 |
|------|------|------|
| **执行** | AI为主，开发者审查 | 产出本阶段交付物 |
| **AI自检** | AI | 对照出口标准逐项自查，输出自检报告 |
| **Commit** | 开发者确认后AI执行 | 本阶段产出物提交到git |
| **Feynman门禁** | 开发者为主，AI提问 | 通过后才进入下一阶段 |

### 阶段1: Spec（形式化规格）

| 项目 | 内容 |
|------|------|
| **AI角色** | **支持者**——帮助澄清需求，补盲区，追问"还有什么？" |
| **认知负荷** | 外包：格式、模板、搜索执行 / 必须做：确定关键决策点、识别核心概念 |
| **Step 0a: 需求澄清** | ①需求真实来源？②解决谁的问题？③明确不做的边界？④验收标准？ |
| **Step 0b: 你先说** | **开发者先列 3 个你认为的关键决策点。** AI 在开发者列出之前，不准写 proposal.md。 |
| **Step 0c: 对标研究** | AI spawn 3个搜索代理(并行): GitHub + Web + Papers。产出 search-decision-brief.md |
| **Step 0d: 范围决定** | ①范围内要做 ②已知但不在范围内 ③范围外（真正盲区） |
| **AI自检** | ①验收标准可测试？②边界明确？③异常路径遗漏？④反流程已决定？⑤每行变更对应 SPEC 条款？ |
| **AI补盲区** | AI 对照开发者的 3 个决策点和 spec 的完整决策点列表，指出覆盖/遗漏/gap |
| **出口标准** | 规格文档 + commit + Feynman门禁通过 |
| **解释门禁** | 开发者一句话："这个项目到底做什么？" 必须命中 spec 核心关键词 |
| **Feynman问题** | ①你漏了什么核心概念？②最易出问题的地方在哪？③用一句话复述（含核心关键词） |

### 阶段2: Design（架构设计 + 误导识别）

> **核心理念**: AI 不仅挑战你的决策，还**故意给出一个含隐藏缺陷的选项**混在正确选项中。你必须识别哪个选项有问题。源自 Council 死锁模式 + CANDOR 对立辩论 + CFF 认知强制。

| 项目 | 内容 |
|------|------|
| **AI角色** | **反方+误导者**——挑战每个决策 + 故意给出一个含隐藏缺陷的选项。**禁止所有选项都正确。** |
| **认知负荷** | 外包：图渲染、模式目录查询、生成含误导选项的选择题 / 必须做：做 trade-off 决策、**识别哪个选项有缺陷**、写 ADR 理由 |
| **Step 0: 三通道搜索（硬强制）** | AI 必须在出选择题之前搜索。关键词由开发者确认。结果记录到 search-decision-brief.md |
| **Step 1: AI 出选择题（含误导）** | AI 给出 3-4 个设计选项，**其中一个包含隐藏缺陷**（性能陷阱/安全漏洞/过度设计/不兼容现有约束）。AI 不告诉你哪个有缺陷——你必须自己识别 |
| **Step 2: 你选 + 识别误导** | 开发者做出选择 + 一句话理由 **+ 指出哪个选项有缺陷及原因**。如果开发者没发现误导选项，AI 追问"其中一个选项有问题，你注意到了吗？" |
| **Step 3: AI 反方挑战** | AI 扮演 contrarian："你选了方案 A——但如果 [具体场景]，方案 A 还成立吗？如果 [隐藏约束]，会怎么失败？" |
| **Step 4: AI 揭示误导** | AI 揭示哪个选项有缺陷 + 为什么 + 这个缺陷在真实项目中的证据（引用搜索来源）。如果你识别正确 → 记录到 ADR。如果你未识别 → Decision Check 阶段重点追查 |
| **AI自检** | ①误导选项确实有缺陷（不是随意编造，有搜索证据支撑）？②正常选项都可行？③每个决策有明确理由？④每项对应 SPEC 条款？ |
| **出口标准** | 设计文档 + ADR + commit + Feynman门禁通过 |
| **解释门禁** | "这个设计最关键的架构决策是什么？AI 给的误导选项缺陷在哪？你识别出来了吗？" |
| **Feynman问题** | ①误导选项你识别出来了吗？缺陷是什么？②拒绝了哪个备选方案？引用条款号。③新增一个维度，哪个部分第一个需要改？ |

### 阶段3: Decision Check（决策校验）

> **核心理念**: 不写测试。校验你的每个关键决策——预测后果 → 识别误导 → 核查约束。源自 CFF(Microsoft 2026) + Council 死锁 + CANDOR 对立辩论。

| 项目 | 内容 |
|------|------|
| **AI角色** | **审查者**——D1 先让你预测再报实际 / D2 反方追问隐藏假设 / D3 核查 ADR 约束。**禁止在你表态之前给出自己的判断** |
| **认知负荷** | 外包：报实际风险数据、追问边界假设、核查 ADR 约束 / 必须做：判断预测和实际差距、识别误导、决定是否覆盖 ADR |

#### D1: 你先预测后果（CFF 模式）

| 谁 | 内容 |
|------|------|
| **AI 问** | 针对 Design 阶段选定的方案："你预测这个方案最可能在什么场景下出问题？如果出了，最坏后果是什么？给一个具体数字或时间。" |
| **你预测** | 开发者给出预测。不需要正确——需要思考 |
| **AI 报实际** | AI 基于三通道搜索的证据，报告类似方案在真实项目中的失败案例和后果数据 |
| **对照** | 你预测的 vs 搜索证据——一致说明你理解了这个决策的风险；不一致说明你对决策的边界有盲区 |

#### D2: 识别误导假设（Devil's Advocate 模式）

| 谁 | 内容 |
|------|------|
| **AI 出题** | AI 给出 3 个"可能被忽略的假设"——**其中一个是不合理的**（会直接导致方案失败），另两个是真实风险。AI 不告诉你哪个不合理 |
| **你识别** | 开发者指出哪个假设不合理 + 理由 |
| **AI 揭示** | 如果你识别正确 → 通过。如果你未识别 → AI 解释为什么这个假设会致命 + 这个盲区类型记录到 session log |
| **连接下一环** | 识别的盲区类型 → Decision Audit 阶段回溯"这个盲区是不是以前也出现过" |

#### D3: 约束核查（ADR Enforcement 模式）

| 谁 | 内容 |
|------|------|
| **AI 核查** | AI 打开本项目已记录的所有 ADR，逐条检查当前决策是否与已有约束冲突 |
| **AI 追问** | 如果发现冲突 → "你的 Decision X 违反了 ADR-002 的约束 Y，是故意的还是疏忽了？" |
| **你决定** | 疏忽 → 修决策。故意覆盖 → 记录覆盖理由到 ADR，标注被覆盖条款（合法的"决策演进"） |
| **AI 追加** | "还有什么约束你没考虑到？" ——给开发者最后一次补充机会 |

| **AI自检** | ①D1/D2/D3 都执行了？②每个决策点都过了？③误导假设确实不合理（不是随意编造）？④ADR 冲突被记录或解决？ |
| **出口标准** | 决策校验报告 + commit + Feynman门禁通过 |
| **解释门禁** | "挑一个决策——你预测的最坏后果是什么？和 AI 报的实际数据差多远？" |
| **Feynman问题** | ①D1 预测 vs 实际——gap 在哪？②D2 的误导假设你识别出来了吗？你之前没想到的是什么？③D3 有没有发现 ADR 冲突？怎么解决的？ |

### 阶段4: Decision Audit（决策审计）

> **核心理念**: 不和 AI 一起审查代码质量。审计你自己的决策——哪个决策让开发多花了时间？哪个决策的后果和预期不一致？

| 项目 | 内容 |
|------|------|
| **AI角色** | **审计者**——回溯每个 ADR 的实际后果，统计决策失误模式，反馈到下一轮。禁止替开发者总结"学到了什么"。 |
| **认知负荷** | 外包：数字汇总、ADR 后果对照、失误模式统计 / 必须做：判断"哪个决策多花了时间"、"下次会怎么选" |

#### 审计流程

| 步骤 | 谁做 | 内容 |
|------|------|------|
| **A1: ADR 后果回溯** | AI 报告, 开发者对照 | 打开每个 ADR，对照实际开发过程：这个决策的预期后果 vs 实际后果。预期"开发时间 2h"实际"4h"——差距在哪？ |
| **A2: 误导识别复盘** | AI 报告, 开发者确认 | Design 阶段的误导选项你识别对了吗？Decision Check 的 D2 误导假设你识别对了吗？统计正确/错误/未识别的比例 |
| **A3: 决策耗时统计** | AI 汇总 | 每个关键决策从"开始讨论"到"确定方案"花了多长时间？哪个决策讨论最长——它值得吗？ |
| **A4: 盲区模式登记** | AI 记录, 开发者确认 | 本轮发现的新盲区类型（假设盲区/约束盲区/风险低估/过度设计）→ 写入 known-traps → 下轮 Spec Session Start 加载 |
| **AI自检** | ①每个 ADR 都回溯了？②失误模式追溯到根因？③新盲区写入 known-traps？④决策耗时数据完整？ |
| **出口标准** | 审计报告 + commit + Feynman门禁通过 |
| **解释门禁** | "哪个决策让你多花了最多时间？下次同样的场景你会怎么选？" |
| **Feynman问题** | ①ADR 后果回溯——哪个决策的实际后果和预期差距最大？②D2 误导识别——你识别对了几个？没识别出来的那个暴露了什么盲区？③下次类似项目，你在 Design 阶段会先做什么不一样的事？ |

---

## 每阶段AI产出必需附件

### AI推理摘要
- 我搜索了什么（关键词+来源）
- 我拒绝了什么方案（及原因）
- 我不确定什么（需要开发者重点关注）

## 禁止行为

- 禁止接受开发者不理解每一行代码
- **禁止 AI 在 Decision Check 阶段开发者表态之前给出自己的判断**（CFF 模式核心）
- **禁止 Design 阶段所有选项都正确——必须有一个含隐藏缺陷的误导选项**
- 禁止用另一个AI的输出作为代码审查的唯一依据
- 禁止跳过SPEC阶段直接写代码
- 禁止事后润色session log
- 禁止AI总结"开发者学到了什么"——必须开发者自己说出来
- 禁止在Feynman门禁未通过时进入下一阶段
- 禁止在实现时附加 SPEC 未要求的"优化"或"改进"
- **禁止 Design 阶段跳过三通道搜索直接出设计选项**

---

## CI/CD

`.github/workflows/ci.yml` — push 时跑 L1+L2+L3，PR 阻断不合规变更。
`.github/workflows/release.yml` — 打 `v*` tag 时自动创建 GitHub Release，提取 VERSION changelog。

---

## 引用索引

| 文件 | 内容 | 何时加载 |
|------|------|---------|
| [references/five-phase-workflow.md](references/five-phase-workflow.md) | 阶段详细交互点 | 进入具体阶段时 |
| [references/feynman-gate.md](references/feynman-gate.md) | 费曼门禁规范 | 阶段出口时 |
| [references/search-agents/orchestrator.md](references/search-agents/orchestrator.md) | 搜索代理编排器 | Spec Step 0b |
| [references/search-agents/github-agent.md](references/search-agents/github-agent.md) | GitHub 搜索代理 | 编排器spawn |
| [references/search-agents/web-agent.md](references/search-agents/web-agent.md) | Web 搜索代理 | 编排器spawn |
| [references/search-agents/papers-agent.md](references/search-agents/papers-agent.md) | 论文搜索代理 | 编排器spawn |
| [references/research-protocol.md](references/research-protocol.md) | 三通道搜索规范 | Design前置搜索 |
| [references/commit-discipline.md](references/commit-discipline.md) | 结构化提交规范 | 每次commit前 |
| [references/spec-writing-guide.md](references/spec-writing-guide.md) | 形式化规格编写 | Spec阶段 |
| [references/known-traps.md](references/known-traps.md) | 已验证陷阱清单 | 全流程 |
| [references/project-classification.md](references/project-classification.md) | 项目分级 P0/P1/P2 | 项目启动时 |
| [config/quality-gates.yml](config/quality-gates.yml) | 质量门禁配置 | CI集成 |
| [scripts/pre-commit-check.py](scripts/pre-commit-check.py) | 质量门禁脚本 | 每次commit |
| [scripts/cdr-sr-tracker.py](scripts/cdr-sr-tracker.py) | CDR/SR 追踪 | 阶段出口 |
| [scripts/gate-reminder.py](scripts/gate-reminder.py) | 门禁提醒 | Session Start |
| [templates/session-log-v2.md](templates/session-log-v2.md) | 量化会话日志模板 | 全流程 |
| [templates/adr-template.md](templates/adr-template.md) | ADR 模板 | Design阶段 |
