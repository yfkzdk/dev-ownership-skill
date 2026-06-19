# 突变测试 — 配置与使用指南

> 突变测试（Mutation Testing）是测量**测试质量**的唯一客观方法。
> 行覆盖率说"这行被跑过"，突变测试说"这行的 bug 被测出来过"。

## Windows 配置（已验证）

**前置条件**: Python 3.11+

```bash
pip install pytest-gremlins

# Windows 必须设置三项:
# 1. PYTHONUTF8=1       — 解决 GBK 编码问题
# 2. --gremlin-executor=subprocess — Windows 无 fork()
# 3. PYTHONPATH=src      — 项目路径（和运行测试一样）

set PYTHONUTF8=1
set PYTHONPATH=src
python -m pytest tests/ --gremlins --gremlin-executor=subprocess -v

# 结果解读:
# Zapped: X gremlins (%) — 被测出来的 bug
# Survived: Y gremlins (%) — 测试没发现的 bug（这是问题）
# 突变得分 = Zapped / (Zapped + Survived) × 100%

# 目标: ≥70%
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
