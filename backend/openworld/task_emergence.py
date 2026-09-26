"""TaskEmergence — tasks are *derived*, not scripted.

A task is a world-state delta that should happen.  We scan the world
state every tick and emit `task.emerged` events for unmet needs, conflicts,
and opportunities.  Agents then claim and complete them.

Dedup rules (the key fix vs. the broken thin-slice):

  * need-driven tasks are deduplicated by **(agent_id, need)**.  A task
    remains alive (open OR claimed) until it completes / fails — only then
    can a new one for the same (agent, need) emerge.  This stops the
    "every tick = new task for same need" explosion.
  * gather tasks are deduplicated by **(kind, pos)** with the same
    open|claimed guard, since the tile is the unit of work.
  * trade opportunities are deduplicated by **(kind, agent-pair)**.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .events import Event
from .world_state import AgentRecord, WorldState, Coord, TaskRecord


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@dataclass
class EmergenceConfig:
    need_threshold: float = 0.6          # need above which a task emerges
    conflict_distance: int = 1            # adjacency for conflict detection
    max_open_tasks: int = 12              # never let the queue explode


# a task is "live" for dedup purposes if it is open OR claimed.
_LIVE_STATUSES = ("open", "claimed")


class TaskEmergence:
    """Scan world state and emit `task.emerged` events for unmet conditions."""

    def __init__(self, config: Optional[EmergenceConfig] = None) -> None:
        self.config = config or EmergenceConfig()

    def scan(self, state: WorldState, tick: int) -> List[Event]:
        events: List[Event] = []
        events.extend(self._scan_needs(state, tick))
        if self._live_task_count(state) >= self.config.max_open_tasks:
            return events
        opps = self._scan_opportunities(state, tick)
        for e in opps:
            state.apply_event(e)
        events.extend(opps)
        return events

    # ----------------------------------------------------------------- needs

    def _scan_needs(self, state: WorldState, tick: int) -> List[Event]:
        events: List[Event] = []
        for agent in state.agents.values():
            for need, level in agent.needs.items():
                if self._live_task_count(state) >= self.config.max_open_tasks:
                    return events
                if level < self.config.need_threshold:
                    continue
                # dedup by (agent_id, need) — regardless of agent position
                if self._has_need_task(state, agent.agent_id, need):
                    continue
                kind = self._need_to_action(need)
                if kind is None:
                    continue
                events.append(Event(
                    kind="task.emerged",
                    payload={
                        "task_id": _new_id("task"),
                        "title": f"{agent.name} needs {need}",
                        "kind": kind,
                        "pos": list(agent.pos),
                        "need": need,
                        "agent_id": agent.agent_id,
                        "reward": {"relationship": 0.1},
                    },
                    tick=tick,
                ))
                state.apply_event(events[-1])
        return events

    # --------------------------------------------------------- opportunities

    def _scan_opportunities(self, state: WorldState, tick: int) -> List[Event]:
        events: List[Event] = []
        # resource tile + nobody on it -> gather task
        for y in range(state.height):
            for x in range(state.width):
                if self._live_task_count(state) >= self.config.max_open_tasks:
                    return events
                tile = state.get_tile((x, y))
                if tile.resource is None or tile.amount <= 0:
                    continue
                # dedup: a live gather task for this tile already exists?
                if self._has_gather_task(state, (x, y), tile.resource):
                    continue
                on_tile = [a for a in state.agents.values() if a.pos == (x, y)]
                if on_tile:
                    continue
                events.append(Event(
                    kind="task.emerged",
                    payload={
                        "task_id": _new_id("task"),
                        "title": f"gather {tile.resource} at ({x},{y})",
                        "kind": "gather",
                        "pos": [x, y],
                        "resource": tile.resource,
                        "reward": {"hunger": -0.2},
                    },
                    tick=tick,
                ))
        # trading opportunity — two agents near each other, both hold something
        agents = list(state.agents.values())
        for i, a in enumerate(agents):
            for b in agents[i+1:]:
                if self._live_task_count(state) >= self.config.max_open_tasks:
                    return events
                if self._distance(a.pos, b.pos) > self.config.conflict_distance + 1:
                    continue
                if not a.inventory or not b.inventory:
                    continue
                if self._has_trade_task(state, a.agent_id, b.agent_id):
                    continue
                events.append(Event(
                    kind="task.emerged",
                    payload={
                        "task_id": _new_id("task"),
                        "title": f"trade between {a.name} and {b.name}",
                        "kind": "trade",
                        "pos": list(a.pos),
                        "agent_a": a.agent_id,
                        "agent_b": b.agent_id,
                        "reward": {"relationship": 0.2},
                    },
                    tick=tick,
                ))
                break  # one trade task per pair per tick
        return events

    # ----------------------------------------------------------------- utils

    def _live_task_count(self, state: WorldState) -> int:
        return sum(1 for t in state.tasks.values() if t.status in _LIVE_STATUSES)

    def _has_need_task(self, state: WorldState, agent_id: str, need: str) -> bool:
        for t in state.tasks.values():
            if t.status not in _LIVE_STATUSES:
                continue
            if t.payload.get("need") == need and t.payload.get("agent_id") == agent_id:
                return True
        return False

    def _has_gather_task(self, state: WorldState, pos: Coord, resource: str) -> bool:
        for t in state.tasks.values():
            if t.status not in _LIVE_STATUSES:
                continue
            if t.kind != "gather":
                continue
            if t.pos == pos:
                return True
        return False

    def _has_trade_task(self, state: WorldState, a_id: str, b_id: str) -> bool:
        for t in state.tasks.values():
            if t.status not in _LIVE_STATUSES:
                continue
            if t.kind != "trade":
                continue
            pair = {t.payload.get("agent_a"), t.payload.get("agent_b")}
            if pair == {a_id, b_id}:
                return True
        return False

    @staticmethod
    def _distance(a: Coord, b: Coord) -> int:
        return abs(a[0]-b[0]) + abs(a[1]-b[1])

    @staticmethod
    def _need_to_action(need: str) -> Optional[str]:
        return {
            "hunger": "gather",    # gather -> consume
            "thirst": "gather",
            "social": "trade",     # social = interact
            "energy": "rest",
        }.get(need)