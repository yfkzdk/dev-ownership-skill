# 表征测试协议 — 通过"变更→对比"理解代码

> 理论基础: Michael Feathers *Working Effectively with Legacy Code* (2004)
> Golden Master / Characterization Test / Approval Test 三词同义
> 核心: "系统实际做了什么"比"它应该做什么"更重要——先拍照，后理解

---

## 核心流程

```
① AI 选目标 → ② 开发者拍"特征照片" → ③ AI 提示变更
  → ④ 开发者改代码 → ⑤ 重新运行 → ⑥ 对比照片
  → ⑦ 判断: 行为对吗？
    对 → 加断言锁定
    错 → 这是 bug，修掉
  → ⑧ 记录到 experiment log
```

## 三级集成

| 级别 | 触发 | 目标 | 时间 | 每项目 |
|------|------|------|:--:|:--:|
| **C1 快速拍照** | TDD RED 出口 | 给 1 个测试的特征拍照——改输入，看输出变化 | 2-3分钟 | ≥3次 |
| **C2 深度对比** | TDD GREEN 出口 | 给新实现代码拍照——改 1 行源码，对比前后输出 | 3-5分钟 | ≥2次 |
| **C3 盲区探测** | Review 出口 | 从突变报告选 1 个幸存者——亲手改，观察测试能否发现 | 5-8分钟 | ≥1次 |

## 详细步骤

### C1: 快速拍照（TDD RED 出口）

```
AI: "我们来看 test_format_date_none_returns_str。
     先记录它现在的行为——这叫'拍照'。

     运行: 输入 format_date(None) → 输出 ''(空字符串)
     这是第一张照片。

     现在改输入: 把 None 改成 date(1999,1,1)
     你猜输出会变吗？"

开发者: 改 → 运行 → format_date(date(1999,1,1)) → '1999-01-01'

AI: "照片对比:
     输入 None      → 输出 ''
     输入 1999-01-01 → 输出 '1999-01-01'

     你学到了什么？用一句话。"

开发者: "这个函数有两条路径——None 走捷径，日期走 strftime。"

→ AI 记录到 session log
```

### C2: 深度对比（TDD GREEN 出口）

```
AI: "我们来看刚实现的 parse_request 函数。
     先拍照。

     运行: GET /index.html HTTP/1.1 → 200 OK + body
     这是基线照片。

     现在改 1 行源码: 把 'if not has_host: return None' 删掉
     重新运行同一个测试。

     你猜会发生什么？"

开发者: "测试应该还是通过？因为测试里带了 Host 头。"

AI: "对。测试仍然通过。但你刚删掉了 Host 检查！
     这意味着——你的测试没有保护 'Host 头缺失→400' 这个行为。

     要不要加一个测试来锁定这个行为？"

→ 如果开发者说"要" → AI 帮忙写测试
→ 如果开发者说"不需要" → 记录为"已知设计决策"
```

### C3: 盲区探测（Review 出口）

```
AI: "突变报告显示: parser.py:83 的 'In→NotIn' 突变存活了。
     这意味着——把 README.md 的排除逻辑反过来，测试没发现。

     来亲自试一下:
     1. 打开 parser.py 第 83 行附近
     2. 把 'if name in (\"README.md\", \"readme.md\")' 改成
        'if name not in (\"README.md\", \"readme.md\")'
     3. 运行测试——你猜结果？"

开发者: "测试应该会失败？因为 README 不再被排除了？"

AI: "试一下。"

开发者: 改 → 跑测试 → 全部通过！

AI: "全部通过！这意味着——你的测试套件对 'README 排除逻辑' 完全没有保护。
     如果有人不小心写成了 not in，所有非 README 文件都会被跳过——测试不会报。

     这是一个需要修复的盲区，还是你决定不修？"

→ 如果要修 → AI 帮忙写测试
→ 如果不修 → 记录豁免原因
```

## 跳过规则

```
P0 项目: C1 不可跳过, C2 不可跳过, C3 不可跳过
P1 项目: C1 可跳 1 次, C2 可跳 1 次, C3 可跳 0 次
P2 项目: 全部可选
每次跳过: 说 "skip" + 记录原因
```

## Session Log 记录格式

```yaml
char_test_log:
  - level: C2
    project: mini-http
    function: parse_request
    input: "GET / HTTP/1.1\\r\\nHost: x\\r\\n\\r\\n"
    output_before: "200 OK"
    change: "deleted 'if not has_host' check"
    output_after: "200 OK (unchanged!)"
    insight: "Host header check is not protected by any test"
    action: "added test_missing_host test"
    timestamp: 2026-06-21T16:00:00
```

## 触发链路（自动——不可跳过）

```
C1: TDD RED commit 前 → AI 选 1 个 staged test → 执行 C1
    → 记录到 char_test_log → 无记录 → pre-commit hook 阻断

C2: TDD GREEN commit 前 → AI 选 1 个刚实现的函数 → 执行 C2
    → 记录到 char_test_log

C3: Review 出口 → AI 从 mutation-fixes.md 选 1 个 survivor → 执行 C3
    → 记录到 char_test_log
```

## AI 角色

| 角色 | 做什么 | 不做什么 |
|------|------|------|
| **选目标** | 从 staged tests / 新函数 / 突变报告选 | 不替开发者选 |
| **提示变更** | 建议一个具体的、可逆的代码修改 | 不给答案 |
| **对比展示** | 清晰呈现"改前 vs 改后" | 不评价"好坏" |
| **记录** | 每次操作写入 session log | 不跳过 |
