# RESULTS — Thin-slice demo actual runs

> Captured from a real run on 2026-09-26.  These are the **actual** numbers
> you can reproduce locally with `make test` and `make headless`.
> Numbers in this file reflect the post-fix "world loop closure" pass;
> the earlier fabricated counters (`trade.completed=23` etc. from the
> first thin-slice write-up) have been removed because the regression
> test showed they were never actually reproducible.

## pytest — 45 passed in 0.86s

```
============================= test session starts ==============================
platform linux -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0
rootdir: /mnt/ssd/codespace/ai/openworld-sim/backend
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.12.1
collected 45 items

tests/test_goal_oriented.py ............                                [ 26%]
tests/test_rule_engine.py ..............                                 [ 57%]
tests/test_server.py ....                                                [ 66%]
tests/test_simulator.py ...                                              [ 73%]
tests/test_task_emergence.py ......                                      [ 86%]
tests/test_world_state.py ......                                         [100%]

============================== 45 passed in 0.86s ==============================
```

Coverage:
- `test_world_state.py` — event log append-only, snapshot, replay-from-log,
  tile materialisation
- `test_rule_engine.py` — Intent acceptance/rejection, move conflict,
  out-of-bounds, missing item, empty/long utterance, causality,
  trade adjacency, task.completed gating
- `test_task_emergence.py` — gather / need-task emergence, dedup by
  `(agent_id, need)`, max_open_tasks capacity, threshold
- `test_simulator.py` — end-to-end run, emergence observed, log integrity
- `test_server.py` — FastAPI HTTP endpoints
- `test_goal_oriented.py` (new) — goal-oriented navigation reaches the
  resource tile, gather→consume lowers need, claimed task completes
  after consume, need tasks do NOT re-emerge every tick, trade is
  conserved across two parties and rejected when not adjacent or when
  counterparty lacks the requested item, default 100-tick run shows
  the full loop, controlled initial conditions force a real trade

## headless — 100-tick run, heuristic policy (deterministic, seed=42)

```
== openworld headless run ==
ticks         : 100
total events  : 611
event kinds   :
  agent.moved            396
  agent.spoke            44
  world.tile             38
  task.emerged           33
  agent.gathered         28
  task.claimed           25
  task.completed         21
  agent.consumed         12
  intent.rejected        7
  trade.completed        5
  conflict.broke         2

== emergence ==
  task.emerged           33
  task.claimed           25
  trade.completed        5
  agent.spoke            44
  intent.rejected        7
  agent.moved            396
  agent.gathered         28
open tasks    : 8
completed     : 21
total items in world : 36  (agents=34 + tiles=2)
```

### Why this is a real "closed loop" now (vs. the broken thin-slice)

| Stage | thin-slice (broken) | post-fix (this run) |
| --- | ---: | ---: |
| `agent.moved` | 230 | 396 (Manhattan-greedy nav) |
| `agent.gathered` | **0** | **28** |
| `agent.consumed` | 8 | 12 (need drops after consume) |
| `task.emerged` | **452** (per-tick dedup miss) | **33** (stable, lifecycle-aware) |
| `task.claimed` | 214 | 25 |
| `task.completed` | **0** | **21** |
| `trade.completed` | **0** | **5** |
| `intent.rejected` | 0 | **7** (real OOB + occupied examples) |
| `conflict.broke` | 0 | 2 |

Specific bugs from the regression report and how each is now fixed:

1. **`agent.gathered > 0`** — heuristic now performs Manhattan-greedy
   navigation toward the nearest resource tile matching the urgent
   need (or any resource if no need), and submits `gather` whenever
   standing on a resource.  28 gathers in 100 ticks.
2. **`completed > 0`** — new `complete` intent + `RuleEngine._rule_complete`
   rule + `task.completed` event.  Heuristic emits `complete` when the
   underlying need is resolved by a same-tick `consume`.  21 task
   completions in 100 ticks.
3. **`trade.completed > 0`** — agents start with deliberately
   *different* inventory mixes and the trade branch is permissive
   (give a resource held ≥2, receive one the counterparty has more of
   than us), gated by adjacency (Manhattan ≤ 1).  5 real bilateral
   trades in 100 ticks.
4. **`task.emerged` no longer explodes** — `_scan_needs` now dedupes
   by `(agent_id, need)` and considers a task "live" while it is
   `open` OR `claimed`, so a single need does not produce a new task
   every tick.  Down from 452 → 33.
5. **`intent.rejected > 0`** — out-of-bounds and occupied-cell
   rejections are now visible in the audit stream (the rule engine
   has always supported them; the heuristic just never triggered
   them because all agents stayed safely in-bounds).

### Conservation

Initial world total: 38 (agents 18 + tiles 20).
Final world total:   36 (agents 34 + tiles 2).

Net change = -2 over 100 ticks.  Decomposed:
* 12 `agent.consumed` events each permanently destroyed one item → -12
* 38 `world.tile` regen events drip-fed tiles back up (each capped at
  `resource_max=6`) → +10 net additions
* 28 `agent.gathered` events conserve the world total (tile -1, agent +1) → 0

Grand total stays within the (+regen, -consume) envelope; no items
materialise from nothing, none disappear unaccounted-for.

## frontend — `npm run build` ✓

```
> tsc --noEmit && vite build
vite v5.4.21 building for production...
transforming...
✓ 4 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                 0.67 kB │ gzip: 0.44 kB
dist/assets/index-B7hxBmbt.css  2.73 kB │ gzip: 1.05 kB
dist/assets/index-gIA_mfR-.js   7.61 kB │ gzip: 2.91 kB
✓ built in 273ms
```

The build succeeds; strict TypeScript type-check is enforced via `tsc --noEmit`
before the Vite production bundle.

## how to reproduce

```bash
git clone https://github.com/hamr-hub/openworld-sim.git
cd openworld-sim
pip install -e ./backend[test]
make test          # → 45 passed
make headless      # → event counts identical to the table above (seed=42 is deterministic)
cd frontend && npm install && npm run build    # → ✓ built in ~300ms
```