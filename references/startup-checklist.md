# 项目启动预防性检查清单

> 此清单由已知陷阱自动生成。新项目初始化时必须逐项执行。
> 每项检查通过后才能进入第一个 commit。

---

## 自动检查项

### C01: .gitignore 完整性

- [ ] `.gitignore` 存在
- [ ] 包含 `__pycache__/`
- [ ] 包含 `*.pyc`, `*.pyo`
- [ ] 包含 `.pytest_cache/`
- [ ] 包含 `.coverage`
- [ ] 包含项目类型特定的忽略项（如 `*.db` for SQLite, `node_modules/` for Node）

**来源陷阱**: Trap-C02 (md2blog), Trap-C04 (mini-erp-core)
**重复次数**: 2

### C02: CLI 入口测试覆盖

- [ ] 如果项目有 `__main__.py` 或 CLI 入口
- [ ] 决定: CLI 入口是否纳入测试范围？
- [ ] 如果纳入 → 写至少 1 个 CLI 集成测试
- [ ] 如果不纳入 → 从 coverage 统计中显式排除（`[tool.coverage.run] omit = ["__main__.py"]`）

**来源**: md2blog Retrospect, mini-erp-core Retrospect
**重复次数**: 2

### C03: 项目类型检测

- [ ] 运行 `project-inspector.py Phase 0`——检测项目类型和缺失工具
- [ ] Phase 0 发现的所有 CRITICAL/HIGH 项在第一个 commit 前修复

**来源**: mini-erp-core（未运行 inspector, .coverage 误提交）
**重复次数**: 1

### C04: 已知陷阱加载

- [ ] 读取上一个项目的 `known-traps.md`
- [ ] 对于每个陷阱，检查当前项目是否存在相同的预防规则违反
- [ ] 如果存在 → 在第一个 commit 前修复

**来源**: v0.2.0-roadmap 缺口 15（陷阱跨项目复发检测）
**重复次数**: —（尚未实现）

### C05: quality-gates.yml 存在性

- [ ] 项目根目录或 `config/` 下存在 `quality-gates.yml`
- [ ] 阈值与本项目类型匹配（Python → ruff+mypy+bandit, Go → golangci-lint+go vet）

**来源**: mini-ERP（CI 有但缺 lint/type/security 步骤）
**重复次数**: 1

---

## 执行规则

1. **新项目第一次 git init 后立即执行此清单**
2. **所有 [ ] 必须变为 [x] 后才能创建第一个 commit**
3. **AI 主动提议执行，开发者确认**
4. **跳过某项需要开发者明确说明原因并记录到 session log**

---

## 更新规则

- 每个项目 Retrospect 发现新陷阱 → 如果该陷阱是"可以在项目初始化时预防的" → 加入此清单
- 如果某项连续 2 个项目未触发 → 降级为"可选检查"，保留但不强制
