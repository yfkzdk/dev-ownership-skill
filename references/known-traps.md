# Known Traps — 已验证陷阱清单（跨项目累积）

> 来源: md2blog, mini-erp-core, issue-triage-cli, mini-redis（4项目）
> 新项目启动时 C04 自动加载此清单检查

## 条目格式

- **发现项目**: 哪个项目首次发现
- **症状**: 具体表现
- **根因**: 为什么发生
- **预防**: 什么检查能提前发现

---

## Trap-C01: 模板系统边界模糊
- **发现项目**: md2blog
- **症状**: ADR 定义模板，实现时发现"模板"的范围不明确——是 HTML 文档结构还是仅 body 内包装？重构 3 次
- **根因**: ADR 未明确"谁生成什么，谁提供什么"
- **预防**: ADR 中所有接口边界必须有具体代码示例

## Trap-C02: Python 版本假设错误
- **发现项目**: md2blog, mini-redis, issue-triage-cli（3次）
- **症状**: `X | None` 语法 → `TypeError: unsupported operand type(s) for |`
- **根因**: Spec 阶段假设 Python 3.10+，目标环境是 3.9
- **预防**: 第一个 commit 前检查 `python --version`，或统一加 `from __future__ import annotations`

## Trap-C03: 数据库方法名拼写错误无法静态检测
- **发现项目**: mini-erp-core
- **症状**: `lastrowind` → `AttributeError: 'Cursor' object has no attribute 'lastrowind'`
- **根因**: Python 在 import 时不检查字符串中的方法/属性名
- **预防**: 提交前跑测试——静态分析无法拦截此类错误

## Trap-C04: 项目初始化 .gitignore 不完整
- **发现项目**: md2blog（__pycache__）, mini-erp-core（__pycache__+.coverage）
- **根因**: 项目骨架不含完整 .gitignore 模板
- **预防**: startup-checklist C01——新项目 git init 后强制检查

## Trap-C05: pre-commit hook 与 TDD RED 阶段冲突
- **发现项目**: issue-triage-cli, mini-redis
- **症状**: RED 阶段测试必须失败，但 hook 以"Tests failed"阻断 commit
- **根因**: hook 不区分 RED vs GREEN phase
- **预防**: `--no-verify` + 在 commit body 中记录原因（commit-discipline.md 已加规则）

## Trap-C06: AI 忘记运行阶段出口测量工具
- **发现项目**: 全部 4 个
- **症状**: CDR tracker / gate-quota close / mutation test 从未在阶段出口自动触发
- **根因**: 工具存在但触发依赖 AI 记忆——AI 在每个项目中都忘了
- **预防**: CDR tracker 已接入 pre-commit hook（git commit 自动触发）。memory 文件 `feedback_ai_phase_exit_enforcement.md` 已创建

## Trap-C07: `--no-verify` 绕过 hook 无记录
- **发现项目**: 全部 4 个
- **症状**: 多个 commit 用了 `--no-verify` 但 commit body 中无记录。mini-redis: 1/3 记录了
- **预防**: commit-discipline.md 已加规则——必须在 commit body 中记录原因。Retrospect 阶段统计分布

## Trap-C08: Windows 不支持 mutmut 原生运行
- **发现项目**: mini-redis（尝试运行）
- **症状**: `mutmut run` → "Please use WSL"
- **预防**: Windows 环境下跳过突变测试，或使用 WSL；在 quality-gates.yml 中按平台配置
