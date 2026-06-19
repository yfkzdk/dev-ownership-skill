# 突变修复指南 — 三类修复模式

> 来源: 多工具通用模式（mutmut/Stryker/PIT）+ Crossfiring ICSE 2025
> 触发: Review 出口突变测试完成后自动生成修复建议
> 不需要新工具——直接使用突变报告输出

## 触发链路（自动——不可跳过）

```
Review 出口
  → run-mutation.py 跑突变测试（方案B）
  → 有幸存突变体 → 自动分类（边界/算术/布尔）
  → 对每个幸存突变体输出修复建议
  → 写入 openspec/changes/mutation-fixes.md
  → pre-commit hook 检查: mutation-fixes.md 存在？
  → 不存在 → 阻断: "请完成突变修复分类后提交"
  → 存在 → 放行
```

## 三类修复模式

### 模式 1: 比较边界（最常见）

**为什么存活**: 测试只测了"明显大于"和"明显小于"，没测恰好等于阈值的情况。

**修复方法**: 加一个测试——传入**恰好等于阈值的值**。

**示例**:
```
存活突变: parser.py:122 — `==` 突变为 `>=`
覆盖测试: test_parser.py::test_blank_lines_separate_paragraphs
修复: 加 test_blank_line_with_single_space — 传入仅含一个空格的字符串
      → 验证空格行也被视为空白行(== 和 >= 在空字符串上行为等价)
```

### 模式 2: 算术运算符

**为什么存活**: 断言只检查"结果是正数"，不检查"结果是多少"。`+` 和 `-` 都产生正数。

**修复方法**: 把方向性断言改成**精确值断言**。

**示例**:
```
存活突变: generator.py:160 — `Div` 突变为 `Add`
覆盖测试: test_generator.py::test_build_output
修复: 将 `assert result > 0` 改为 `assert result == 5`
      → Div 产生 5，Add 产生 12——只有 Div 是正确的
```

### 模式 3: 布尔逻辑

**为什么存活**: 测试用对称输入（两个条件同时为 True 或同时为 False）。`&&` 和 `||` 在对称输入下行为一致。

**修复方法**: 加**不对称输入**（一个条件为 True，另一个为 False）。

**示例**:
```
存活突变: generator.py:83 — `Or` 突变为 `And`
覆盖测试: test_generator.py::test_generate_rss_missing_config  
修复: url="" title="X" description="D"——只有 url 为空
      → Or 为 True(desc非空), And 为 False(url为空)
      → Or 触发 ValueError, And 不触发——暴露差异
```

## 分类规则（自动判定）

run-mutation.py 解析 mutatest 输出后，对每个 SURVIVED 行自动分类：

```
幸存突变内容含:
  "<class 'ast.Eq'>" / "<class 'ast.Gt'>" / "<class 'ast.Lt'>" 
  / "<class 'ast.GtE'>" / "<class 'ast.LtE'>" 
  → 分类: 比较边界

  "<class 'ast.Add'>" / "<class 'ast.Sub'>" / "<class 'ast.Mult'>" 
  / "<class 'ast.Div'>" / "<class 'ast.Mod'>"
  → 分类: 算术运算符

  "<class 'ast.Or'>" / "<class 'ast.And'>" / "<class 'ast.Not'>"
  / "If_Statement"
  → 分类: 布尔逻辑

  "None to" / "to None" / "True to False" / "False to True"
  → 分类: 值替换

  其他 → 分类: 其他
```

## 豁免规则——不需要修复的

以下类型的幸存突变体**标记为"豁免"**，不要求修复:

1. `__main__.py` — CLI 入口, 已知 0% 覆盖
2. `slice` / `unbound` — Python 语法等价突变 (`x[1:]` = `x[slice(1,None)]`)
3. 日志/时间/配置行 — arid 节点（3 规则匹配）

## 修复输出格式

`openspec/changes/mutation-fixes.md`:

```markdown
# 突变修复建议 — mini-diff Review

## 得分: 62% (18/29) — ⚠️ 55-64% 软警告

### 需要修复 (3)

| # | 文件:行 | 类型 | 覆盖测试 | 修复建议 |
|:--:|------|------|---------|------|
| 1 | diff.py:83 | 布尔逻辑 | test_rss_missing_config | 加不对称输入: url空+title满 → 应报ValueError |
| 2 | diff.py:160 | 算术运算符 | test_build_output | 改 `assert result > 0` → `assert result == 5` |
| 3 | parser.py:122 | 比较边界 | test_blank_lines | 加仅含空格的单行输入 → 验证被视为空行 |

### 豁免 (2)

| 文件:行 | 原因 |
|------|------|
| __main__.py:31 | CLI入口, 已知0%覆盖 |
| diff.py:45 | Slice等价突变——Python语法等价 |
```

## 修复流程

```
1. 突变报告输出 → 自动分类幸存突变体
2. 对"需要修复"列表 → 按严重度排序(布尔 > 算术 > 边界)
3. 开发者逐条处理 → 补断言或测试 → 重跑突变 → 确认 KILLED
4. 标记为已修复 → 下次 Review 出口重新分类
```
