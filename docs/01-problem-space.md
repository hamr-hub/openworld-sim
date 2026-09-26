# 01 — 问题定义与设计空间

> *Open-world multi-agent social simulation — what problem are we even solving?*

## 1.1 一句话命题

构造一个 **世界规则持续推演 + Agent 作为一级公民** 的开放游戏世界：
世界有自己稳定运行的内核（时钟 / 状态机 / 因果事件），Agent 不是外挂，
而是世界里**有身体、有需求、必须遵守规则**的公民；任务和剧情从世界状态
**涌现**（emerge），不是脚本表。

## 1.2 三大根本张力

设计开放世界仿真时，三对力量始终拉扯：

| 张力 | 一极 | 另一极 |
| --- | --- | --- |
| **一致性 vs 创造性** | 严格规则世界：每个事件可追溯、可重放（[Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html)） | 神经世界模型：画面与行为涌现（[Genie/Oasis](https://deepmind.google/discover/blog/genie-2-a-large-scale-foundation-world-model/)） |
| **Agent 自主 vs 世界约束** | Agent 可自由表达意图 | Agent 只能提 Intent，世界裁决（[BDI](https://en.wikipedia.org/wiki/BDI_software_agent) 的 *intention* 是受约束的） |
| **任务预编 vs 涌现** | 任务表驱动，编剧可控 | 任务从状态缺口涌现，玩家体验独特（[Generative Agents](https://arxiv.org/abs/2304.03442)） |

任何严肃方案都要在这三对力上**有意识**地落点。

## 1.3 设计空间切分

我们把设计空间切成 6 维，每一维都是一个连续光谱：

1. **世界状态表示** — 离散 (tile/ECS/event log) ↔ 连续 (latent vector / video frame)
2. **时间推进** — fixed tick ↔ event-driven (DES) ↔ continuous real-time
3. **Agent 决策** — 启发式 (hand-coded) ↔ RL ↔ LLM-as-brain ↔ 混合分层
4. **规则执行** — 中央 RuleEngine ↔ Agent 自律 ↔ 分布式共识
5. **任务来源** — 脚本表 ↔ 状态缺口涌现 ↔ 玩家驱动 ↔ 混合
6. **持续推理形态** — 单机 batch ↔ server-resident loop ↔ edge + cloud

## 1.4 "一级公民" 这个词到底在说什么

这是本项目区别于 "LLM-driven NPC" 类玩具的关键。当我们说 **Agent 是一级公民**：

- Agent 有 **位置 / 属性 / 需求 / 目标 / 记忆**，存在于世界状态里
- Agent 有 **私有视角**（observe），但没有 **私有写入**（write）
- Agent 只能 **提交 Intent**（请求），不能直接修改世界
- RuleEngine **仲裁** Intent，产生 Event，Event 改世界
- 世界一致性由 **内核** 保证，不靠 Agent 自觉

这与 [Belief-Desire-Intention (BDI) 架构](https://en.wikipedia.org/wiki/BDI_software_agent)
（Rao & Georgeff, 1991）的"intention 受 belief/世界约束"是同构的。
BDI 是这个设计的理论根基之一。

## 1.5 "涌现" 的最小标准

什么是 *任务涌现*？我们要求满足：

- 任务 **不是脚本预定义**的
- 任务 **产生自世界状态扫描**（need 缺口 / 资源机会 / 关系冲突）
- 任务列表是 **运行时派生** 而非静态配置

可以参考 [Generative Agents 的 emergent social behaviours](https://arxiv.org/abs/2304.03442)：
他们的 agents 自发形成了派对邀请、关系建立等事件，这些事件并非剧本。

## 1.6 非目标

- **不是做通用游戏引擎**（Unity / Unreal 已经做得很好）。
- **不是做神经网络世界模型**（Genie 解决画面一致性，社会一致性需要规则）。
- **不是做 LLM Agent 框架**（LangGraph / AutoGen 解决对话流，世界需要规则内核）。
- **不是做产品**（这是研究 + demo，不是发布版）。

## 1.7 一句话立场

> 我们的立场是 **确定性规则内核 + 事件溯源** 是 Agent 社会仿真的地基；
> LLM 仅作 Agent 决策脑，可插拔；任务从世界状态涌现。
> 这个立场贯穿所有后续文档。

---

继续阅读：[02 — 现有方案全景](02-landscape.md) · [03 — 世界内核](03-world-kernel.md)