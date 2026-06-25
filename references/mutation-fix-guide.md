# 突变修复指南 — 三层体系

> 来源: 多工具通用模式（mutmut/Stryker/PIT）+ Crossfiring ICSE 2025 + md2blog 实战
> 触发: Review 出口突变测试完成后自动生成诊断报告

---

## 三层修复体系

| 层级 | 谁执行 | 怎么触发 | 做什么 |
|------|------|---------|------|
| **Layer 0 — 检测** | 自动化(mutatest) | Review 出口 | 跑突变 → 输出幸存者列表 |
| **Layer 1 — 诊断+Auto-fix** | AI 自动 | 检测完成后 | 读代码→根因分类→写具体修复→自动修 |
| **Layer 2 — 人工修复** | 开发者 | Layer 1 推过来的 | AI 写具体建议, 开发者执行 |

---

## 根因分类（Layer 1 诊断核心）

| 根因 | 含义 | 判断标准 | 修复方向 | Auto-fix? |
|------|------|---------|------|:--:|
| **断言问题** | 断言只检查方向/类型, 不检查精确值 | survivor 是 arithmetic/boundary/value | 改精确值断言 | ✅ |
| **输入不足** | 只测了常规输入, 没测边界/空/None/不对称 | survivor 是 boolean/If_Statement | 加边界或不对称输入 | ✅ |
| **分支未覆盖** | 某个 if/else 分支根本没被走到 | survivor 是 If_False/If_True 且无覆盖测试 | 加覆盖该分支的测试 | ⚠️ |
| **等价代码** | 突变和原代码行为完全相同 | Slice/Unbound/类型检查通过 | 标记豁免 | ❌ |
| **设计耦合** | 测试依赖了不该依赖的实现细节 | 加断言会变脆弱 | 推 Layer 2 | ❌ |

---

## Layer 1 AI 诊断流程

```
每个幸存突变体:
  ① AI 读取突变位置源码(3-5 行上下文)
  ② AI 读取覆盖该行的一个测试
  
  ③ 搜索阶段（三通道并行——不凭训练数据）:
     GitHub: 搜索同类突变(如 If_Statement→If_False)在开源项目的修复记录
     Web:   搜索 "(mutation_type) fix pattern pytest" 最佳实践
     Papers: 搜索 Crossfiring ICSE 2025 / 相关论文的方法论验证
  
  ④ AI 基于搜索结果 + 代码上下文 → 判断根因(断言/输入/分支/等价/耦合)
  ⑤ AI 写具体修改建议(含代码 diff + 行号 + 搜索来源)
  ⑥ 判断: auto-fix?
     YES → AI 直接修改测试文件, 重跑确认 KILLED
     NO  → 标记 Layer 2, 写入 mutation-fixes.md
```

---

## 触发链路（自动——不可跳过）

```
Review 出口
  → run-mutation.py 跑突变测试（方案B）
  → 有幸存突变体 → AI 对每个执行诊断流程
  → Layer 1 auto-fix 成功的 → 直接修改测试
  → Layer 1 修不了的 → 写入 mutation-fixes.md
  → mutation-fixes.md 不存在 → pre-commit hook 阻断
  → 开发者处理 Layer 2
```

---

## 三类修复模式（Layer 1 的具体手段）

### 模式 1: 比较边界（最常见）
**为什么存活**: 测试没测恰好等于阈值的情况。
**修复**: 加一个传入恰好等于阈值的输入。

### 模式 2: 算术运算符
**为什么存活**: 断言只检查方向(>0)，不检查精确值。
**修复**: 改精确值断言 `assert result == expected`。

### 模式 3: 布尔逻辑
**为什么存活**: 测试用对称输入(两个都True或两个都False)。
**修复**: 加不对称输入(一个True一个False)。

---

## 豁免规则（以下不要求修复）

1. `__main__.py` — CLI 入口, 已知 0% 覆盖
2. `slice/unbound` — Python 语法等价突变
3. 日志/时间/配置行 — arid 节点

## 修复输出格式

`openspec/changes/mutation-fixes.md`:

```markdown
# 突变修复诊断 — [项目] Review

## 诊断 #N: [文件:行] — [根因]

源码、覆盖测试、为什么存活、具体修复(含代码diff)、Auto-fix判定
```
