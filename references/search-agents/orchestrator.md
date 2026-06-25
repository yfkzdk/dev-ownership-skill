# Search Agent Orchestrator

> Spec 阶段 Step 0b 的自动化实现。三个代理并行运行，产出合并为搜索摘要。
> AI 不可跳过此步骤——pre-commit hook 在 proposal.md 提交时强制检查。

## 触发时机

Spec 阶段的 Step 0b（对标研究）开始时，AI 必须同时 spawn 三个搜索代理。

## 代理定义

| 代理 | Prompt 文件 | 产出文件 | 搜索范围 |
|------|-----------|---------|---------|
| GitHub | `search-agents/github-agent.md` | `search-github.md` | 开源实现、模块结构、设计决策 |
| Web | `search-agents/web-agent.md` | `search-web.md` | 官方规范、技术文档、RFC/ISO |
| Papers | `search-agents/papers-agent.md` | `search-papers.md` | arXiv/ACM/Google Scholar |

## AI 执行流程

```
Spec 阶段 Step 0b 开始:
  1. AI 准备搜索上下文（domain, language, key_terms）
  2. AI 同时 spawn 3 个 Agent（run_in_background=true）:
     - Agent("github-search", prompt=github-agent.md + context)
     - Agent("web-search", prompt=web-agent.md + context)
     - Agent("papers-search", prompt=papers-agent.md + context)
  3. 三个代理并行运行，各自写入 openspec/changes/search-{channel}.md
  4. 所有代理完成后，AI 读取三个报告
  5. **Phase 4: 交叉推理**（AI 主导——不可自动化）
     AI 读取三个报告后，进行跨通道关联推理:
     - GitHub 说 X，Web 规范说 Y——这是矛盾还是互补？
     - 论文的数据能不能解释 GitHub 参考实现中的某个设计选择？
     - 三个通道有没有同时指向同一个结论？（如果三个独立通道都指向同一结论，置信度极高）
     - 有没有一个通道的信息填补了另一个通道的空白？
     → 产出: openspec/changes/search-cross-reference.md
  6. AI 合并为 openspec/changes/search-summary.md
  7. AI 基于搜索摘要起草 proposal.md
```

## 搜索上下文模板

AI 在 spawn 代理时，必须提供以下上下文（每个代理的 prompt 末尾追加）:

```
## Search Context
- Domain: [项目要解决什么问题]
- Language: [目标实现语言]
- Key terms: [5-10个搜索关键词]
- Known references: [已有的参考来源]
- Constraints: [零依赖 / 特定平台 / 性能要求]
```

## 合并输出格式

### Phase 4 交叉推理输出

`search-cross-reference.md` 结构（AI 亲自写，不交给子代理）:

```markdown
# 交叉推理报告 — [项目名]

## 通道间矛盾
- [GitHub发现] vs [Web规范发现]: [是否矛盾？如何解释差异？]
- 如无矛盾: "三个通道独立搜索，未发现矛盾。"

## 通道间互补
- GitHub 发现 [X]，但未说明为什么选这个方案
- 论文 [Y] 提供了 [X] 的理论依据: [具体数据/原理]
- → 综合结论: [方案X有理论支撑，可采用]

## 三通道共识
以下结论在 ≥2 个独立通道中被发现:
- [结论1]: GitHub([repo]) + Web([spec §X])
- [结论2]: ...

## 意外发现
单个通道发现了其他通道未覆盖的信息:
- [发现]: 来自 [通道]，其他通道未提及
- 重要性: [对我们的设计有多大影响]

## 推理出的新结论
以下结论不在任何单一通道的输出中，而是从跨通道关联中推理得出:
- [新结论]: [推理链条——从A通道的X + B通道的Y → 推论出Z]
```

### 搜索摘要合并

`search-summary.md` 结构:

```markdown
# 三通道搜索摘要 — [项目名]

## GitHub
[从 search-github.md 提取的关键发现]
- 可借鉴的模式: ...
- 拒绝的模式: ...（及原因）

## Web/文档
[从 search-web.md 提取的关键发现]
- 必须遵守的规范要求: ...
- 规范中明确的边界条件: ...

## 论文
[从 search-papers.md 提取的关键发现]
- 或 "确认搜索后未找到相关论文。搜索了: [关键词列表]"

## 对设计的直接影响
- 因为搜索结果，采用 [X] 模式作为 [模块] 的实现方案
- 因为搜索结果，拒绝 [Y] 方案（原因: ...）
- 因为搜索结果，标记 [Z] 为"已知但不在范围内"
- **交叉推理发现**: [从跨通道关联中推理出的设计决策——这是任何单一通道都无法独立得出的]
```

## 强制执行

**pre-commit hook**: 如果 staged files 包含 `proposal.md` 或 `design.md`，但 `search-summary.md` 不存在或早于 proposal.md 的最后修改时间 → **阻断 commit**。

```
检查逻辑:
  if "openspec/changes/proposal.md" in staged:
      if not exists("openspec/changes/search-summary.md"):
          BLOCK: "提交 proposal.md 前必须完成三通道搜索。请运行搜索代理。"
      if mtime(search-summary.md) < mtime(proposal.md):
          BLOCK: "搜索摘要早于最新提案——请重新运行搜索代理。"
```

## FAQ

**Q: 论文通道总是找不到论文怎么办？**
A: 在 search-papers.md 中记录搜索过程（搜索了哪些关键词、哪些数据库），然后说明"确认无相关论文"。这不影响其他两个通道。论文通道不是必须成功——是必须执行。

**Q: 代理运行太慢怎么办？**
A: 三个代理并行运行（background=true），实际等待时间 = 最慢的那个。5 分钟预算限制。

**Q: 小项目也需要三个代理吗？**
A: 需要。规模不影响搜索——10 行的 CLI 工具和 1000 行的服务器都可能有参考实现和规范。但 P2（测试项目）可以只用 GitHub 通道，跳过 Web 和 Papers。
