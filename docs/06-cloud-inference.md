# 06 — 云端持续推理与成本控制

> *The simulator is resident.  LLM is pluggable.  Token cost is the wall.*

## 6.1 持续推理的形态

参考 [AI Town](https://github.com/a16z-infra/ai-town) 的部署形态，
持续推理 (continuous inference) 系统有三种部署：

| 形态 | 描述 | 适用 |
| --- | --- | --- |
| **Browser-resident** | 前端 SPA，每 tick 调 LLM API | 客户端玩、零运维 |
| **Server-resident** | 后端 long-running 服务，tick 推进 | 多用户、可持久化 |
| **Edge-resident** | 设备端推理（小模型） | 离线 / 隐私 / Jetson |

本项目采用 **server-resident** + 可选 edge fallback：

```
Browser ── WebSocket ──> FastAPI Server ── tick loop ──> Simulator (Kernel)
                                       └─ optional LLM call (per agent per tick)
```

## 6.2 tick 调度

```python
# backend/openworld/server.py
async def _drive_loop():
    interval = OPENWORLD_TICK_MS / 1000  # default 800ms
    while True:
        await asyncio.sleep(interval)
        events = _simulator.step()
        snapshot = _simulator.state.snapshot()
        await _broadcast({"type": "tick", "snapshot": snapshot, "events": events[-20:]})
```

- 单进程 asyncio；simulator 是同步的，事件循环跑 tick。
- 多个 WebSocket subscriber 并行接收 snapshot。
- tick ms 可配（环境变量 `OPENWORLD_TICK_MS`）。

### 为什么不用线程
同步 simulator + asyncio 广播已经够用；多线程会引入 race condition。
WorldState 不是 thread-safe 的。

## 6.3 LLM 调用的成本墙

LLM 决策不是免费的。粗略算账（用 GPT-4o 级别，2024-2025 价格）：

- 1 个 agent decision ≈ 1 个 prompt (1k tokens in) + 1 completion (0.3k tokens out)
- 1 tick = 4 agents = 4 calls = ~5k tokens ≈ $0.015 (gpt-4o, 2025)
- 1 hour @ 1 tick/s = 3600 ticks × $0.015 = **$54/hour per agent 群**

100 个 agent × 1 小时 ≈ $5400。这是个真问题。

### 成本控制 4 法

#### 1. **分层调用**（coarse-to-fine）
- Reactive 层：每 tick 启发式，**0 token**。
- Deliberative 层：每 N tick 或按需 LLM。
- Reflective 层：每 50 tick LLM 反思一次。

#### 2. **请求合并 / 批处理**
- 同 tick 内多个 agent 的 decision 合并成 1 次 LLM 调用（多 agent roleplay prompt）。
- 服务端缓存：相同 observation 的 decision 复用结果。

#### 3. **小模型 + 大模型混合**
- 日常用 7B 本地模型（llama / qwen）做 reactive 层。
- 关键决策（关系 / 计划）才升级到大模型。

#### 4. **tick 频率自适应**
- agent 数量少时降低 tick 频率（节约每 tick 的固定开销）。
- agent "low-attention" 时（无紧急 need）允许慢 tick。
- 系统 busy 时降级到本地小模型。

## 6.4 持续推理的工程要求

### 持久化
- **event log 必须落盘**（推荐 append-only JSONL / SQLite）。
- 进程崩溃可从最近 checkpoint + log replay 恢复。
- thin-slice 不实现落盘；研究版本用 SQLite。

### 观测
- 每 tick 产出的 event 数 / 任务数 / LLM call 次数 必须可监控。
- 推荐接入 OpenTelemetry，把 tick 视为 span。
- 前端通过 `/stats` endpoint 看实时统计。

### 限流
- 单 tick 内 LLM call 数量限制（默认 ≤ agent_count）。
- 429 / network error 时 policy 回退到启发式（**永远不能让世界停摆**）。

## 6.5 离线 vs 在线模式

### 在线（默认）
- FastAPI 服务常驻；WebSocket 广播。
- `OPENWORLD_LLM=1` + API key → LLMPolicy。
- `OPENWORLD_LLM=0` → HeuristicPolicy（默认）。

### 离线（CI / 笔记本）
- `python -m openworld.headless --ticks N --json`
- 不启服务；纯批跑；统计输出。
- 永远不调 LLM（除非显式 opt-in）。

### 端侧（7GB Jetson）
- 禁用 LLM（`OPENWORLD_LLM=0`）。
- 用最小 FastAPI 或纯 asyncio。
- 网格缩到 12×12，agent 4 个。

## 6.6 与 [DESBench](https://ar5iv.arxiv.org/html/2605.13172) 等研究的关联

DESBench（2026 arXiv）研究 hierarchical / heterarchical agent 协调在
discrete-event scheduler 上的表现。我们的 fixed tick 实际上是更简单的 scheduler。
未来工作：把 simulator 抽象成 discrete-event 时钟（按需跳到下一事件），
适合 agent 稀疏事件的规模。

## 6.7 一句话结论

> **持续推理 = server-resident tick loop + WebSocket fan-out**。
> LLM 调用有 4 道成本控制（分层 / 批 / 小大混合 / 频率自适应）。
> 离线 / Jetson 永远能跑（启发式回退）。
> 落盘 / 观测 / 限流是生产工程必修课。

---

继续阅读：[05-task-emergence](05-task-emergence.md) · [07-visualization](07-visualization.md)