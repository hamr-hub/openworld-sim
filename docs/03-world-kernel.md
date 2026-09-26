# 03 — 世界内核：状态、时间、一致性

> *World kernel is the protagonist.  It ticks.  It arbitrates.  It remembers.*

世界内核（world kernel）是开放世界仿真的核心抽象。本文档整理
**状态表示 / 时间推进 / 一致性 / 事件溯源** 四个子问题，给出本项目的选择。

## 3.1 状态表示

### 候选
1. **离散符号状态**（grid / ECS / entity-component）：本项目选择这个。
2. **连续潜空间**（神经世界模型 latent）：渲染一致性好，社会一致性差。
3. **混合**（符号 + 神经渲染）：未来方向。

### 我们为什么选离散符号
- **可序列化**：直接 JSON 化，前端好渲染、好调试、好持久化。
- **可重放**：event log 重放得到状态。
- **可校验**：每个状态迁移都能写测试。
- **资源友好**：7GB Jetson 也能跑。

### 我们的具体模型
参考 [Sutton & Precup 1999 (Options)](https://www-anw.cs.umass.edu/~barto/courses/cs687/Sutton-Precup-Singh-AIJ99.pdf)
和 [Unity DOTS / Unreal Mass](https://docs.unrealengine.com/) 的 ECS 思路，
把世界切为：
- **Tile**：网格最小单位，类型（ground/water/wall），可附资源（wood/ore/food）。
- **AgentRecord**：agent_id / name / pos / inventory / needs / goals / memory_short / relationships。
- **TaskRecord**：task_id / kind / pos / status / claimed_by / reward。
- **EventLog**：append-only 事件流（真理之源）。

## 3.2 时间推进

### 候选
1. **Fixed tick**：每个 tick 推进一帧（[Minigrid](https://github.com/Farama-Foundation/Minigrid)、本项目）。
2. **Discrete Event Simulation (DES)**：跳到下一个有事件的时间点（[Alchemist](https://alchemistsimulator.github.io/)）。
3. **Continuous real-time**：浏览器 `requestAnimationFrame`，tick 间隔 ms 级（AI Town）。

### 我们为什么选 fixed tick
- **可解释**：tick N 状态就是事件 N 的 fold，易讲清楚。
- **可重放**：固定 tick 数 = 固定事件流 = 固定结果。
- **可观察**：每 tick 发 snapshot 给前端，UI 自然同步。
- **成本可控**：tick 频率是单一参数（`OPENWORLD_TICK_MS`，默认 800ms）。

### 与 DES 的关系
DES 在 agent 稀疏事件时更省算力——open-world sim 适合 fixed tick，因为
agent 数量稳定且每个 tick 都有事可做。生产系统可以扩展为 DES（按需"加速"
无事件 ticks）。

## 3.3 一致性（consistency）

### 定义
任何时刻，世界状态必须满足：
1. **空间**：每个 agent 占据恰好一格，没有重叠（除非 multi-tile entity）。
2. **资源守恒**：gather 一定对应 tile.amount 减少；trade 双方物品守恒。
3. **因果**：每个 Event 必须可追溯到一个 Intent（或世界自发事件）。
4. **逻辑**：speak 不能给自己塞 inventory；trade 双方必须都拥有相应物品。

### 实现方式
- 空间：RuleEngine 检查目标格是否被占用（contested moves = conflict.broke）。
- 资源守恒：gather/trade 是 Event 间 *代数等式*，有测试覆盖。
- 因果：每 Event 带 `caused_by: intent_id`，全链路可审计。
- 逻辑：每种 action 一个 `_rule_*` 方法，类型化校验。

### 一致性故障的兜底
如果发现 invariant 破缺（例如负 inventory），世界进入 `quarantine`：
停止向前推进，记日志，保留最后 100 tick 给运维排错。
（本项目 thin-slice 不带强制 1;但 RuleEngine 拒绝任何越界 Intent，本身就难以破缺。）

## 3.4 事件溯源（Event Sourcing, ES）

### 思想
参考 Martin Fowler 的 [EventSourcing](https://martinfowler.com/eaaDev/EventSourcing.html)：
**状态 = reduce(apply_event, initial, log)**。

```
state_t = fold(events_0 ... events_t)
```

这给我们：
- **可重放**：从日志任意前缀恢复任意时刻状态。
- **可审计**：每件事都有 event_id + caused_by。
- **可分析**：把 event log 当 query 源，做离线统计 / 训练数据。
- **可调试**：headless 跑批后重放任一 tick 到前端。

### 我们的 Event 设计
```python
@dataclass
class Event:
    kind: str                 # "agent.moved" / "trade.completed" / "task.emerged" / ...
    payload: Dict[str, Any]   # event-specific data
    tick: int                 # world tick
    caused_by: Optional[str]  # intent_id (for causal traceability)
    event_id: str             # unique id
    timestamp: float          # wall-clock
```

### 我们的 Intent 设计
```python
@dataclass
class Intent:
    agent_id: str
    action: str               # "move" / "speak" / "gather" / "trade" / "claim"
    target: Optional[str]
    payload: Dict[str, Any]
    tick: int
    intent_id: str
```

Intent 是请求；Event 是事实。RuleEngine 把 Intent 转成 Event（或拒绝）。
**这是 Agent 与世界的 seam：Agent 永远无法跳过它。**

### 关联架构：ESAA / CQRS
本项目结构与 **ES + CQRS**（[Greg Young 起源](https://martinfowler.com/bliki/CQRS.html)）
的精神一致：
- 写入模型（write）：Intent → Event
- 读取模型（read）：snapshot（WorldState.snapshot()）
- 二者通过 EventLog 一致化。

我们没有严格区分读写模型（snapshot 是 state 的 JSON 序列化），但概念上是一致的。

## 3.5 与其他世界模型的差异

| 系统 | 状态表示 | 时间推进 | 一致性机制 |
| --- | --- | --- | --- |
| Generative Agents | 像素 + LLM 记忆 | tick | 无规则 |
| Oasis | transformer latent | continuous | 无（神经） |
| Minigrid | grid + obj | tick | 物理环境硬编码 |
| **本项目** | **grid + ECS + event log** | **fixed tick** | **RuleEngine + ES** |

## 3.6 一句话结论

> **状态用离散符号 + event log；时间用 fixed tick；
> 一致性由 RuleEngine 强制，invariant 测试覆盖；
> Agent 只能通过 Intent 与世界交互，无法绕过。**

---

继续阅读：[02-landscape](02-landscape.md) · [04-agent-citizen](04-agent-citizen.md)