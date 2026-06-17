# 结构化提交规范

> [来源: Conventional Commits v1.0.0 — conventionalcommits.org]
> [来源: 0x404/ccs_dataset — 88,704条commit, 116个开源项目的真实类型分布]
> [来源: TituxMetal#19 + cc-foundry + nimblehq#604 — 选择性暂存/质量门/8步pipeline]
> [来源: workflow-patterns — TDD 11-step lifecycle with atomic commits]

## 硬性规则

1. **一个阶段至少一个commit。** 禁止跨阶段合并。禁止事后整理commit历史。
2. **TDD每个子阶段独立commit。** RED(test)→GREEN(feat/fix)→REFACTOR(refactor) 不允许合并为一个 `feat`。
3. **禁止 `git add -A`。** 只暂存与当前变更逻辑相关的文件。
4. **依赖顺序提交。** 阶段内部: 基础设施 → 核心逻辑 → 测试 → 文档。
5. **文档与代码分开提交。** DESIGN.md 和 src/ 不在同一个commit。
6. **Commit message必须包含spec条款引用。**
7. **同一feature的commit之间必须通过Refs字段关联。**

## Commit Type 定义

> 来源: Conventional Commits v1.0.0 + 0x404 研究团队的精准定义（减少类型重叠）

| Type | 用途 | 判断标准 | 真实占比 |
|------|------|---------|:--:|
| `fix` | 修复 bug | 修复了与 spec 不符的行为 | 27.0% |
| `chore` | 维护任务 | 不修改 src 或 test 文件 | 26.0% |
| `feat` | 新功能 | 新增了 spec 中定义的功能 | 17.2% |
| `refactor` | 重构 | 改结构不改行为，测试全绿 | 9.6% |
| `docs` | 文档 | 只改 .md / 注释 | 8.1% |
| `test` | 测试 | 只添加/修改测试，不改源码 | 6.0% |
| `build` | 构建系统 | 改 pyproject.toml / 依赖 / 打包 | 3.5% |
| `ci` | CI/CD | 改 .github/workflows / 流水线 | 1.3% |
| `style` | 代码风格 | 只改格式/空格/lint fix (无逻辑变化) | 0.9% |
| `perf` | 性能 | 改进性能，不改行为 | 0.4% |

## Type 选择决策树

```
改了什么？
├── 只改了 .md 文件？                                    → docs
├── 只改了测试文件(tests/)？                              → test
├── 只改了 CI/构建配置？                                  → ci / build
├── 只改了格式(空格/换行/ruff fix)？                      → style
├── 修了一个与 spec 不一致的行为？                         → fix
├── 新增了 spec 中定义的功能？                             → feat
├── 改进已有代码结构，测试全绿，行为不变？                  → refactor
├── 改进性能，行为不变？                                   → perf
└── 都不符合？                                            → chore
```

## 阶段内 Commit 序列

### Spec阶段
```
docs(spec): add formal specification for <feature> [spec-§1-§N]
```

### Design阶段
```
docs(design): add architecture design with ADRs [spec-§1-§N]
```

### TDD阶段 — 必须拆分为三个独立commit

```
RED:
  test(<scope>): add failing tests for <feature> [spec-§X.Y]

GREEN:
  feat(<scope>): implement <feature> [spec-§X.Y]
  Refs: <test-commit-hash>
  (或 fix(<scope>): 如果是修bug)

REFACTOR (如有):
  refactor(<scope>): <what was restructured> [spec-§X.Y]
  Refs: <impl-commit-hash>
```

### Review阶段
```
fix(<scope>): <具体修复内容> [spec-§X.Y]
(多个fix分开commit——一个问题一个commit)
```

### Retrospect阶段
```
docs(retrospect): project review with traceability audit
```

## 提交前自检

每个commit之前，AI执行：

1. [ ] 这个 commit 的 type 是上面 11 种之一吗？
2. [ ] TDD 阶段是否拆分了 test → feat → refactor？（不允许合并为一个 feat）
3. [ ] Staged files中是否混入了 spec 文档和源码？
4. [ ] Commit message 是否包含 spec 条款引用？
5. [ ] 如果是系列commit，Refs 字段是否指向了前一个commit？
6. [ ] 是否可以独立 revert 这个 commit 而不影响其他功能？

## `--no-verify` 使用规则

1. **每次使用 `--no-verify` 必须在 commit body 中记录原因**：
   ```
   --no-verify: <具体原因>
   例: --no-verify: TDD RED phase — tests expected to fail
   例: --no-verify: coverage gap (__main__.py 0%) — deferred to next iteration
   ```

2. **禁止原因**（出现即违规）:
   - "为了快速提交"
   - "lint 问题太多懒得修"
   - 空白或无原因

3. **Retrospect 统计**: 项目结束时，AI 必须统计 `--no-verify` 次数和原因分布。
   - RED 阶段占比高 → 正常
   - "懒得修"占比高 → 警告
   - 原因缺失 → 违规

## 反模式

| 反模式 | 为什么错 | 真实数据佐证 |
|--------|---------|------------|
| TDD 阶段只提交一个 `feat`（test+src 混合） | 测试和实现是不同目的——test 独立 commit 才能验证"测试先于代码" | 真实项目中 6% 的 commit 是独立 test 类型 |
| bug 在 commit 前修复所以不提交 `fix` | `fix` 是 27%（最常见的类型）——bug 是正常开发过程的一部分，不是耻辱 | 你的项目 fix=0%，真实项目 fix=27% |
| 重构混在 `feat` 里 | 重构和新增功能不应该在同一次 diff 中出现——review 无法区分意图 | 真实项目中 refactor 占 9.6% |
| `.gitignore` 修复用 `chore` 在 TDD 之后 | 应该在项目第一个 commit 就包含完整 .gitignore。startup-checklist C01 已覆盖 | — |

## 示例: 一个完整的 TDD commit 序列

```
test(order): add failing test for line item total calculation  [spec-§4.1]
feat(order): implement line item total calculation  [spec-§4.1]
  Refs: a1b2c3d
refactor(order): extract calculate_line_total private method  [spec-§4.1]
  Refs: e4f5g6h
```

每个 commit 独立可 revert，测试全绿，意图清晰。
