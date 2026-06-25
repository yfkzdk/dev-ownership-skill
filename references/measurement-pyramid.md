# 个人测量金字塔 — 工程化测量体系

> 理论基础: GQM (Basili 1994) + EngThrive (Houck 2026) + AI 质量悖论 (2026)
> 适用尺度: 个人开发者（非企业级）
> 状态: v0.2.0 草案

---

## 三层金字塔架构

```
塔尖（战略 — 每个项目结束测）
  ├── 功能模块调用成功率（需求→真实可用）
  ├── 认知债务累积比 CDR / 稳定性比 SR
  └── BDD 触发次数 / 项目

塔中（流程 — 每个阶段出口测）
  ├── 阶段返工次数（spec 修订率、design 推翻率）
  ├── 验证覆盖率 σ(t) = 突变得分×0.6 + (1-AI回滚率)×0.4
  └── commit→测试通过→阶段完成的时间

塔基（代码 — 每次 commit 自动测）
  ├── 静态分析: lint/type/security — 硬阻断
  ├── 测试分层: 单元70% / 集成20% / E2E 10%
  ├── 突变得分 ≥70% — 软警告
  ├── AI 代码回滚率 — 累积追踪
  └── 过滤器链效能: 每层拦截率 × AI负载衰减系数
```

## 核心判定公式

### 1. 验证能力 σ(t) — 个人尺度

```
σ(t) = mutation_score × 0.6 + (1 - ai_rollback_rate) × 0.4

其中:
  mutation_score  = 被杀死的突变体 / 总突变体（mutmut/pit/stryker）
  ai_rollback_rate = AI代码在后续commit中被修改或删除的行数 / AI生成总行数
```

突变得分测量"你的测试有没有真的保护代码"。
回滚率测量"AI 生成的代码有多少你后来改了"——改得越多 = 越不理解 = 验证越弱。

**两个都是客观观测值，不依赖你的主观判断。**

### 2. 冷启动期: 认知债务累积比 CDR（N < 30 commit）

```
CDR = 未经过Feynman门禁验证的AI代码行数 / 当前项目总活动代码行数

门禁: CDR ≤ 0.15（即未验证代码占比 ≤15%，对应 σ₀ ≥ 0.85）
```

小样本时 SR 公式分母易接近零导致发散，CDR 作为过渡代理指标。

### 3. 运行期: 稳定性比 SR（N ≥ 30 commit）

```
SR = 1 / (4 × σ* × (1 - σ*))
σ* = 最近15次commit对应文件在14天观察窗内的closure比例
门禁: SR ≥ 2.4
```

标定参照:
- FastAPI: SR=2.4（盈亏平衡边缘）
- Django: SR=23.0（宽安全冗余）
- Matplotlib: SR=28.1（极宽安全冗余）

### 4. BDD 触发条件 — 个人尺度

```
BDD触发 = 一个功能模块的commit无法完成对应需求
        OR 模块卡住超过阈值时间（尝试多个方案后仍不work）

注意区分: 测试绿了 ≠ 模块真的work。
          以"真实功能调用成功"为判定标准。
```

触发后: 进入 **BDD 响应协议** ([bdd-response-protocol.md](bdd-response-protocol.md))
        诊断→分类处理→重试→升级

### 5. 过滤器链效能衰减

```
Φ = 1 - Π(1 - e_i(v))
e_i(v) = e⁰_i × exp(-α_i × (v - 1))

v = 1.55 (AI辅助开发的生成速率倍数)
γ_AI = 0.0276 (AI代码侵蚀验证能力的速度是人类12倍)
```

### 6. 临界慢化检测 — 个人尺度

```
触发条件（满足任一）:
  - 连续3个commit的SR方向一致下降
  - 14天文件closure比例连续2个观测期下降
  - 单一模块反复返工 ≥3次
```

### 7. 滞后效应与恢复

```
跳过Feynman门禁 → 透支验证配额 → σ(t)下降
恢复条件: 下个项目必须双倍门禁配额补回
         η恢复 ≥ 1.15 × η临界
         强制限制AI代码生成速率直到SR回到2.4以上
```

## 门禁递进机制

### 设计/架构级门禁
- 不可跳过
- 不过 → 不进下一阶段
- 连续2次不过 → 冻结，补学习后再开

### 代码实现级门禁
- 每个项目允许跳过1次（5阶段共5个门禁，配额=1）
- 跳过第2个 → 后续所有阶段冻结
- 跳过的门禁必须在Retrospect之前补完

### 跨项目惩罚
- 跳过的门禁累计到下一个项目的配额
- 例: 项目A跳过5个 → 项目B配额 = 1 - 5 = 负值
  → 项目B零跳过可用 + 必须补完项目A的5个旧门禁

## 指标切换时间线

```
项目开始 ──── N=30 commit ────> 持续运行
   │              │                │
   │ CDR ≤ 0.15   │ 切换到 SR ≥ 2.4│
   │ (冷启动代理)  │ (15-commit滑动窗口)│
   │              │                │
   └─ 每commit ───┴── 每15 commit ──┘
      追踪CDR        追踪SR + σ(t)
```

## 参考来源

- GQM: Basili, Caldiera, Rombach (1994). *The Goal Question Metric Approach.*
- EngThrive: Houck et al. (2026). *EngThrive: Make It Fast and Easy to Do Great Work.* arXiv:2605.04259
- AI 质量悖论: *The AI Quality Paradox: How Code Complexity Drives Rework.* Zenodo, March 2026.
- SPACE: Forsgren et al. (2021). *The SPACE of Developer Productivity.* CACM, 64(6).
