# 修复任务：打通世界玩法闭环（真机回归暴露的真实缺陷）

上一轮 thin-slice 已推送，但用 `python -m openworld.headless --ticks 100` 真机回归发现玩法闭环是断的，与之前自报不符。实测事件统计：

```
agent.moved 230 | task.emerged 452 | task.claimed 214 | agent.spoke 56
agent.consumed 8 | trade.completed 0 | agent.gathered 0 | intent.rejected 0
completed 0
```

即 Agent 只移动+说话+claim，**从不到资源上采集、不消费、不交易、任务永不完成、需求任务每 tick 重复涌现**。请定位并修复，让世界真正"转"起来。

## 已定位的根因（供参考，需你核对）
1. `openworld/policies.py HeuristicPolicy.decide` 用 `_random_move` 做纯随机游走，没有朝最近资源块的目标导向导航，几乎踩不到 resource tile → gather intent 产生不了。
2. 没采集 → inventory 为空 → consume 条件（有 food）和 trade 的 surplus（qty>=2）条件永不满足。
3. 任务 claim 之后缺少 complete 路径（满足目标后没有把 task 标记 done 的 intent / 规则 / 事件），所以 completed 恒为 0。
4. `task_emergence.py` 需求任务用 `(kind, pos)` 去重，Agent 一移动 pos 改变就再次涌现同一需求，导致 task.emerged 爆炸（452），而真正的需求并未解决。

## 修复要求（保持轻量，禁止重型依赖/下载模型，7GB Jetson）
- 让启发式 Agent 具备**目标导向**：当存在未满足需求或 open 的 gather 任务时，朝最近的相关资源块做曼哈顿贪心移动（可含少量随机扰动避免卡死），踩到资源即 gather。
- 打通闭环：gather 增加 inventory → 有 food/water 且饥饿/口渴时 consume 降低 need → need 降到阈值以下时，对应任务应能被判定/提交 complete（请补 complete intent 与 RuleEngine 裁决 + world_state 应用，completed 计数真实增长）。
- 交易：相邻且双方各有对方所需 surplus 时发起 trade，RuleEngine 裁决后产生真实 `trade.completed`（注意要双方合意/资源校验，避免单方凭空生成物品，保证世界守恒）。
- 任务涌现去重：需求任务应按 **(agent, need)** 维度去重并跟踪生命周期，而不是仅按 (kind,pos)；任务完成/失效后才允许重新涌现。避免同一需求每 tick 重复 task.emerged。
- 保持事件溯源一致性：所有变化仍经 Intent→RuleEngine→Event，物品/资源守恒，非法 Intent 仍会被拒（最好让回归中能观察到 intent.rejected>0 的真实例子，例如越界移动）。
- 补/改 pytest：为上述闭环加断言（目标导向能到达资源、gather→consume 降低 need、任务能 complete、trade 守恒、需求任务不重复涌现）。`pytest` 必须真实全绿。
- 更新 docs/RESULTS.md，用**真机实际输出**替换旧的、与实测不符的数字（不得保留 trade=23 这类未复现数据）。

## 验收（我会真机独立复验，禁止假报）
1. `cd backend && . .venv/bin/activate && pytest -q` 全绿。
2. `python -m openworld.headless --ticks 100` 真实输出中必须出现：agent.gathered>0、consume 后 need 下降、completed>0、trade.completed>0（若 100 tick 太短可放宽 ticks，但命令默认参数要能稳定复现）；task.emerged 数量合理（不再数百条重复）。
3. 物品与资源总量守恒，无凭空生成。
4. frontend 若受影响，`npm run build` 仍需通过。
5. 提交（有意义的 commit message）并 push 到 github.com/hamr-hub/openworld-sim 的 main（不要 force push）。
最终报告：改动文件、pytest 结果、headless 真实事件统计、push 后的 commit 与 URL。做不到的项如实说明。
