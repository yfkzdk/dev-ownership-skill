# 测量工具触发标准与成本

> 每个测量工具必须有明确的触发条件、时间成本、阻断级别。
> 避免"每个 commit 全跑"和"从来都不跑"两个极端。

---

## 触发分级

| 级别 | 触发时机 | 时间预算 | 示例 |
|:--:|------|------|------|
| **T0** | 每次 git commit | <3秒 | lint, type check |
| **T1** | 每个阶段出口 commit | <10秒 | CDR, 覆盖率 |
| **T2** | 项目结束/Review 出口 | <5分钟 | 突变测试, gate-quota close |
| **T3** | 项目启动/一次性 | <30秒 | hook 安装, inspector |

---

## 全量工具触发矩阵

### T0: 每次 commit 自动触发（pre-commit hook）

| 工具 | 测什么 | 耗时 | 阻断级别 | 自动化状态 |
|------|------|:--:|:--:|:--:|
| **lint** (ruff/eslint) | 代码规范 | <1s | 硬阻断 | ✅ 已接入 hook |
| **type check** (mypy/tsc) | 类型安全 | <2s | 硬阻断 | ✅ 已接入 hook |
| **security** (bandit) | 安全漏洞 | <2s | 硬阻断 | ✅ 已接入 hook |
| **CDR** (cdr-sr-tracker) | 认知债务 | <2s | P0:硬阻断 P1:软警告 P2:仅报告 | ✅ 已接入 hook |
| **search check** (search-summary.md) | 搜索完整性 | <1s | 硬阻断(Spec/Design commit 时) | ✅ 已接入 hook |

**T0 总耗时**: <8秒。每个 commit 都跑。

### T1: 阶段出口触发（AI 在 commit 前执行）

| 工具 | 测什么 | 什么时候跑 | 耗时 | 阻断级别 | 自动化状态 |
|------|------|------|:--:|:--:|:--:|
| **分支覆盖率** (pytest --cov) | 测试覆盖 | TDD exit, Review exit | <10s | ≥90% 硬阻断 | ✅ 接入 hook(TDD exit) |
| **CDR 趋势** | CDR 变化方向 | 每个阶段出口 | <2s | 连续3次上升→警告 | ⚠️ 需要手动对比历史值 |
| **`--no-verify` 审计** | 跳钩次数 | Review exit | <1s | 便利性跳过>50%→警告 | ❌ 未自动化(需 git log 手动统计) |
| **Feynman 门禁** | 理解验证 | 每个阶段出口 | 2-5分钟 | P0:硬阻断 P1:可跳1次 P2:可跳 | ❌ 无自动化(依赖开发者/AI) |

**T1 总耗时**: <5分钟(含 Feynman 门禁)。

### T2: 项目结束触发（Review/Retrospect exit）

| 工具 | 测什么 | 什么时候跑 | 耗时 | 阻断级别 | 自动化状态 |
|------|------|------|:--:|:--:|:--:|
| **突变测试** (mutatest) | 测试断言质量 | Review exit: targeted diff / Retrospect: full / Small(<200行): all | 2-5min | **<55% 硬阻断 / 55-64% 软警告 / ≥64% 通过**。跑两次取中位数。连续 3 项目 <55% → 强制修复。方案B: diff-based + arid过滤 + 趋势对比 | ✅ Python 3.9+ |
| **pytest-gremlins** (备选) | 同上 | Review exit | 1-5分钟 | **≥55% 软警告** | ⚠️ 需要 Python 3.11+ |
| **mutatest2** (备选) | 同上 | Review exit | 2-10分钟 | **≥55% 软警告** | ⚠️ 需要 Python 3.11 |
| **gate-quota close** | 门禁配额结转 | Retrospect exit | <1s | 必须执行(否则下个项目配额错误) | ❌ 手动 |
| **known-traps 更新** | 陷阱库 | Retrospect exit | 2分钟 | 软要求 | ❌ 手动 |
| **session 归档** | 对话记录 | 项目结束/会话结束 | 1分钟 | 软要求 | ❌ 手动 |
| **baseline 复测** | 自评量表复测 | Retrospect exit | 3分钟 | 软要求 | ❌ 手动 |
| **SR 计算** (cdr-sr-tracker) | 稳定性比 | N≥30 时 Retrospect exit | <3s | ≥2.4 通过 | ⚠️ 脚本有,从未触发(无项目达到30 commits) |

**T2 总耗时**: <20分钟。每个项目结束跑一次。

### T3: 项目启动触发（一次性）

| 工具 | 测什么 | 什么时候跑 | 耗时 | 阻断级别 | 自动化状态 |
|------|------|------|:--:|:--:|:--:|
| **startup-checklist** (C01-C06) | 项目骨架 | git init 后 | <1分钟 | C01-C03 硬阻断 | ✅ 手动但有清单 |
| **project-inspector** (Phase 0+1) | 环境+结构 | git init 后 | <10s | 硬阻断(CRITICAL) | ❌ 手动(AI 忘了触发) |
| **CDR 基线** | CDR 初始值 | 第一个 commit 前 | <2s | 记录(不阻断) | ✅ T0 已覆盖 |
| **gate-quota set-level** | 项目分级 | git init 后 | <1s | 必须执行 | ✅ 手动但 AI 记得 |
| **install-hooks** | git hook | git init 后 | <1s | P0/P1 必须 | ✅ 手动但 AI 记得 |

**T3 总耗时**: <3分钟。一个项目只跑一次。

---

## 不应触发的条件（避免浪费）

| 工具 | 什么时候**不跑** |
|------|------|
| CDR | P2 测试项目 → 仅报告,不阻断 |
| 突变测试 | P2 测试项目 → 建议运行,不阻断 |
| SR | N<30 commits → 跳过(无统计意义) |
| 覆盖率 | `test:` 类型 commit(RED 阶段) → 不阻断 |
| 搜索检查 | 非 Spec/Design commit → 不检查 |
| BDD 协议 | 没有模块卡住 → 不触发 |
| project-inspector | 已有 .claude/gates/ 标记完成 → 不重复跑 |
| Feynman 门禁 | P2 测试项目 → 可跳过(需记录原因) |

---

## 当前缺口汇总

| 缺口 | 影响 | 修复方向 |
|------|------|------|
| T1: CDR 趋势对比 | 知道当前 CDR 但不知道是升是降 | pre-commit hook 存储上次 CDR 值,对比 |
| T1: `--no-verify` 审计 | 规则加了但未统计 | Retrospect 阶段 AI 跑 git log |
| T1: Feynman 门禁 | 唯一无自动化执行的关键步骤 | 暂无 hook 方案——依赖开发者纪律 |
| T2: 突变测试 | —（已解决: mutatest for Py3.9） | ✅ |
| T2: gate-quota close | 项目结束时 AI 忘了执行 | 加入 pre-commit hook(检测 retrospect commit 时提醒) |
| T2: session 归档 | 对话结束 AI 忘了 | 加入 Stop hook |
