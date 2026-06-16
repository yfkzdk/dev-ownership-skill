# 项目分级 — Feynman 门禁标准

> 不同项目有不同的质量标准。一个分级避免"这是测试项目"被无限合理化。

---

## 三级定义

| 级别 | 定义 | 判断标准 | 示例 |
|------|------|---------|------|
| **P0** | 面试/生产项目 | 影响他人对你的评价，或影响实际业务运行 | VoIP计费(面试题)、部署到生产的服务 |
| **P1** | 练习项目 | 以学习为目的，需要一定纪律约束 | 自己学新框架的demo、预研 |
| **P2** | 测试/验证项目 | 验证工具/流程用的，不关心项目本身 | md2blog(测skill流程)、mini-erp-core(测v0.2.1) |

## 分级后果

| | P0 面试/生产 | P1 练习 | P2 测试/验证 |
|------|:--:|:--:|:--:|
| **设计门禁** (Spec, Design) | 不可跳过 | 不可跳过 | 可跳过(记录原因) |
| **代码门禁** (TDD, Review, Retrospect) | 不可跳过 | 可跳 1 次/项目 | 可跳过(记录原因) |
| **跳过惩罚** | — | 累计到下一个 P0/P1 项目 | 不累计 |
| **pre-commit hook** | 必须安装 | 建议安装 | 可选 |
| **session-log** | 必须实时填写 | 必须实时填写 | 可选 |
| **CDR/SR 追踪** | 每个阶段出口运行 | 项目结束运行 | 可选 |
| **startup-checklist** | 全部 [x] 才能 commit | C01-C03 必须 [x] | 建议 [x] |
| **项目结束复盘** | 必须(含自评量表复测) | 建议 | 不需要 |

## 级别判定流程（项目启动时执行）

```
开发者回答 3 个问题:

Q1: 这个项目做给谁看的？
  → 面试官/同事/用户 → 考虑 P0
  → 自己 → 继续 Q2

Q2: 项目的需求的来源是什么？
  → 外部给定的需求(别人要我做的) → 考虑 P1 或 P0
  → 自己设定的需求(我自己想做的) → 考虑 P1 或 P2

Q3: 如果这个项目代码质量很差，你会后悔吗？
  → 会后悔 → P1
  → 不会后悔，这只是测试 → P2
```

## 级别变更

级别不是锁死的。如果 P2 项目做出了超出预期的价值，可以在 Retrospect 阶段升级为 P1（补做跳过的门禁）。

如果 P1 项目决定用于面试，在面试前升级为 P0（必须补完所有跳过的门禁）。

## 与 gate-quota-tracker 集成

```bash
# 项目启动时设定级别
python scripts/gate-quota-tracker.py --project-id <name> set-level P0
python scripts/gate-quota-tracker.py --project-id <name> set-level P1
python scripts/gate-quota-tracker.py --project-id <name> set-level P2

# 查询当前级别和配额
python scripts/gate-quota-tracker.py --project-id <name> status
```

## 修改记录

- 原 `gate-quota-tracker.py` 硬编码配额=1，未区分项目级别
- 本次更新: 根据 P0/P1/P2 动态调整配额和规则
