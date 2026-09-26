# 05 — 动态任务涌现

> *Tasks are not scripted.  They emerge from state.*

## 5.1 涌现 vs 脚本：本质区别

| 维度 | 脚本表 | 涌现 |
| --- | --- | --- |
| 来源 | 配置 / JSON | 运行时状态扫描 |
| 数量 | 固定 | 动态（bounded） |
| 重复 | 同样任务每次出现 | 取决于状态，独特 |
| 内容 | 静态文本 | 由触发条件生成 |
| 测试 | 测表内容 | 测触发器逻辑 |

我们的立场：**任务从世界状态中派生**。

参考 [Generative Agents](https://arxiv.org/abs/2304.03442) 中
自发形成的派对邀请、关系建立等事件，涌现任务提供：

- **可重玩性**：每次跑批不同，玩家体验独特。
- **可解释性**：任务 ID 反向链接到 world state 快照。
- **可演化**：增加 needs / 增加资源类型 → 涌现更多任务种类。

## 5.2 三类触发器

### A. 需求缺口 (Need Gap)

```python
for agent in state.agents.values():
    for need, level in agent.needs.items():
        if level > need_threshold and not _has_open("need:hunger", agent.pos):
            emit("task.emerged", kind="gather", pos=agent.pos, ...)
```

例子：
- Alice.hunger > 0.6 → task "Alice needs food", kind=gather, pos=Alice.pos。
- Bob.social > 0.6 → task "Bob needs social", kind=trade, pos=Bob.pos。

### B. 资源机会 (Resource Opportunity)

```python
for tile in state.tiles:
    if tile.resource and tile.amount > 0 and not on_tile(agent, tile.pos):
        emit("task.emerged", kind="gather", pos=tile.pos, resource=tile.resource)
```

例子：地图上 (3,3) 有 wood 资源，没有 agent 站在那 → task "gather wood at (3,3)"。

### C. 关系 / 交易机会 (Relation Opportunity)

```python
for (a, b) in pairs(agents):
    if distance(a, b) <= 2 and a.inventory and b.inventory:
        emit("task.emerged", kind="trade", pos=a.pos)
```

例子：Alice 和 Bob 相距 1 步，两人都有 inventory → task "trade between Alice and Bob"。

### 冲突任务 (Conflict Tasks)

未来可加：两个 agent 同时饥饿、抢同一资源 → task "compete for wood at (3,3)"。
本项目 thin-slice 通过 `conflict.broke` 事件隐式表达冲突。

## 5.3 涌现的边界

涌现不是无界。必须做：

### 数量上限
`max_open_tasks = 12`：避免 emergent 任务无限堆积（默认启发式策略 + 4 个 agent
大约 1-3 个 task 同时 open）。

### 去重
同一 `(kind, pos)` 不重复 emit open task。

### 时效
任务有生命周期：
- `open`：可被 claim。
- `claimed`：被某 agent 锁定，其他 agent 不能 claim。
- `done`：completed 的 moment；当前 thin-slice 简化（claimed 即等于完成）。
- `failed`：claim 后未在 5 tick 完成 → 自动回 open。

本项目 thin-slice 实现 open / claimed / done 三态。

## 5.4 Agent 如何与涌现任务交互

Agent 在每 tick `decide` 时可以：

1. **看任务列表**（observe）：取与自己 pos 相近的 open tasks。
2. **claim**：`action=claim, payload={task_id}` → RuleEngine 检查 task 是否仍 open。
3. **执行**：claim 后，policy 根据 task.kind 决定具体行动（gather / trade）。
4. **完成**：rule 拒绝 / tile 耗尽 / trade 完成 → task 自动变 done。

**涌现 ≠ 强制**：Agent 可忽略任务，去做自己的事。这是"自由意志"。

## 5.5 涌现的因果性

每个 `task.emerged` Event 在 log 里：
- 携带 `task_id`（唯一）
- 携带 `pos` / `kind` / `reward`
- **不携带 `caused_by`**（因为它不是某个 Intent 的结果）

这是合理的：涌现任务是 world 自发产生的，不是 agent 申请产生的。
但 task.claimed / task.completed / task.failed 都带 `caused_by`。

## 5.6 测试覆盖

我们的 thin-slice 包含 3 个测试：
- `test_emergence_creates_gather_task_on_resource`：放资源、放 agent，扫描后应有 gather task。
- `test_emergence_creates_need_task_on_high_hunger`：hunger 涨到阈值，应有 need task。
- `test_emergence_respects_max_open_tasks`：放 100 个 need，扫描后 open ≤ max。

详见 [backend/tests/test_task_emergence.py](../backend/tests/test_task_emergence.py)。

## 5.7 一句话结论

> **任务 = world state 派生**，不是脚本表。
> 三类触发器：need gap / resource opportunity / relation opportunity；
> 数量上限防爆；Agent 可自由选择是否完成。
> 这是开放世界"自由感"的来源。

---

继续阅读：[04-agent-citizen](04-agent-citizen.md) · [06-cloud-inference](06-cloud-inference.md)