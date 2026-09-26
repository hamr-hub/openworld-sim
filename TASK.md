# OpenWorld Sim — 项目任务书（给执行 Agent）

你要把本仓库建设成一个**开放世界多 Agent 社会仿真**的「方案研究 + 可运行 demo」开源项目，并完成首次提交与推送。

## 项目核心命题
如何搭建一个由**世界规则持续推演**、**Agent 作为一级公民自主主导**的开放游戏世界：
- 世界推演内核（world kernel）是主角：时钟 tick、确定性世界规则、因果事件、一致性约束。
- Agent 是一级公民：有位置/属性/需求/目标/记忆，走「观察→决策→行动」，但**只能提交 Intent，不能直写世界状态**。
- RuleEngine 裁决 Intent，产生 Event，Event 改变世界；世界一致性由内核保证，不靠 Agent 自觉。
- 动态任务从世界状态涌现（需求缺口 / 冲突 / 机会），不是脚本表。
- 云端持续推理：simulator 常驻；LLM 仅作 Agent 决策脑，可插拔；无 API key 时必须能用内置启发式策略离线跑通。

## 第一部分：方案研究文档库（核心交付，必须扎实、有据）
用 WebSearch/WebFetch 做真实调研（不要编造），产出 docs/ 下：
- 01-problem-space.md 问题定义与设计空间、关键张力
- 02-landscape.md 四条路线全景：学术系统 / 开源框架 / 神经世界模型 / 传统游戏引擎
- 03-world-kernel.md 状态表示、时间推进、一致性、事件溯源（含 ESAA 等）
- 04-agent-citizen.md 感知/需求/记忆/规划、快慢分层决策
- 05-task-emergence.md 需求/冲突/机会 → 任务的模式
- 06-cloud-inference.md tick 调度、持续推理、LLM 成本控制
- 07-visualization.md 世界状态实时沙盘可视化方案
- 08-tech-options.md 各模块现成轮子横向对比表 + 推荐（AgentSociety / AI Town / LangGraph / AutoGen / Generative Agents 等）
- 09-research-plan.md 研究问题、可证伪假设、实验与度量、里程碑
- REFERENCES.md 带链接的参考文献（论文/仓库/博客），分类整理
要求：每个方案写清「解决什么 / 原理 / 优缺点 / 对本项目的可借鉴点」。中英文术语都给。README.md 已存在，按需完善索引和一句话结论。

## 第二部分：可运行 thin-slice demo（基于第一部分推荐选型）
尽量用现成框架，但世界规则层自控。轻量、**禁止重型 ML 依赖 / 禁止下载大模型**（本机是 7GB Jetson，怕 OOM）：
- backend/：Python 3.11，建议 FastAPI + WebSocket。实现 Clock、WorldState（事件溯源，append-only event log）、RuleEngine、EventBus、3~5 个 Agent（默认内置启发式策略；预留 LLM 决策接口，读 OPENWORLD_LLM 环境变量，无 key 自动回退）、TaskEmergence。提供 `python -m openworld.headless --ticks N` 无服务端离线跑批，打印涌现事件统计。
- frontend/：Vite + TypeScript 极简实时沙盘（网格地图 + Agent 点 + 事件流面板），连 WebSocket。`npm run build` 必须通过。
- 测试：backend 用 pytest 覆盖关键规则（Intent 被拒、世界一致性、任务涌现），`pytest` 全绿；记录真实运行输出。
- 根目录提供一键脚本或 Makefile（dev / test / headless）、requirements.txt 或 pyproject、LICENSE(MIT)、.gitignore。

## 第三部分：提交并开源
- 仓库本地路径 ~/codespace/ai/openworld-sim，已 git init（main 分支）。
- 完成后：写清有意义的 commit，然后用 gh 创建 **public** 仓库 `openworld-sim`（owner hamr-hub）并推送。
- gh 已认证（ssh）。不要 push --force。不要改动本目录之外的文件。

## 验收标准（硬）
1. docs/ 十份文档齐全、有真实出处链接，不是空话。
2. `pytest` 真实全绿；headless 跑批有真实输出并确实出现涌现事件（交换/冲突/合作等至少一类）。
3. frontend `npm run build` 真实成功。
4. 成功 push 到 github.com/hamr-hub/openworld-sim 并给出可访问 URL。
完成后在最终回复里报告：文档清单、测试结果、跑批涌现事件摘要、build 结果、远程仓库 URL。任何一项做不到要如实说明，禁止假报。
