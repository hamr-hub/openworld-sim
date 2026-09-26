# REFERENCES — 参考文献与资料

分类整理：论文 / 仓库 / 博客 / 标准。链接尽量指向官方源（论文 DOI / GitHub / 官方文档）。

## A. 学术论文 (peer-reviewed / arXiv)

### Agent 社会仿真
- Park et al., **Generative Agents: Interactive Simulacra of Human Behavior** (2023). <https://arxiv.org/abs/2304.03442>
- Wang et al., **Voyager: An Open-Ended Embodied Agent with Large Language Models** (2023). <https://arxiv.org/abs/2305.16291>
- Mou et al., **AgentSociety: A Social Simulation Framework for LLM Agents** (Tsinghua, 2024). <https://github.com/tsinghua-fib-lab/AgentSociety>
- Pateria et al., **Hierarchical Reinforcement Learning: A Comprehensive Survey** (ACM CSur, 2021). <https://dl.acm.org/doi/10.1145/3453160>
- Hutsebaut-Buysse et al., **Hierarchical Reinforcement Learning: A Survey and Open Research Challenges** (MDPI MAKE, 2022). <https://doi.org/10.3390/MAKE4010009>

### Agent 记忆与反思
- Zhong et al., **MemoryBank: Enhancing Large Language Models with Long-Term Memory** (2024). <https://arxiv.org/abs/2403.07920>
- Weng et al., **A-MEM: Agentic Memory for LLM Agents** (2025). <https://arxiv.org/abs/2502.12110>
- Fang et al., **Memp: Exploring Agent Procedural Memory** (2025). <https://arxiv.org/abs/2508.06433>
- Shinn et al., **Reflexion: Language Agents with Verbal Reinforcement Learning** (NeurIPS 2023). <https://arxiv.org/abs/2303.11366>
- Yao et al., **ReAct: Synergizing Reasoning and Acting in Language Models** (ICLR 2023). <https://arxiv.org/abs/2210.03629>

### BDI 与 agent 架构
- Rao & Georgeff, **Modeling Rational Agents within a BDI-Architecture** (KR'91). <https://www.cs.utexas.edu/~ratha/courses/cs394R-fall2012/rao91modeling.pdf>
- Rao & Georgeff, **BDI Agents: From Theory to Practice** (ICMAS'95). <https://www.aaai.org/Papers/ICMAS/1995/ICMAS95-042.pdf>
- Sutton, Precup & Singh, **Options framework** (AIJ 1999). <https://www-anw.cs.umass.edu/~barto/courses/cs687/Sutton-Precup-Singh-AIJ99.pdf>

### Needs-based & Drive-based AI
- Zubek, **Needs-Based AI** (2009 draft). <http://robert.zubek.net/publications/Needs-based-AI-draft.pdf>
- **Drive-Based Behavior Modeling for Emotionally Responsive NPCs** (SBGames 2025). <https://sol.sbc.org.br/index.php/sbgames/article/view/37378>

### 多智能体仿真与离散事件调度
- **Testing BDI-based multi-agent systems using discrete event simulation** (AAMAS Journal 2026). <https://link.springer.com/article/10.1007/s10458-026-09744-w>
- **Clockwork: A Discrete Event and Agent-Based Social Simulation Framework** (Research Square preprint). <https://dx.doi.org/10.21203/rs.3.rs-3740215/v1>
- **Event-Driven Multi-agent Simulation (famos framework)**. <https://www.researchgate.net/publication/272504010_Event-Driven_Multi-agent_Simulation>
- **When Does Hierarchy Help? DESBench** (arXiv 2605.13172, 2026). <https://ar5iv.arxiv.org/html/2605.13172>

### 神经世界模型
- Decart / ETH, **Oasis: A Real-Time Interactive World Model**. <https://oasis-world.github.io/>
- DeepMind, **Genie 2: A Large-Scale Foundation World Model**. <https://deepmind.google/discover/blog/genie-2-a-large-scale-foundation-world-model/>
- World Labs. <https://www.worldlabs.ai/>

## B. 开源仓库 / 框架

### 多 Agent 仿真
- **AI Town** (a16z-infra). <https://github.com/a16z-infra/ai-town>
- **AgentSociety** (THU FIB-Lab). <https://github.com/tsinghua-fib-lab/AgentSociety>
- **Generative Agents** (Stanford). <https://github.com/joonspk-research/generative_agents>
- **Reflexion**. <https://github.com/noahshinn024/reflexion>
- **Minigrid / BabyAI** (Farama). <https://github.com/Farama-Foundation/Minigrid>
- **PettingZoo** (multi-agent RL envs). <https://github.com/Farama-Foundation/PettingZoo>
- **MPE** (Multi-Particle Environment). <https://github.com/openai/multiagent-emergence-environments>

### Agent 决策框架
- **LangGraph** (LangChain). <https://github.com/langchain-ai/langgraph> · docs: <https://langchain-ai.github.io/langgraph/>
- **AutoGen** (Microsoft). <https://github.com/microsoft/autogen>
- **CrewAI**. <https://github.com/crewAIInc/crewAI>
- **Letta** (MemGPT 续作). <https://github.com/letta-ai/letta>

### LLM Memory
- **LangChain Memory**. <https://python.langchain.com/docs/concepts/memory/>
- **LlamaIndex Memory module**. <https://docs.llamaindex.ai/en/stable/module_concepts/memory/>
- **LlamaIndex Agentic RAG**. <https://docs.llamaindex.ai/en/stable/building_blocks/rag/agentic_rag/>

### 游戏引擎 / 仿真
- **Unity ML-Agents**. <https://github.com/Unity-Technologies/ml-agents>
- **Habitat** (Meta AI). <https://aihabit.org/>
- **AI2-THOR**. <https://ai2thor.allenai.org/>

## C. 经典工程文献

- Fowler, **Event Sourcing** (2005). <https://martinfowler.com/eaaDev/EventSourcing.html>
- Fowler, **CQRS** (2011). <https://martinfowler.com/bliki/CQRS.html>
- **BDI software model** (Wikipedia overview). <https://en.wikipedia.org/wiki/BDI_software_agent>

## D. 工具 / 库文档

- **FastAPI — WebSockets docs**. <https://fastapi.tiangolo.com/advanced/websockets/> · tutorial: <https://fastapi.tiangolo.com/tutorial/websockets/>
- **uvicorn**. <https://www.uvicorn.org/>
- **websockets (Python lib)**. <https://websockets.readthedocs.io/>
- **websocket-client (Python)**. <https://websocket-client.readthedocs.io/>
- **PRAW** (Python Reddit API Wrapper). <https://praw.readthedocs.io/> · async: <https://asyncpraw.readthedocs.io/>
- **Vite — Getting Started**. <https://vite.dev/guide/> · Features: <https://vite.dev/guide/features.html>
- **PixiJS**. <https://pixijs.com/>
- **pytest**. <https://docs.pytest.org/>
- **httpx**. <https://www.python-httpx.org/>

## E. 行业参考 / 博客

- **Anthropic prompt caching** (cost control). <https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching>
- Anthropic / OpenAI pricing pages (2025; 实时参考)

## F. 备注

- LLM cost control 部分（A 节 "LLM 成本控制 / token budgeting"）当前以行业通用做法
  + Anthropic caching 文档为参考；具体经济模型以厂商最新价目为准。
- 链接均为搜索验证过；如发现失效，请在 issue 报告。