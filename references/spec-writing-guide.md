# 形式化规格编写方法

> [来源: voip-calc-core/SPEC.md — 形式化契约: 前置条件/后置条件/不变量]
> [来源: Red Hat 2026 — Spec Coding: 5维度规格 (目标/边界/设计决策/接口契约/测试场景)]
> [来源: forztf/skilled-spec-cn — EARS需求格式]

## 规格应包含的5个维度

| 维度 | 内容 | 缺失的后果 |
|------|------|-----------|
| 目标 | 解决什么问题，成功标准是什么 | 不知道什么时候算做完 |
| 边界 | 范围内/范围外，非功能性约束 | 范围蔓延，盲目造轮子 |
| 设计决策 | 关键选择+理由（引用ADR） | 后人不知道为什么这样设计 |
| 接口契约 | 前置条件/后置条件/不变量 | 测试无法推导 |
| 测试场景 | 正常路径/异常路径/边界 | 测试覆盖不完整 |

## 记法约定

使用数学记法描述核心逻辑，确保实现和规格之间可验证：

| 符号 | 含义 |
|------|------|
| $R_{base}(cc)$ | 国家码 `cc` 的基础费率 |
| $D(tier)$ | 客户等级折扣因子 |
| $C(t, cc, tier, d, b)$ | 总话费 |
| $\lceil x \rceil$ | 向上取整 |

## 函数规格格式

每个公共函数定义：

```
函数名(参数)
  前置: 输入约束（类型/范围/业务规则）
  后置: 输出保证（返回值/副作用/异常）
  异常: 什么情况下抛什么异常
  幂等: 是否幂等（如适用）
```

### 示例

```
Money(amount, currency)
  前置: amount 为 Decimal 或可安全转换为 Decimal 的类型
        若 amount 为 float，走 Decimal(str(amount)) 间接转换
  后置: self.amount 始终为 Decimal 类型
        self.currency 不变

money * scalar
  前置: scalar ∈ {Decimal, int, float}
        若 scalar 为 float: scalar → Decimal(str(scalar))  (IEEE 754 防御)
  后置: result.amount == self.amount * scalar_as_Decimal
        result.currency == self.currency
```

## 测试场景推导规则

每个函数规格条款 → 推导测试场景：

| 规格条款 | 测试场景类型 | 示例 |
|---------|-------------|------|
| 正常路径 | Happy path | 标准输入→期望输出 |
| 边界 | 最小值/最大值 | 零值、空值、极限值 |
| 异常 | 错误输入 | 类型错误、范围越界、币种不一致 |
| 不变式 | 状态不变 | 操作前后不变的关系 |

## 使用模板

详见 [templates/spec-template.md](../templates/spec-template.md)
