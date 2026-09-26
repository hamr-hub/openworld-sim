# 09 — 研究问题与实验计划

> *What we want to find out, and how we'll know if we did.*

## 9.1 核心研究问题

**RQ1**：*确定性规则内核 + LLM Agent 决策脑* 的混合架构，能否在
保持世界一致性的同时，产生可被人类评估为"涌现"的社会行为？

**RQ2**：在缺乏 LLM 的纯启发式策略下，是否仍能产生可观察的涌现行为
（任务涌现 / 关系涌现 / 冲突涌现）？LLM 加成到底在哪一层最值钱？

**RQ3**：持续推理（continuous inference）的 token 成本墙如何破？
分层调用 / 批处理 / 小大模型混合的实际收益是多少？

**RQ4**：事件溯源 + RuleEngine 的世界内核是否能替代游戏引擎的物理系统
用于 *社会* 仿真？（与 RQ1 是反面问题）

## 9.2 可证伪假设

| ID | 假设 | 拒绝标准 |
| --- | --- | --- |
| H1 | 在 12×12 grid / 4 agents / 200 ticks 的设置下，能观察到 ≥3 类涌现事件 | task.emerged / trade.completed / conflict.broke 中有 < 3 类 > 0 |
| H2 | 启发式策略能让 agents 形成 ≥1 个持续关系（多 tick 多次 trade） | 200 tick 内 trade.completed = 0 |
| H3 | 任务涌现数 ≥ 1.0 per tick per agent | 实际 < 0.3 |
| H4 | RuleEngine 能 100% 拒绝越界 Intent（out-of-bounds / 缺物品） | 接受 ≥ 1 个越界 |
| H5 | WebSocket snapshot 在 4 subscriber 下延迟 < 1s | 任意 tick 延迟 > 1s |

每个假设对应 `backend/tests/test_*.py` 中至少 1 个测试。

## 9.3 实验设计

### 实验 1: Emergence baseline（启发式）
- 设置：12×12 grid, 4 agents, 200 ticks, seed=42。
- 度量：event_kinds() 中非零类别数、trade.completed 数、task.emerged 数。
- 当前结果：见 `headless` 输出 — 已观察到 task.emerged/claimed/moved/spoke/trade/gather/consumed/registered/init。
- 验证：见 [backend/tests/test_emergence.py](../backend/tests/test_emergence.py)（thin-slice）。

### 实验 2: LLM on / off 对比
- 设置：A 组 HeuristicPolicy；B 组 LLMPolicy（需要 OPENWORLD_LLM=1 + key）。
- 度量：emergence 行为数量、agent 关系网络密度、任务完成率。
- 假说：LLM 组在 *关系网络密度* 上显著高于启发式组；在 *任务完成率* 上接近。

### 实验 3: Tick 频率成本
- 设置：100 / 500 / 1000 / 2000 ms tick 间隔，各跑 1 hour 等价 ticks。
- 度量：LLM 调用次数（设 OPENWORLD_LLM=1）、总 token、emergence 行为密度。
- 假说：emergence 行为密度与 tick 频率呈 *亚线性* — 高频 tick 边际收益递减。

### 实验 4: 规模扫 (scaling sweep)
- 设置：agent_count ∈ {4, 16, 64, 256}, grid 自适应。
- 度量：每 tick CPU 时间、emergence 行为数、RuleEngine 拒绝率。
- 假说：拒绝率随 agent 数上升（资源稀缺）— 涌现 *冲突* 增加。

### 实验 5: 持久化回放
- 设置：跑 1000 tick → 落盘 event log → 从 log 重放 → 验证 state 与 replay 一致。
- 度量：state diff 必须 = 0。

## 9.4 度量指标

### 涌现质量
- **emergence diversity**：每 run 中 event_kinds 非零类别数（thin-slice 目标 ≥ 6）。
- **emergence density**：每 tick 每 agent 涌现事件数。
- **task completion rate**：done / (open + done)。

### 关系涌现
- **affinity network density**：graph(|relationships| > 0) / C(n,2)。
- **reciprocal trades**：双向 trade 数。

### 性能
- **tick latency**：simulator.step() 平均时间。
- **ws broadcast latency**：snapshot 从 step 到 client 的时延。
- **rejection rate**：intent.rejected / total intents。

## 9.5 里程碑

| 阶段 | 内容 | 验收 |
| --- | --- | --- |
| M0 (done) | thin-slice: 12×12 / 4 agents / heuristic / FastAPI + WS + Vite | headless 出 emergence; pytest 全绿 |
| M1 | 落盘 (SQLite event log) + replay API | replay state diff = 0 |
| M2 | LLMPolicy 真接 OpenAI / Anthropic | 实验 2 跑完，对比表 |
| M3 | 任务维度扩展（rest / craft / explore / mediate）| emergence diversity ≥ 8 |
| M4 | 场景化：稀缺资源 / 灾变 / 节日 | 涌现 *冲突* 显著增加 |
| M5 | 多 sim 联邦（多 server 同步 tick） | 实验 5 联邦版 |

## 9.6 风险与开放问题

- **LLM 成本** 见 [06-cloud-inference](06-cloud-inference.md)；M2 必须先解决分层成本。
- **涌现 ≠ 有趣**：emergence diversity 高不代表游戏好玩；M4 需要 UX 评估。
- **跨语言**：thin-slice 是中文 / 英文混排，LLM prompt 需要双语能力。

## 9.7 一句话结论

> **5 个实验 + 5 个里程碑**：
> 启发式 baseline → LLM 对比 → 频率成本 → 规模扫 → 持久化回放。
> H1-H5 五个可证伪假设都在 pytest 里有对应测试。

---

继续阅读：[08-tech-options](08-tech-options.md) · [REFERENCES](REFERENCES.md)