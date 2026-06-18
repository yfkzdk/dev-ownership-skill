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
  5. AI 合并为 openspec/changes/search-summary.md
  6. AI 基于搜索摘要起草 proposal.md
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
