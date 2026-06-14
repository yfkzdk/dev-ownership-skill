# 结构化提交规范

> [来源: TituxMetal/claude-code-tool-kit#19 — 单commit崩坏修复: 9次尝试/12分钟→commit序列策略]
> [来源: cc-foundry git-commit plugin — 8步pipeline: 识别逻辑单元→排序→质量门→自审→选择性暂存→消息验证→提交→验证]
> [来源: nimblehq/ios-templates#604 — /commit skill 强制选择性暂存, 禁止 git add -A]

## 硬性规则

1. **一个阶段至少一个commit。** 禁止跨阶段合并。禁止事后整理commit历史。
2. **禁止 `git add -A`。** 只暂存与当前变更逻辑相关的文件。
3. **依赖顺序提交。** 阶段内部: 基础设施 → 核心逻辑 → 测试 → 文档。
4. **文档与代码分开提交。** DESIGN.md 和 src/ 不在同一个commit。
5. **Commit message必须包含spec条款引用。**
6. **同一feature的commit之间必须通过Refs字段关联。**

## 结构化 Commit Message 格式

```
<type>(<scope>): <subject>  [spec-§X.Y]

<body>
- 为什么这样改（不是改了什么——diff已经显示改了什么）
- 拒绝的备选方案及原因

Refs: <前一个相关commit的短hash>
关联: Spec条款 §X.Y / ADR-N (如有)
```

### Type 取值

| Type | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复bug |
| `refactor` | 重构（不改变外部行为） |
| `test` | 添加/修改测试 |
| `docs` | 文档变更 |
| `chore` | 构建/工具配置 |

### 示例

```
feat(country-code): add E.164 full code set with Trie lookup  [spec-§2.2]

Replaced sorted() per-call approach with module-level Trie constant.
Rejected regex-only approach — 1-to-3-digit country codes break simple patterns.
Rejected strategy pattern — only 3 rate rules, YAGNI.

Refs: a1b2c3d
关联: Spec条款 §2.2 / ADR-3
```

## 阶段内 Commit 序列

每个阶段内部按以下顺序提交：

### Spec阶段
```
1. docs(spec): add formal specification  [spec-§1-§N]
```

### Design阶段
```
1. docs(design): add ADR for architecture decisions  [spec-§X]
2. docs(design): add domain model diagram  [spec-§X]
```

### TDD阶段
```
1. test(country-code): add E.164 prefix matching tests  [spec-§2.2]
2. feat(country-code): implement Trie-based country code extraction  [spec-§2.2]
   Refs: <test-commit-hash>
```

### Review阶段
```
1. fix(money): add Decimal(str(float)) defense against IEEE 754  [spec-§1.4]
   Refs: <impl-commit-hash>
```

### Retrospect阶段
```
1. docs(retrospect): add project review report
```

## 提交前自检

每个commit之前，AI执行：

1. Staged files是否只包含与本变更相关的文件？
2. Staged files中是否混入了spec文档和源码？
3. Commit message是否包含spec条款引用？
4. 如果是系列commit，Refs字段是否指向了前一个commit？
5. 是否可以独立revert这个commit而不影响其他功能？

使用 `scripts/pre-commit-check.sh` 自动化检查。
