# 02 — 现有方案全景

四条路线全景：学术系统 / 开源框架 / 神经世界模型 / 传统游戏引擎。
每条路线挑出代表性项目，按 *解决什么 / 原理 / 优缺点 / 对本项目的可借鉴点* 拆解。

## 2.1 学术系统（research prototypes）

### [Generative Agents](https://arxiv.org/abs/2304.03442) — Stanford, 2023
- **解决什么**：在一个像素风小镇（Smallville）里放 25 个 LLM Agent，
  观察是否能自发形成社会行为（派对、社交、新八卦）。
- **原理**：每个 Agent 有 *记忆流*（memory stream），LLM 检索相关记忆生成决策；
  决策以 *行动计划* 形式提交到世界引擎执行。
- **优点**：可信地展示了"涌现"的可行性；记忆-反思架构可复用。
- **缺点**：世界引擎是 hand-coded 的对话触发器，**没有规则仲裁层**；
  Agent 可以直接执行任何行动（没有"提交 Intent、被驳回"的语义）。
- **可借鉴**：记忆流结构（短期 / 长期 / 反思）、反思 prompt 模板。

### [AgentSociety](https://github.com/tsinghua-fib-lab/AgentSociety) — Tsinghua THU, 2024+
- **解决什么**：大规模（>10k agents）LLM Agent 城市仿真，研究舆情 / 疫情 / 政策。
- **原理**：基于消息中间件，Agent 通过异步消息通信；LLM 做决策。
- **优点**：真规模跑得动；面向社会科学研究。
- **缺点**：世界规则层薄；规则强耦合到 LLM prompt。
- **可借鉴**：可插拔 LLM 决策层的工程模式。

### [AI Town (a16z)](https://github.com/a16z-infra/ai-town)
- **解决什么**：Generative Agents 的产品化开源版本，玩家可加入。
- **原理**：在 Convex / Fly.io 上做实时 tick；agents 用 LLM 决策；
  前端是 [PixiJS](https://pixijs.com/) 渲染的 2D 小镇。
- **优点**：完整可部署的 thin slice；社区活跃。
- **缺点**：Agent 行为空间有限（移动/对话），没有复杂任务/规则。
- **可借鉴**：**整体技术栈**：LLM + 实时 tick + 像素前端。

### [Voyager](https://arxiv.org/abs/2305.16291) — NVIDIA, 2023
- **解决什么**：Minecraft 中 LLM Agent 终身学习，可解锁技能树。
- **原理**：LLM 提出课程，代码作为技能写入长期记忆，遇到不会的任务就重试。
- **优点**：展示了技能库的可行性。
- **缺点**：Minecraft API 是 Agent 的"自由世界"——没有规则约束；
  长期记忆会无限膨胀。
- **可借鉴**：技能库的概念可对应到我们世界中的 *能力*（gather/trade）。

## 2.2 开源框架（agent frameworks）

### [LangGraph](https://langchain-ai.github.io/langgraph/)
- **解决什么**：把 LLM 应用建模为 *图*（state graph），节点是 LLM/工具调用。
- **原理**：每个节点是一个函数，边是条件分支；状态在节点间流动。
- **优点**：极适合 LLM 决策循环的工程化；可视化、调试、回放都成熟。
- **缺点**：图节点没有"被驳回"的语义——不是世界仿真框架。
- **可借鉴**：把 Agent 内部 think-loop 用 LangGraph 实现，世界层自管。

### [AutoGen](https://github.com/microsoft/autogen) — Microsoft, 2023+
- **解决什么**：多 Agent 对话框架（角色扮演 / 群聊）。
- **原理**：Agent 通过 *消息* 互相调用，可嵌套。
- **优点**：成熟、易上手、对话模式丰富。
- **缺点**：同样没有世界状态 / 规则仲裁概念；Agent 自己改自己的状态。
- **可借鉴**：GroupChat 的角色分工思路。

### [CrewAI](https://github.com/crewAIInc/crewAI)
- **解决什么**：角色化多 Agent 协作（PM / Dev / QA）。
- **原理**：role / goal / backstory，Agent 自动组成"crew"执行 task。
- **优点**：上手快、prompt 模板好。
- **缺点**：定位于"任务流水线"，非"持续世界"。
- **可借鉴**：agent persona 设计模式（role / goal / backstory）。

### [MemGPT / Letta](https://github.com/letta-ai/letta)
- **解决什么**：LLM 长期记忆系统，主内存 + 外部存档分层。
- **原理**：LLM 像 OS 一样自己调度 page-in / page-out。
- **优点**：长期记忆在长任务上明显。
- **缺点**：单一 Agent 视角；不是多 Agent 世界。
- **可借鉴**：记忆分层（short / long / archive）概念。

## 2.3 神经世界模型（neural world models）

### [Oasis](https://oasis-world.github.io/) — Decart / ETH, 2024
- **解决什么**：实时生成式游戏（MineRL 风格）世界，画面是 transformer 实时推理。
- **原理**：transformer 自回归生成下一帧 + 用户输入。
- **优点**：零资产实时生成；画面惊艳。
- **缺点**：**没有逻辑一致性**（物理、规则、因果）；Agent 视角同样不可结构化。
- **可借鉴**：实时 streaming 给前端的技术（diff 渲染）。

### [Genie 2](https://deepmind.google/discover/blog/genie-2-a-large-scale-foundation-world-model/) — DeepMind, 2024
- **解决什么**：从单张图片生成可交互 3D 世界。
- **原理**：大规模视频基础模型 + 动作条件化。
- **优点**：3D 一致性比之前好得多。
- **缺点**：同 Oasis，**社会/逻辑一致性缺位**；不能问"3 号村民现在饥饿值多少"。
- **可借鉴**：理论上 Agent 的"看到的世界"可以是 Genie 渲染的图像，
  但 Agent 决策仍必须基于符号状态。

### [World Labs](https://www.worldlabs.ai/)
- **解决什么**：从单张图片生成可探索 3D 世界。
- **优点**：空间一致性大幅提升。
- **缺点**：依然是 *渲染* 而非 *仿真*；不能内部运行规则。
- **可借鉴**：未来结合方案：神经世界做视觉，符号世界做逻辑。

## 2.4 传统游戏引擎 + AI

### Unity ML-Agents
- **解决什么**：在 Unity 游戏里训练 RL Agent。
- **原理**：GameObject 暴露 sensor / action，RL 训练在外。
- **优点**：成熟的物理 / 渲染 / Asset 生态。
- **缺点**：每局一个 episode，没有"持续世界"概念；Agent 是外部训练的。
- **可借鉴**：sensor 抽象（RayPerception、GridSensor），
  本项目的 Agent 感知层可以借鉴 sensor 设计。

### Unreal Engine Mass AI
- **解决什么**：大规模实体 AI（千人同屏）。
- **原理**：ECS + state tree + crowd。
- **优点**：真能跑 1000+ NPC。
- **缺点**：决策是 FSM / behavior tree，LLM 接入路径不顺。
- **可借鉴**：ECS 是事件溯源的高性能实现参考。

### [Minigrid / BabyAI / MPE](https://github.com/Farama-Foundation/Minigrid)
- **解决什么**：轻量网格世界 RL 基准。
- **原理**：2D 网格 + 部分可观察 + 多 Agent。
- **优点**：极轻、跑得飞快；RL 研究标配。
- **缺点**：环境是静态 / 任务预定义；规则是 RL agent 的 reward。
- **可借鉴**：网格 + 部分可观察的概念，本项目直接用 12×12 grid 起步。

## 2.5 路线对比表

| 路线 | 一致性 | 涌现能力 | 工程门槛 | 成本 | 对本项目可借鉴度 |
| --- | --- | --- | --- | --- | --- |
| 学术系统（Stanford 等） | 中 | 高 | 中 | 中 | 高（架构思想） |
| Agent 框架（LangGraph 等） | 低 | 中 | 低 | 低 | 中（LLM 调用工程） |
| 神经世界模型 | 极低 | 高（视觉） | 高 | 高（GPU） | 低（不能做社会规则） |
| 游戏引擎 | 高（物理） | 低 | 高 | 中 | 中（sensor / ECS） |

## 2.6 一句话结论

> **采用学术系统的"涌现"思想 + Agent 框架的 LLM 集成 + 游戏引擎的事件溯源 / 网格抽象**；
> 不走纯神经路线（与社会规则仿真目标相悖）；不走纯脚本表路线（违反"涌现"原则）。
> 具体选型见 [08-tech-options.md](08-tech-options.md)。

---

继续阅读：[01-problem-space](01-problem-space.md) · [03-world-kernel](03-world-kernel.md)