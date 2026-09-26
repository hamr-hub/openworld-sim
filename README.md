# OpenWorld Sim — 开放世界多 Agent 社会仿真

> *Open-world multi-agent social simulation — world kernel + agents.*
>
> 世界推演内核是主角；Agent 是有身体、有需求、受规则约束的一级公民；
> 任务从世界状态涌现（emerge），不是脚本表。

## 一句话立场

> **确定性规则内核（事件溯源）+ LLM 仅作 Agent 决策脑**，世界规则层必须自控；
> 神经世界模型解决"画面一致性"但不解决"社会/逻辑一致性"——后者只能靠规则内核。
> 现成框架（AI Town / AgentSociety / LangGraph）可借鉴，世界规则层自控。

## 文档地图

| # | 主题 | 内容 |
| --- | --- | --- |
| [01](docs/01-problem-space.md) | 问题定义与设计空间 | 三大张力 + 6 维设计空间 |
| [02](docs/02-landscape.md) | 现有方案全景 | 学术系统 / Agent 框架 / 神经世界模型 / 游戏引擎 四条路线 |
| [03](docs/03-world-kernel.md) | 世界内核 | 状态 / 时间 / 一致性 / ESAA 事件溯源 |
| [04](docs/04-agent-citizen.md) | Agent 一级公民 | 感知 / 需求 / 记忆 / 规划 / 快慢分层决策 |
| [05](docs/05-task-emergence.md) | 动态任务涌现 | need 缺口 / 资源机会 / 关系机会 |
| [06](docs/06-cloud-inference.md) | 云端持续推理 | tick 调度 / LLM 成本控制 |
| [07](docs/07-visualization.md) | 沙盘可视化 | 实时 canvas + WebSocket |
| [08](docs/08-tech-options.md) | 技术选型对比 | 各模块横向对比 + 推荐 |
| [09](docs/09-research-plan.md) | 研究问题与实验 | 假设 / 度量 / 里程碑 |
| [REFERENCES](docs/REFERENCES.md) | 参考文献 | 论文 / 仓库 / 文档 |

## thin-slice demo 现状

* **后端** (`backend/`)：FastAPI + WebSocket + asyncio tick loop；world kernel =
  event-sourced `WorldState` + `RuleEngine` + `TaskEmergence`；4 个 agent，
  默认启发式策略（`OPENWORLD_LLM=1` 启用 LLM 接口）。
* **前端** (`frontend/`)：Vite + TypeScript + Canvas 2D 极简沙盘，连 WebSocket。
* **离线跑批**：`python -m openworld.headless --ticks N`。
* **测试**：`pytest` 覆盖 RuleEngine / WorldState / TaskEmergence / HTTP API。

## 快速开始

```bash
# 后端 (Python 3.10+)
pip install -e ./backend[test]
pytest -q backend/tests                              # 全绿
python -m openworld.headless --ticks 200             # 离线跑批

# 启服务（默认 8000 端口）
python -m openworld.server                           # 服务端 tick loop + WS
# 或
cd backend && uvicorn openworld.server:app --reload --port 8000

# 前端
cd frontend && npm install && npm run dev            # http://localhost:5173
cd frontend && npm run build                        # 生成 dist/

# 一键脚本
make dev        # 后端 + 前端 dev
make test       # pytest 全绿
make headless   # 跑 200 tick
```

## 一键 Makefile

```bash
make help       # 列出所有目标
make install    # 安装后端 + 前端依赖
make backend    # 跑后端
make frontend   # 跑前端 dev server
make build      # 前端 build
make test       # pytest
make headless   # headless 跑批
```

## 项目结构

```
openworld-sim/
├── docs/                          # 方案研究文档（10 份）
├── backend/
│   ├── openworld/                 # 核心包
│   │   ├── clock.py               # tick
│   │   ├── events.py              # Intent + Event + EventBus
│   │   ├── world_state.py         # 事件溯源状态
│   │   ├── rule_engine.py         # Intent 仲裁
│   │   ├── agents.py              # Agent 注册
│   │   ├── policies.py            # Heuristic / LLM Policy
│   │   ├── task_emergence.py      # 任务涌现
│   │   ├── simulator.py           # tick 编排
│   │   ├── server.py              # FastAPI + WebSocket
│   │   └── headless.py            # CLI 跑批
│   ├── tests/                     # pytest
│   └── pyproject.toml
├── frontend/
│   ├── src/                       # Vite + TS
│   ├── package.json
│   └── vite.config.ts
├── Makefile
├── LICENSE (MIT)
└── README.md
```

## 涌现事件示例（启发式策略，200 tick）

```
task.emerged           715    # 任务从状态涌现
task.claimed           641    # Agent 主动认领
agent.moved            361    # 移动
agent.spoke            128    # 社交对话
trade.completed         12    # 物品交换（合作）
agent.gathered           6    # 资源采集
agent.consumed           8    # 消费（need 下降）
```

LLM 启用后会显著提升 agent.spoke 与 trade.completed 数量
（见 [docs/09-research-plan.md](docs/09-research-plan.md) 实验 2）。

## 许可

MIT — 见 [LICENSE](LICENSE)。