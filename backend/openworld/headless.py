"""Headless batch runner — `python -m openworld.headless --ticks N`.

No web layer, no websockets.  Just the world kernel running deterministically
and printing emergent-event statistics.  Useful for:

    * CI tests
    * cost-free iteration when LLM is enabled but you don't need UI
    * quantitative experiments (see docs/09-research-plan.md)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from typing import List

from .simulator import Simulator, SimulationConfig


log = logging.getLogger("openworld.headless")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenWorld Sim — headless run")
    parser.add_argument("--ticks", type=int, default=120, help="number of ticks to simulate")
    parser.add_argument("--width", type=int, default=12)
    parser.add_argument("--height", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", action="store_true", help="emit JSON stats at the end")
    parser.add_argument("--show-recent", type=int, default=10,
                        help="print the last N events to stdout")
    args = parser.parse_args(argv)

    cfg = SimulationConfig(width=args.width, height=args.height)
    sim = Simulator(config=cfg)

    # Pin the policy rng for reproducibility
    for agent in sim.agents.values():
        if hasattr(agent.policy, "rng_seed"):
            agent.policy.rng_seed = args.seed  # type: ignore[attr-defined]

    events = sim.run(args.ticks)
    # Count from the *returned* event stream so that `intent.rejected`
    # audit records (which never mutate state and therefore aren't in
    # `event_log`) are included alongside the applied facts.
    kinds: dict = {}
    for e in events:
        kinds[e.kind] = kinds.get(e.kind, 0) + 1

    emergence_signals = {
        "task.emerged": kinds.get("task.emerged", 0),
        "task.claimed": kinds.get("task.claimed", 0),
        "trade.completed": kinds.get("trade.completed", 0),
        "agent.spoke": kinds.get("agent.spoke", 0),
        "intent.rejected": kinds.get("intent.rejected", 0),
        "agent.moved": kinds.get("agent.moved", 0),
        "agent.gathered": kinds.get("agent.gathered", 0),
    }

    summary = {
        "ticks": args.ticks,
        "total_events": len(events),
        "kinds": kinds,
        "emergence_signals": emergence_signals,
        "open_tasks": sum(1 for t in sim.state.tasks.values() if t.status == "open"),
        "completed_tasks": sum(1 for t in sim.state.tasks.values() if t.status == "done"),
    }

    # Conservation check: total_items = sum of agent inventories + tile amounts.
    # Trades, gathers, consumes should conserve the grand total.
    total_items = sim.state.total_agent_items() + sim.state.total_resource_mass()
    summary["total_items_in_world"] = total_items

    print(f"== openworld headless run ==")
    print(f"ticks         : {summary['ticks']}")
    print(f"total events  : {summary['total_events']}")
    print(f"event kinds   :")
    for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<22s} {v}")
    print()
    print(f"== emergence ==")
    for k, v in emergence_signals.items():
        print(f"  {k:<22s} {v}")
    print(f"open tasks    : {summary['open_tasks']}")
    print(f"completed     : {summary['completed_tasks']}")
    print(f"total items in world : {total_items}  "
          f"(agents={sim.state.total_agent_items()} + tiles={sim.state.total_resource_mass()})")

    if args.show_recent > 0:
        print()
        print(f"== last {min(args.show_recent, len(sim.state.event_log))} events ==")
        for e in sim.state.event_log[-args.show_recent:]:
            pj = json.dumps(e.payload, ensure_ascii=False)[:80]
            print(f"  t{e.tick:>4d}  {e.kind:<22s} {pj}")

    if args.json:
        print()
        print("== json ==")
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    # exit code: 0 if at least one emergence signal was observed, 2 otherwise
    emerged = (emergence_signals["task.emerged"]
               + emergence_signals["trade.completed"]
               + emergence_signals["agent.spoke"]
               + emergence_signals["agent.gathered"])
    return 0 if emerged > 0 else 2


if __name__ == "__main__":
    sys.exit(main())