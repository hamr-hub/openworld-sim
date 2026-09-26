"""TaskEmergence — tasks are *derived*, not scripted.

A task is a world-state delta that should happen.  We scan the world
state every tick and emit `task.emerged` events for unmet needs, conflicts,
and opportunities.  Agents then claim and complete them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .events import Event
from .world_state import AgentRecord, WorldState, Coord


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@dataclass
class EmergenceConfig:
    need_threshold: float = 0.6          # need above which a task emerges
    conflict_distance: int = 1            # adjacency for conflict detection
    max_open_tasks: int = 12              # never let the queue explode


class TaskEmergence:
    """Scan world state and emit `task.emerged` events for unmet conditions."""

    def __init__(self, config: Optional[EmergenceConfig] = None) -> None:
        self.config = config or EmergenceConfig()

    def scan(self, state: WorldState, tick: int) -> List[Event]:
        # _scan_needs already applies events to state for accurate dedupe/capacity
        events: List[Event] = []
        events.extend(self._scan_needs(state, tick))
        if self._open_task_count(state) >= self.config.max_open_tasks:
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
                # respect capacity per-task
                if self._open_task_count(state) >= self.config.max_open_tasks:
                    return events
                if level < self.config.need_threshold:
                    continue
                # already a matching open task?
                if self._has_open(state, f"need:{need}", agent.pos):
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
                        "reward": {"relationship": 0.1},
                    },
                    tick=tick,
                ))
                # apply immediately so capacity tracking is accurate
                state.apply_event(events[-1])
        return events

    # --------------------------------------------------------- opportunities

    def _scan_opportunities(self, state: WorldState, tick: int) -> List[Event]:
        events: List[Event] = []
        # resource tile + someone with empty inventory near -> gather task
        for y in range(state.height):
            for x in range(state.width):
                tile = state.get_tile((x, y))
                if tile.resource is None or tile.amount <= 0:
                    continue
                # is there already a gather task for this tile?
                if self._has_open(state, "gather", (x, y)):
                    continue
                # is any agent already standing on it?
                on_tile = [a for a in state.agents.values() if a.pos == (x, y)]
                if on_tile:
                    continue
                # pick nearest agent as the implicit beneficiary
                nearest = min(state.agents.values(),
                              key=lambda a: abs(a.pos[0]-x)+abs(a.pos[1]-y),
                              default=None)
                if nearest is None:
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
                if self._distance(a.pos, b.pos) > self.config.conflict_distance + 1:
                    continue
                if not a.inventory or not b.inventory:
                    continue
                if self._has_open(state, "trade", a.pos):
                    continue
                events.append(Event(
                    kind="task.emerged",
                    payload={
                        "task_id": _new_id("task"),
                        "title": f"trade between {a.name} and {b.name}",
                        "kind": "trade",
                        "pos": list(a.pos),
                        "reward": {"relationship": 0.2},
                    },
                    tick=tick,
                ))
                break  # one trade task per pair per tick
        return events

    # ----------------------------------------------------------------- utils

    def _open_task_count(self, state: WorldState) -> int:
        return sum(1 for t in state.tasks.values() if t.status == "open")

    def _has_open(self, state: WorldState, kind: str, pos: Coord) -> bool:
        return any(t.kind == kind and t.status == "open" and t.pos == pos
                   for t in state.tasks.values())

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