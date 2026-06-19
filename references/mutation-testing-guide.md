# 突变测试 — 配置与使用指南

> 突变测试（Mutation Testing）是测量**测试质量**的唯一客观方法。
> 行覆盖率说"这行被跑过"，突变测试说"这行的 bug 被测出来过"。

## 证据基础

本指南基于 7 篇工业级论文（全文阅读，非摘要推断）：

| 论文 | 关键发现 | 我们的应用 |
|------|---------|----------|
| Google TSE 2022 | diff-based scoping + arid 过滤(15%→89%有效率) + 5算子(AOR/LCR/ROR/UOI/SBR) | diff-based + 3类arid规则 |
| Google ICSE 2021 | r_s=0.9突变vs测试量, 覆盖率r_s=-0.24, 1470万突变体, 一行一个够 | 一行一个突变体 |
| Zenseact ASE 2024 | 趋势 > 快照, dashboard > 文本报告, 16条CI建议 | 历史趋势对比 |
| Crossfiring ICSE 2025 | 84%幸存者可通过增强断言杀死, 6x提升 | 幸存者处理指南 |
| LLM FSE 2026 | LLM生成有效率43%→66%(SMART), 7B≈GPT-4o | 未来方向,暂不采用 |
| FlakiMe | 5% flakiness→2-4%分数波动, 两次重跑缓解 | 跑两次取中位数 |
| Zhang ICSME | R²=0.86, 两种评估指标强相关, 只用一个指标有效 | 只用突变得分 |

## 三模策略

| 模式 | 触发 | 范围 | 深度 | 时间 |
|------|------|------|------|:--:|
| **review** | Review 出口 | `git diff` 变更的 .py 文件 | 每文件 -n 20, 跑两次取中位数 | <2min |
| **retrospect** | 项目结束 | 全项目 src/ | -n 30, 跑两次取中位数 | <10min |
| **small** | <200行项目(自动检测) | 全项目 | -n 100(不采样) | <5min |

## Arid 突变过滤

仅需 3 个规则——Google 经验证明这 3 类从 15%→80% 有效率(TSE 2022 §3.2.5):

```
1. 日志调用: .log( / logger. / logging. / debug( / info( / warn( / error(
2. 时间操作: sleep( / deadline / timeout / backoff / set_deadline(
3. 配置/flag: .flags / .config / FLAGS_ / FLAG_
```

标记为 arid 的行 → 不生成突变体。避免在"日志打点""超时设置""开关变更"上浪费测试精力。

## Windows 配置（Python 3.9 — 已验证）

**推荐**: `mutatest`（AST-based，无文件修改，Azure Pipelines 官方测试 Windows）

```bash
pip install mutatest
set PYTHONPATH=src
mutatest -s src/<your_module> -t "python -m pytest tests/ -q" -n 20

# 结果解读:
# DETECTED: X — 被测出来的 bug（好）
# SURVIVED: Y — 测试没发现的 bug（盲区）
# 突变得分 = DETECTED / (DETECTED + SURVIVED) × 100%
# 目标: ≥70%
```

## Windows 配置（Python 3.11+ — 已验证）

**备选**: `pytest-gremlins`（3.73× 比 mutmut 快，pytest 集成）

```bash
pip install pytest-gremlins
set PYTHONUTF8=1
set PYTHONPATH=src
python -m pytest tests/ --gremlins --gremlin-executor=subprocess -v
```

## macOS/Linux 配置

```bash
pip install mutmut
mutmut run
mutmut results  # 查看突变得分
```

## 原理

```
原始代码:        x = a + b
注入突变:        x = a - b   (将 + 改为 -)
测试应该失败:    断言 x == sum  → 失败了 → 突变被"杀死" ✅
如果测试没失败:  断言 x == sum  → 通过了 → 突变"存活" ❌
                → 这个测试没有真正验证加法逻辑

"存活"的突变 = 测试套件的盲区
```

## 得分标准

| 得分 | 评价 | 处置 |
|------|------|:--:|
| ≥70% | 测试质量合格 | 通过 |
| 50-70% | 测试有盲区 | 警告——补充断言 |
| <50% | 测试形式主义 | 阻断——重写测试 |

## 常见存活突变及修复

| 突变类型 | 例子 | 为什么存活 | 怎么修 |
|---------|------|-----------|--------|
| return value → None | `return result` → `return None` | 没测返回值类型 | 加 `assert isinstance(result, ...)` |
| not x → x | `if not items:` → `if items:` | 没测空列表分支 | 加 `test_empty_items_raises` |
| or → and | `a or b` → `a and b` | 两个条件总是同时为 True | 加测试覆盖"仅 a True""仅 b True" |
| + → - | `total + amount` → `total - amount` | 只测了一组数据 | 加边界值测试 |

## 已知限制

- **Windows**: 需要 Python 3.11+ 和 `PYTHONUTF8=1`。Python 3.9/3.10 不支持 pytest-gremlins。
- **中文源码**: `PYTHONUTF8=1` 必须设置，否则 `pathlib.read_text()` 使用 GBK 编码报错。
- **耗时**: 突变测试比普通测试慢 10-100 倍。只在 Review 阶段出口运行一次，不在每次 commit 时跑。
