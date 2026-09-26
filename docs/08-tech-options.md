# 08 — 候选技术选型对比与推荐

> *Side-by-side: pick the boring one that fits.*

每个模块都列 2-4 个候选，给出 *集成度 / 学习曲线 / 与本项目契合度 / 推荐度*。
thin-slice 的选择用 **★** 标注。

## 8.1 后端框架

| 框架 | 集成度 | 学习曲线 | 契合度 | 推荐 |
| --- | --- | --- | --- | --- |
| [FastAPI](https://fastapi.tiangolo.com/) + [uvicorn](https://www.uvicorn.org/) | 高（WebSocket + OpenAPI） | 低 | 高 | ★★★ |
| Flask + flask-socketio | 中 | 低 | 中 | ★ |
| Django Channels | 高 | 高 | 中 | ★ |
| aiohttp | 中 | 中 | 中 | ★ |

选 **FastAPI**：自带 WebSocket、async 友好、官方文档详细
（[FastAPI WebSockets docs](https://fastapi.tiangolo.com/advanced/websockets/)）。

## 8.2 WebSocket 服务端

| 库 | 适合 | 推荐 |
| --- | --- | --- |
| FastAPI 内置 | 应用层 | ★★★（thin-slice 用这个） |
| [websockets](https://websockets.readthedocs.io/) | 独立 ws 服务 | ★★ |
| [websocket-client](https://websocket-client.readthedocs.io/) | 客户端 | 不需要 |
| Socket.IO | 浏览器兼容优先 | ★ |

我们用 FastAPI 内置；ws 协议足够简单，不需要 Socket.IO 的回退。

## 8.3 LLM 决策

| 方案 | 离线可跑 | 决策质量 | 推荐 |
| --- | --- | --- | --- |
| 启发式 (HeuristicPolicy) | ✓ | 中 | ★★★（默认） |
| OpenAI API + JSON prompt | × | 高 | ★★（OPENWORLD_OPENAI=1） |
| Anthropic Claude + JSON | × | 高 | ★★ |
| 本地 llama.cpp / ollama | ✓ | 中-高 | ★★（需 GPU） |
| LangGraph + LLM | × | 高 | ★（overkill） |

thin-slice 默认 **HeuristicPolicy**；LLM 接口预留，可插拔。

## 8.4 Agent 决策框架

| 框架 | 适合 | 推荐 |
| --- | --- | --- |
| [LangGraph](https://langchain-ai.github.io/langgraph/) | LLM think-loop 图编排 | ★★（可作 Policy 内部实现） |
| [AutoGen](https://github.com/microsoft/autogen) | 多 Agent 对话 | ★（不强调世界） |
| [CrewAI](https://github.com/crewAIInc/crewAI) | 角色化任务流水线 | ★（不持续） |
| 手写 Policy class | 简单可控 | ★★★（thin-slice 用这个） |

thin-slice 手写 `Policy` 协议 + `HeuristicPolicy` / `LLMPolicy` 两个实现。
理由：thin-slice 只 4 agent，没必要把 LangGraph 拉进来；接口稳定，后续可换。

## 8.5 前端

| 栈 | 上手 | 性能 | 推荐 |
| --- | --- | --- | --- |
| [Vite](https://vite.dev/guide/) + TS + Canvas | 低 | 中-高 | ★★★ |
| Next.js + React + Konva | 中 | 高 | ★★ |
| Vue + PixiJS | 中 | 高 | ★★ |
| Svelte + D3 | 中 | 中 | ★★ |

thin-slice 选 **Vite + TS + 原生 Canvas**。
理由：12×12 grid 不需要 React/Vue；Vite 提供零配置 TS + dev server + build。

## 8.6 持久化

| 方案 | 推荐 |
| --- | --- |
| 无（thin-slice） | ★★★ |
| SQLite（事件日志） | ★★ |
| Postgres + JSONB | ★（生产） |
| DuckDB（分析） | ★（离线分析） |

thin-slice 不落盘；研究版用 SQLite。

## 8.7 可视化细节库

| 库 | 用途 | 推荐 |
| --- | --- | --- |
| 原生 Canvas 2D | 网格 + agent | ★★★（thin-slice） |
| [PixiJS](https://pixijs.com/) | 2D sprite 大场景 | ★★（未来扩展） |
| Konva | 交互 2D | ★ |
| Three.js | 3D | ★（未来） |

## 8.8 测试

| 工具 | 用途 | 推荐 |
| --- | --- | --- |
| [pytest](https://docs.pytest.org/) | Python 测试 | ★★★ |
| [httpx](https://www.python-httpx.org/) + ASGI | FastAPI 测试 | ★★★ |
| Jest / Vitest | 前端测试 | ★（thin-slice 不做） |

thin-slice 只测后端。

## 8.9 横向对比表（汇总）

| 模块 | thin-slice 选择 | 替代 |
| --- | --- | --- |
| 后端 web | FastAPI + uvicorn | aiohttp |
| WebSocket | FastAPI 内置 | websockets |
| LLM | HeuristicPolicy（默认）| OpenAI/Anthropic |
| Agent 框架 | 手写 Policy | LangGraph |
| 前端 | Vite + TS | Next.js |
| 持久化 | 无（thin-slice） | SQLite |
| 测试 | pytest + httpx | unittest |

## 8.10 与流行项目的选型对比

| 项目 | 后端 | 前端 | LLM | 持久化 |
| --- | --- | --- | --- | --- |
| AI Town | Convex (serverless) | PixiJS + TS | OpenAI | Convex DB |
| AgentSociety | 自研 + MQ | React + Ant | OpenAI / Qwen | SQLite / 文件 |
| Generative Agents | Python (research) | React | OpenAI | JSON files |
| **本项目** | **FastAPI** | **Vite + TS + Canvas** | **启发式 / LLM 可选** | **无（thin-slice）** |

## 8.11 一句话结论

> **FastAPI + Vite + 启发式 Policy + 无持久化** 是 thin-slice 的最小可行选型。
> 一切重型依赖（LangGraph / PixiJS / SQLite）都是 *未来可替换* 的接口存在，
> thin-slice 不引入。LLM 接口已预留（OPENWORLD_LLM=1 启用）。

---

继续阅读：[07-visualization](07-visualization.md) · [09-research-plan](09-research-plan.md)