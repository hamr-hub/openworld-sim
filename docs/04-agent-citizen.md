# 04 — Agent 作为一级公民

> *Agents are not external scripts.  They perceive, decide, and submit Intent — but the world arbitrates.*

## 4.1 一句话定位

Agent 是世界中的 **一级公民**：
有身体（位置）、有需求（hunger/social/energy）、有记忆（短/长/反思）、有目标（goals），
观察世界，提交 **Intent**，由 RuleEngine 裁决。整个过程 LLM 可作为决策脑，但
**不能跳过 RuleEngine 直写世界**。

## 4.2 感知（Observation）

### 范围
Agent 默认拿到自己的 *局部视野*：
- 自身状态（pos / inventory / needs / goals / memory_short[-5:]）
- 同胞 Agent（其他 agent 的名字、pos）
- 视野内 tile（3×3 / 5×5）
- 视野内 open tasks
- 视野内最近 N 条 events（按相关性过滤）

### 注意：感知 ≠ 写入
Agent 看见世界但不拥有世界。LLM prompt 把这些信息塞进去，
LLM 输出 *proposed intent*，再通过 Policy 接口提交给 simulator。

## 4.3 决策循环（observe → decide → act）

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────────┐
│  observe    │ -> │  decide      │ -> │  submit      │ -> │  world      │
│  (snapshot) │    │  (LLM/heur)  │    │  Intent(s)   │    │  arbitrates │
└─────────────┘    └──────────────┘    └──────────────┘    └─────────────┘
                                                                  │
                              observe (next tick) ◄────────────────┘
```

每一 tick 闭环一次。

## 4.4 决策的分层：快 / 慢

参考 [Hierarchical Reinforcement Learning](https://dl.acm.org/doi/10.1145/3453160)
与 [Reflexion / ReAct](https://arxiv.org/abs/2210.03629)，我们把 Agent 决策分层：

| 层 | 频率 | 触发 | 实现 |
| --- | --- | --- | --- |
| **Reactive (快)** | 每 tick | 反射式行为（avoid danger / claim task / move random） | HeuristicPolicy |
| **Deliberative (慢)** | 每 N tick 或按需 | 计划、反思、关系管理 | LLM Policy（可选） |
| **Reflective (反思)** | 罕见 | 总结经验、改写长期记忆 | LLM Policy（可选） |

**关键设计**：快层必须可在没有 LLM 的情况下完整跑通——
这是 7GB Jetson / 离线 / 单元测试的前提。

## 4.5 记忆

参考 [Generative Agents 的 memory stream](https://arxiv.org/abs/2304.03442) 与
[MemoryBank](https://arxiv.org/abs/2403.07920) / [A-MEM](https://arxiv.org/abs/2502.12110)：

- **memory_short**（长度 ≤ 10）：最近的事件摘要，per-tick 更新。
- **memory_long**（按相关性检索）：重要性高的记忆持久化。
  thin-slice 不实现（用 Vec + 简单 tag 过滤），但接口预留。
- **reflective**：周期性把 short 压缩成 summary，作为新的 long entry。

LLM-based reflection prompt 模板（thin-slice 暂不接 LLM）：
```
You are {name}.  Recent memories: {short}.  Long-term memories: {long}.
Goals: {goals}.  Needs: {needs}.
What is the highest-priority goal right now, and what single next action
should you take (move, speak, gather, consume, trade, claim)?
Output JSON: {"intents": [...]}.
```

## 4.6 需求（Needs）

参考 [Robert Zubek — Needs-Based AI](http://robert.zubek.net/publications/Needs-based-AI-draft.pdf)
和 [BDI architecture](https://en.wikipedia.org/wiki/BDI_software_agent)：

| Need | 驱动 | 解决动作 |
| --- | --- | --- |
| hunger | 随 tick 上升 | gather food → consume |
| thirst | 随 tick 上升 | gather water → consume |
| social | 随 tick 上升 | speak / trade |
| energy | 随 tick 上升 | rest / 减少行动 |

**needs → task.emerged** 是 TaskEmergence 模块的职责（见 05）。
Agent 不能"创造"任务，只能观察 + 完成。

## 4.7 关系（Relationships）

每个 Agent 维护一个 `relationships: Dict[agent_id, affinity]` 映射。
affinity 受事件影响：
- `+0.1` 收到善意的 speak（"help" / "share" / "please"）
- `+0.2` 一次 trade.completed（双向）
- `-0.4` 一次 conflict.broke（双向）

affinity 不直接产生 Event（避免 LLM 自洽循环），
但参与 TaskEmergence（high-affinity pair 更易产生 trade task）。
本项目 thin-slice 实现简单线性更新。

## 4.8 政策（Policy）接口

```python
class Policy(Protocol):
    def decide(self, agent: AgentRecord, state: WorldState, tick: int) -> List[Intent]: ...
```

两个实现：
- **HeuristicPolicy**（默认）：纯 Python、确定性、可单元测试、不需要任何外部服务。
- **LLMPolicy**（可选）：接 OPENAI_API_KEY；thin-slice 是 stub，生产可替换。

环境变量路由：
- `OPENWORLD_LLM=1` 且 `OPENAI_API_KEY` 非空：使用 LLMPolicy。
- 否则：使用 HeuristicPolicy。

LLM 决策的 **成本控制** 是关键问题，见 [06-cloud-inference](06-cloud-inference.md)。

## 4.9 BDI 对应

我们的 Agent 自然对应 [BDI 模型](https://www.aaai.org/Papers/ICMAS/1995/ICMAS95-042.pdf)：
- **Belief**：world.snapshot() ∩ agent.memory
- **Desire**：agent.goals + agent.needs
- **Intention**：policy.decide() 返回的 Intents —— *受 RuleEngine 仲裁*

BDI 是这个分层设计的"老前辈"。

## 4.10 一句话结论

> **Agent = observe + decide + submit Intent**。
> 快层用启发式保证 7GB Jetson 离线能跑；慢层 / 反思层用 LLM，
> 由 `OPENWORLD_LLM=1` 启用。
> 记忆分短/长/反思；需求驱动；关系更新；永远不能跳过 RuleEngine。

---

继续阅读：[03-world-kernel](03-world-kernel.md) · [05-task-emergence](05-task-emergence.md)