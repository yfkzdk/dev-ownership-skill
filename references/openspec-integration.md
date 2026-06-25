# OpenSpec 集成 — 规范驱动开发对接

> [来源: Fission-AI/OpenSpec — spec-driven development framework, 48K stars, 29 AI tools supported]
> [来源: forztf/skilled-spec-cn — 纯 Skills 实现的 OpenSpec 工作流, 零 CLI, Windows 兼容]
> [来源: 腾讯云开发者社区 2026-02-24 — 不安装 OpenSpec, 用 Skills 实现规范驱动开发]

## 概述

OpenSpec 提供规范驱动开发的标准工作流: Proposal → Design → Tasks → Apply → Archive。
dev-ownership 不重复发明这个流程，而是对接它。

## 两个方案

### 方案A: OpenSpec CLI（团队/企业）

```bash
npm install -g @anthropic/openspec
openspec init
openspec proposal "新增功能X"
openspec design
openspec tasks
openspec apply
openspec archive
```

适用: 50+ 人团队、CI 集成、严格审计

### 方案B: 纯 Skills（个人/小团队，推荐）

安装 OpenSpec 的 7 个纯 Skills 到 `.claude/skills/openspec/`，零安装依赖。

| Skill | 触发词 | 产出 |
|-------|--------|------|
| `/spec-start` | "开始规范流程"、"新需求" | 强制进入规范模式 |
| `/spec-proposal` | "创建提案" | proposal.md |
| `/spec-design` | "技术设计" | design.md |
| `/spec-tasks` | "拆分任务" | tasks.md |
| `/spec-apply` | "实现任务" | 受控代码变更 |
| `/spec-review` | "规范审查" | 一致性评分(0-100) |
| `/spec-archive` | "归档" | 归档总结 |

## 与 dev-ownership 五阶段的映射

```
OpenSpec 工作流          dev-ownership 阶段       交付物
───────────────         ─────────────────       ──────
spec-start ──────────→  1.Spec 入口             —
spec-proposal ───────→  1.Spec 执行             proposal.md
spec-design ─────────→  2.Design 执行           design.md + ADR
spec-tasks ──────────→  3.TDD (任务拆分)        tasks.md
spec-apply ──────────→  3.TDD (逐任务实现)      代码 + 测试
spec-review ─────────→  4.Review                 审查报告
spec-archive ────────→  5.Retrospect            审视报告 + lessons
```

## 文件结构

```
project-root/
├── openspec/
│   ├── specs/          ← 当前规范（OpenSpec 管理）
│   ├── changes/        ← 进行中的变更提案
│   └── archive/        ← 已完成归档
├── src/
├── tests/
└── .claude/skills/
    ├── dev-ownership/  ← 本 skill（行为纪律层）
    └── openspec/       ← OpenSpec 7 skills（规范制品层，方案B）
```

## Feynman 门禁与 OpenSpec 的对接

每个 dev-ownership 阶段的 Feynman 门禁，验证的是开发者对**该阶段 OpenSpec 制品**的理解：
- Spec 门禁 → 验证对 proposal.md 中验收标准的理解
- Design 门禁 → 验证对 design.md 中架构决策的理解
- TDD 门禁 → 验证对 tasks.md + 代码实现的理解
- Review 门禁 → 验证对审查发现的理解
- Retrospect 门禁 → 验证对整个项目的反思

## 方案选择建议

- 个人项目 / 2-5人小团队 → **方案B**（零安装、灵活、够用）
- 需要 CI 自动验证、合规审计 → **方案A**
- 先方案B跑2-3个功能，如果不够再切方案A
