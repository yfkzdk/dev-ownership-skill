---
name: dev-ownership
version: 0.1.0-draft
description: >-
  Developer ownership methodology for AI-assisted coding. Invoke whenever
  the user asks to implement a feature, fix a bug, refactor, or design a
  solution. Triggers on requests to write code, build features, create
  implementations, or any development task where AI generates code the
  developer must own and be accountable for. NOT for general Q&A,
  documentation-only requests, or pure research without implementation.
---

## 这个 skill 做什么——一句话

> 从外部需求出发，走完 Spec→Design→TDD→Review→Retrospect 五个阶段，每一步自动检测、自动搜索、自动修复——检测不到的问题推到人工层。全流程可追溯、可回滚、可复盘。

**完整闭环**:

```
外部需求进入
  ↓
Spec: 拆解需求 → 三通道并行搜索(GitHub/Web/论文) → 推理可行性 → 写形式化规格
  ↓ commit (带 spec 条款引用)
Design: 对标搜索结果 → 架构决策(ADR) → 模块分解
  ↓ commit
TDD: RED(先写失败测试) → GREEN(最小实现) → REFACTOR(重构)
  ↓ commit (test→feat→refactor 三拆)
Review: 自动测量(CDR/覆盖率/突变/Lint/安全) → AI 审查 → 发现问题
  ↓
  ├── 能自动修 → AI 搜索(GitHub/Web/论文) → 推理 → 直接改代码
  └── 修不了 → 标记 Layer 2 → 开发者处理
  ↓ commit
Retrospect: 追溯审计(spec↔code 双向矩阵) → 失误记录 → 陷阱更新 → 归档
  ↓ commit

全程自动化:
  每次 commit: CDR/覆盖率/Lint/Type/安全 → hook 强制执行
  每个阶段出口: Feynman 门禁(理解验证) → 不过不进入下一阶段
  每次检测到问题: 搜索→推理→解决→验证
  每次修改: 可追溯到对应 spec 条款

遇到未覆盖的边界 → 三层修复体系:
  Layer 0: 自动化检测
  Layer 1: AI 诊断 + 自动修复
  Layer 2: 开发者处理
```

# Dev Ownership - AI辅助开发的决策者方法论

## 硬规则

以下规则适用于所有阶段。违反任何一条都必须暂停并修正。

1. **永远不自动提交。** 每次 git 操作必须开发者在当前轮次明确请求。
   **WHY:** Claude 默认行为是在完成工作后主动提交，而非等待开发者确认。在 Sonnet 4.5/4.6 上观察到。
   **Retire when:** 默认模型在冷启动后连续3次在执行 git 操作前主动请求确认。

2. **永远不发明值。** 文件路径、环境变量、ID、函数名、库API——不确定就停下来问。
   **WHY:** Claude 默认行为是生成看似合理的值（路径/变量名/API名）而非承认不确定。在 Sonnet 4.5/4.6 上观察到。
   **Retire when:** 默认模型在冷启动后连续3次对模糊标识符主动提问澄清。

3. **一个阶段至少一个commit，禁止跨阶段合并。** 禁止事后整理commit历史。
   **WHY:** 面试诊断书 §1.2 + §3.8 — 压缩后的commit丢失了决策时序，面试官一眼能识别。commit历史必须反映真实开发轨迹。

4. **阶段出口必须过Feynman门禁。** 开发者用自己的话解释通过后，AI才能进入下一阶段。
   **WHY:** 面试诊断书 §1.1 + §1.6 — 能说出概念名称≠能解释为什么。门禁强制"教给别人听"以暴露理解盲区。

5. **设计方案前必须搜索。** 至少3个信息源（GitHub/文档/行业标准），搜索过程记录到session log。
   **WHY:** Claude 默认行为是用内部知识直接设计方案，不验证已有方案。在 Sonnet 4.5/4.6 上观察到。
   **Retire when:** 默认模型在冷启动后连续3次在提出方案前主动执行外部搜索。

6. **代码审查不由另一个AI独立执行。** 开发者先用5轴清单自查，AI只做标记辅助。
   **WHY:** 面试诊断书 §2.4 + §3.6 — 审查能力必须属于开发者，而非工具链。AI审查结果仅作对照参考。

7. **测试必须具备双路径。** 正确路径 + API不可用时的本地fixture兜底路径。
   **WHY:** 防止测试依赖外部API可用性，确保离线环境也能完整运行。

8. **AI交互实时记录，禁止事后润色。** 开发者原始输入原文照录，不允许AI改写。
   **WHY:** 面试诊断书 §1.4 — 事后润色的PROMPTS.md被面试官识破。session log是开发过程的原始快照，不是交付物。

9. **每项设计/优化变更必须逐条对应到规格条款。** 禁止增加规格未要求的"优化"或"改进"。
   **WHY:** AI 默认倾向于在实现时附加"额外改进"，导致范围蔓延和非必要的复杂度。每行变更必须在 SPEC 中有明确依据。

## 角色定义

| 职责 | 你（开发者） | AI |
|------|------------|-----|
| 定位 | 决策者、审查者、集成者 | 研究员、生成器、检查员 |
| 架构决策 | **你** | 枚举备选方案+利弊，供你选择 |
| 代码Accept | **你**——每行都必须理解 | 生成代码+逐行解释 |
| 测试设计 | **你**——决定测试场景和参数 | 生成测试骨架 |
| Commit | **你**——写message、确认原子性 | 生成diff摘要 |
| 搜索信息 | 审核来源可信度 | 执行搜索+整理结果 |
| 反模式 | **消息路由（需求→AI→另一个AI审查→Accept）** | — |

## 五阶段流程

```
1.Spec → 2.Design → 3.TDD → 4.Review → 5.Retrospect
  │         │         │         │           │
  Feynman   Feynman   Feynman   Feynman    Feynman
  Gate      Gate      Gate      Gate       Gate
  │         │         │         │           │
  commit    commit    commit    commit     commit
```

每个阶段包含四个步骤：

| 步骤 | 谁做 | 内容 |
|------|------|------|
| **执行** | AI为主，开发者审查 | 产出本阶段交付物 |
| **AI自检** | AI | 对照本阶段出口标准逐项自查，输出自检报告 |
| **测量工具** | **AI强制执行**（不可跳过） | Spec出口→CDR基线 / Design出口→CDR趋势 / TDD出口→CDR+覆盖率 / Review出口→CDR+突变 / Retrospect出口→gate-quota close + 归档 |
| **Commit** | 开发者确认后AI执行 | 本阶段产出物提交到git |
| **Feynman门禁** | 开发者为主，AI提问 | P0: 不可跳过 / P1: 代码可跳1次 / P2: 可跳但记录原因 |

### 各阶段入口/出口

#### 阶段1: Spec（形式化规格）

| 项目 | 内容 |
|------|------|
| **入口条件** | 开发者接收外部需求（他人给定的需求/issue/用户故事，非自己编造） |
| **Step 0a: 需求接收与澄清** | ①需求的真实来源是谁？②这个需求打算解决谁的什么问题？③有没有明确不做的边界？④验收标准是什么？ |
| **Step 0b: 对标研究** | AI自动spawn 3个搜索代理(并行): ①GitHub搜索代理→clone+读参考实现②Web搜索代理→找官方规范③论文搜索代理→arXiv/ACM。产出: search-summary.md。预提交hook强制检查——无摘要阻断commit |
| **Step 0c: 范围决定** | 基于对标结果，明确：①范围内要做的；②标注为"已知但不在范围内"的（对标后发现存在，但有意识跳过）；③范围外（对标后仍然不知道的——这是真正的盲区） |
| **Step 1: 形式化规格** | （原需求溯源四问合并入 Step 0a） |
| **AI产出** | 形式化规格草稿（前置条件/后置条件/不变量/测试场景推导/边界定义）+ 对标研究报告 + AI推理摘要 |
| **AI自检** | ①每项验收标准是否可测试？②边界是否明确？③是否有遗漏的异常路径？④对标研究中发现的"反流程"是否已经决定纳入或跳过？⑤本设计的每一行变更是否都能对应到 SPEC 中的具体条款？是否存在 SPEC 未要求的"优化"？ |
| **出口标准** | 规格文档完成 + commit + Feynman门禁通过 |
| **Feynman问题** | ①这个功能解决谁的什么问题？②对标了哪个成熟系统？你发现了什么你原来不知道的？③你明确跳过了什么，为什么？ |

#### 阶段2: Design（架构设计）

| 项目 | 内容 |
|------|------|
| **入口条件** | Spec阶段通过 |
| **前置搜索** | 至少3个信息源，关键词+搜索结果记录到session log |
| **AI产出** | 架构设计文档（限界上下文/领域模型/ADR决策记录/备选方案对比）+ AI推理摘要 |
| **AI自检** | ①每个决策是否有明确理由？②备选方案是否充分枚举？③是否过度设计？④每项设计决策是否都能对应到 SPEC 中的具体条款？ |
| **出口标准** | 设计文档完成 + commit + Feynman门禁通过 |
| **Feynman问题** | ①在 ADR 中拒绝了哪个备选方案？引用 ADR 条款号解释原因 ②当前方案最大风险点对应 DESIGN 哪一节？③DESIGN 中是否有 SPEC 未要求的额外设计？ |

#### 阶段3: TDD（测试驱动开发）

| 项目 | 内容 |
|------|------|
| **入口条件** | Design阶段通过 |
| **流程** | RED（写失败测试）→ 开发者审查测试 → GREEN（最小实现）→ REFACTOR |
| **AI产出** | 测试用例（含参数选择理由）+ 实现代码（含逐行解释）+ AI推理摘要 |
| **测试双路径** | Primary path（正常）+ Fallback path（API不可用时本地fixture） |
| **AI自检** | ①测试是否覆盖边界？②断言能否抓到bug？③双路径是否都可用？ |
| **出口标准** | 测试+代码完成，所有测试通过 + commit + Feynman门禁通过 |
| **Feynman问题** | ①`[测试文件:行号]` 的参数 `[参数名]` 为什么选 `[值]` 而不是其他值？②`[源文件:行号]` 的 `[函数名]` 边界情况有哪些？测试覆盖了吗？③如果 `[源文件:行号]` 有一个单字符错误，断言能抓到吗？ |

#### 阶段4: Review（代码审查）

| 项目 | 内容 |
|------|------|
| **入口条件** | TDD阶段通过 |
| **流程** | 开发者先用5轴清单自查 → AI标记潜在问题 → 开发者确认修正 |
| **5轴** | 设计/可读性/性能/安全/可测性（详见code-review-checklist.md） |
| **需求一致性检查** | 当前实现是否仍然对齐Spec验收标准？有无偏离？ |
| **AI自检** | ①是否所有spec条款都有对应实现？②是否存在无spec依据的代码？③修正建议是否分级？④每项修正建议是否都是必要的（对应spec条款或明确的bug）？ |
| **出口标准** | 审查通过 + 修正commit + Feynman门禁通过 |
| **Feynman问题** | ①5轴审查发现的3个最大风险是什么？引用具体文件:行号 ②有没有代码接受了但没完全理解？指出文件:行号 ③`[源文件名]` 的 `[类名/函数名]` 用不同方案重写，变化最大的是什么？ |

#### 阶段5: Retrospect（项目审视）

| 项目 | 内容 |
|------|------|
| **入口条件** | Review阶段通过，所有代码已合并 |
| **Step 1** | **可追溯性审计**（详见traceability-audit.md）：正向SPEC→CODE矩阵 + 反向CODE→SPEC矩阵 + 合规评分 |
| **Step 2** | **失误记录**（故意聚焦错误而非成就）+ **known-traps复查**: AI 打开上次项目的 known-traps.md, 逐条检查当前项目是否复发。如有 → 标记为已复发。如无 → 记录"未复发" |
| **Step 3** | AI协作效果评估 |
| **Step 4** | Start/Stop/Continue + 新陷阱候选 |
| **AI自检** | ①审计是否逐类遍历？②失误是否追溯到根因？③是否有应加入known-traps的新陷阱？ |
| **出口标准** | 审视报告完成 + commit + Feynman门禁通过 |
| **Feynman问题** | ①这次最大的失误是什么？引用具体文件:行号和根本原因 ②下次类似项目哪里做不同？具体到流程/工具/检查点 ③有什么新陷阱应加入 known-traps.md？写下条目草稿 |

## 每阶段AI产出必需的附件

每个阶段AI交付产出物时，必须附带：

### AI推理摘要
- 我搜索了什么（关键词+来源）
- 我拒绝了什么方案（及原因）
- 我不确定什么（需要开发者重点关注的部分）

## 禁止行为

- 禁止接受开发者不理解每一行的代码
- 禁止用另一个AI的输出作为代码审查的唯一依据
- 禁止跳过SPEC阶段直接写代码
- 禁止事后润色session log
- 禁止AI总结"开发者学到了什么"——必须开发者自己说出来
- 禁止在Feynman门禁未通过时进入下一阶段
- 禁止在实现时附加 SPEC 未要求的"优化"或"改进"

## 引用索引

以下文件按需加载，提供深度参考：

| 文件 | 内容 | 何时加载 |
|------|------|---------|
| [references/five-phase-workflow.md](references/five-phase-workflow.md) | 五阶段详细交互点 | 进入具体阶段时 |
| [references/characterization-test-protocol.md](references/characterization-test-protocol.md) | 表征测试协议（C1/C2/C3—变更→对比→锁定） | TDD RED/GREEN/Review出口 |
| [references/feynman-gate.md](references/feynman-gate.md) | 费曼门禁机制规范 | 阶段出口时 |
| [references/search-agents/orchestrator.md](references/search-agents/orchestrator.md) | 搜索代理编排器（三通道并行+合并+强制执行） | Spec阶段Step 0b |
| [references/search-agents/github-agent.md](references/search-agents/github-agent.md) | GitHub 搜索代理 prompt | 编排器spawn |
| [references/search-agents/web-agent.md](references/search-agents/web-agent.md) | Web/文档搜索代理 prompt | 编排器spawn |
| [references/search-agents/papers-agent.md](references/search-agents/papers-agent.md) | 论文搜索代理 prompt | 编排器spawn |
| [references/research-protocol.md](references/research-protocol.md) | 三通道搜索执行规范 | Design阶段前置搜索时 |
| [references/ai-interaction-patterns.md](references/ai-interaction-patterns.md) | 6种AI交互模式 | 选择交互方式时 |
| [references/code-review-checklist.md](references/code-review-checklist.md) | 5轴审查清单 | Review阶段 |
| [references/commit-discipline.md](references/commit-discipline.md) | 结构化提交规范 | 每次commit前 |
| [references/openspec-integration.md](references/openspec-integration.md) | OpenSpec对接说明 | 全流程（规范制品层） |
| [references/spec-writing-guide.md](references/spec-writing-guide.md) | 形式化规格编写方法 | Spec阶段 |
| [references/dual-path-testing.md](references/dual-path-testing.md) | 双路径测试设计 | TDD阶段 |
| [references/known-traps.md](references/known-traps.md) | 已验证陷阱清单（项目模板） | 全流程 |
| [references/traceability-audit.md](references/traceability-audit.md) | 可追溯性审计规范 | Retrospect阶段Step 1 |
| [references/measurement-pyramid.md](references/measurement-pyramid.md) | 个人测量金字塔（GQM+EngThrive+AI质量悖论） | 全流程度量 |
| [references/project-classification.md](references/project-classification.md) | 项目分级（P0/P1/P2 → 不同门禁标准） | 项目启动时 |
| [references/startup-checklist.md](references/startup-checklist.md) | 项目启动预防性检查清单（C01-C06） | 新项目初始化时 |
| [references/bdd-response-protocol.md](references/bdd-response-protocol.md) | BDD 响应协议（模块卡住→诊断→治疗→升级） | BDD触发时 |
| [references/mutation-fix-guide.md](references/mutation-fix-guide.md) | 突变修复指南（三类修复模式+自动分类+触发链） | Review出口(自动) |
| [references/mutation-testing-guide.md](references/mutation-testing-guide.md) | 突变测试配置指南（方案B: 7论文证据+三模策略） | TDD/Review阶段 |
| [references/v0.2.0-roadmap.md](references/v0.2.0-roadmap.md) | v0.2.0 改进路线图（9缺口） | 全流程参考 |
| [config/quality-gates.yml](config/quality-gates.yml) | 质量门禁配置（版本控制） | CI集成 |
| [scripts/pre-commit-check.py](scripts/pre-commit-check.py) | Python 质量门禁（读 quality-gates.yml，框架检测） | 每次 commit |
| [scripts/cdr-sr-tracker.py](scripts/cdr-sr-tracker.py) | CDR/SR 追踪（v2: 多目录+AI检测+测试反馈） | 阶段出口 |
| [scripts/project-inspector.py](scripts/project-inspector.py) | 4-Phase 全流程项目检查器 | 项目启动/阶段出口 |
| [scripts/gate-quota-tracker.py](scripts/gate-quota-tracker.py) | 门禁配额追踪脚本 | 全流程 |
| [templates/session-log-v2.md](templates/session-log-v2.md) | 量化会话日志模板 | 全流程实时填写 |
| [templates/pre-project-self-assessment.md](templates/pre-project-self-assessment.md) | 项目启动前自评量表 | 项目启动前 |
| [templates/adr-template.md](templates/adr-template.md) | 架构决策记录模板 | Design阶段 |
| [templates/session-log.md](templates/session-log.md) | 交互记录模板 | 全流程实时填写 |
| [templates/retrospect-template.md](templates/retrospect-template.md) | 项目审视模板 | Retrospect阶段 |
