# 07 — 沙盘可视化

> *The world must be visible.  A live canvas that mirrors the kernel.*

## 7.1 设计原则

参考 [AI Town](https://github.com/a16z-infra/ai-town) 的前端做法 + [PixiJS](https://pixijs.com/) /
[Konva](https://konvajs.org/) / [Three.js](https://threejs.org/) 的能力对比，
我们确定 4 条原则：

1. **只读视图**：前端从不修改世界状态，所有变更通过 WebSocket /snapshot 推送。
2. **零状态**（尽量）：前端只缓存最近 N tick 的快照用于动画过渡。
3. **符号 → 像素**：网格 + emoji / 色块 即可表达 tile / agent / task。
4. **低带宽**：snapshot 增量推送，事件流分页。

## 7.2 选型对比

| 方案 | 上手成本 | 性能 | 适合规模 | 备注 |
| --- | --- | --- | --- | --- |
| 原生 DOM + Canvas | 低 | 中 | ≤ 10k 实体 | 本项目 thin-slice 用这个 |
| PixiJS | 中 | 高 | ≤ 100k 实体 | AI Town 用 |
| Three.js (3D) | 中 | 中 | ≤ 50k | 需要 3D 模型 |
| deck.gl | 高 | 极高 | ≥ 100k | 地理可视化 |
| React + SVG | 低 | 低 | demo | 不推荐生产 |

thin-slice 选择 **原生 TS + Canvas 2D + WebSocket**。
理由：12×12 grid + 4 agents = ~144 实体，DOM + Canvas 完全胜任。

## 7.3 视图层结构

```
┌─────────────────────────────────────────────────────┐
│ World View                  │  Side Panel           │
│  ┌──────────────────────┐   │  ┌─────────────────┐  │
│  │ 12×12 grid (Canvas)  │   │  │ Agent list      │  │
│  │ ░░░░░░░░░░░░         │   │  │  - Alice        │  │
│  │ ░░A░░░░░░░░░         │   │  │  - Bob          │  │
│  │ ░░░░T░░░░░░░         │   │  │  - ...          │  │
│  │ ░░░░░░░░░░░░         │   │  ├─────────────────┤  │
│  │ ...                  │   │  │ Task queue      │  │
│  └──────────────────────┘   │  │  - gather wood  │  │
│                             │  │  - trade ...    │  │
│                             │  ├─────────────────┤  │
│                             │  │ Event stream    │  │
│                             │  │  t14 trade.com  │  │
│                             │  │  t13 agent.moved│  │
│                             │  └─────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## 7.4 视觉编码

### Tile
- ground: 浅灰 `#e8e6e1`
- wall: 深灰 `#3a3a3a`
- water: 浅蓝 `#9bc4e2`
- 资源叠加：彩色小圆点（food=红、wood=绿、ore=橙）

### Agent
- 头部 emoji（首字母大写）：A / B / C / D
- 边框颜色：inv 满 = 金、inv 空 = 灰
- 名字悬停 tooltip

### Task
- task.emerged 目标格显示标记图标：gather=⛏、trade=⇄
- claimed 变暗

### Event 流
- 颜色按 kind：move=蓝、trade=金、conflict=红、emerged=紫
- 只显示最近 50 条

## 7.5 实时同步

### WebSocket 协议
```json
// server -> client (每 tick)
{
  "type": "tick",
  "snapshot": { "tick": 42, "agents": [...], "tasks": [...], "width": 12, "height": 12 },
  "events":   [ {"kind": "trade.completed", "payload": {...}, "tick": 42}, ... ]
}

// server -> client (首次连接)
{ "type": "hello", "snapshot": {...} }
```

### 前端策略
- 每 tick 收到 snapshot → 替换整个渲染（12×12 太小，没必要 diff）。
- 收到 events → prepend 到事件流列表（保留最近 50）。
- 没有事件流时显示 "idle"。

## 7.6 性能考虑

- 12×12 = 144 cells，agent ≤ 12，每 tick 重画 ≈ 1ms（Canvas）。
- 大规模（>100 agents）需要：sprite batching、脏区域重画、空间索引。

## 7.7 进阶方向

- **世界时间线 scrub bar**：拖动回看任意 tick。
- **agent inspector**：点 agent 看 inventory / needs / memory。
- **task inspector**：点 task 看 reward / 关联 event。
- **diff view**：两个 tick 之间状态对比。
- **多视图**：2D 平面 + 3D 透视；可在 VR 中漫步（[Habitat](https://aihabit.org/) 风格）。

## 7.8 与神经渲染的混合

未来：tile 还是符号（保持可调试），但 **远景 / 视觉氛围** 用神经模型渲染
（参见 [Oasis](https://oasis-world.github.io/) / [Genie 2](https://deepmind.google/discover/blog/genie-2-a-large-scale-foundation-world-model/)），
前端是 hybrid canvas + image-paint layer。thin-slice 不做。

## 7.9 一句话结论

> **Canvas 2D + WebSocket + 零状态前端**。
> 只读视图；增量推送；符号编码；
> 当前规模（12×12 grid / 4 agents）零依赖即可。

---

继续阅读：[06-cloud-inference](06-cloud-inference.md) · [08-tech-options](08-tech-options.md)