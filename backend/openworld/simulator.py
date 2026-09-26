"""Simulator — orchestrates one tick.

Sequence per tick:

    1. clock advances
    2. agents perceive state and submit Intents
    3. RuleEngine arbitrates Intents -> Events
    4. TaskEmergence scans state -> `task.emerged` events
    5. all new Events appended to log; EventBus fans them out

The simulator is the *only* place that drives time forward.  Everything
else is pure functions over (state, intent) -> events.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .agents import Agent, default_agents, register_agents
from .clock import Clock
from .events import Event, EventBus, Intent
from .rule_engine import RuleEngine
from .task_emergence import EmergenceConfig, TaskEmergence
from .world_state import WorldState


log = logging.getLogger(__name__)


@dataclass
class SimulationConfig:
    width: int = 12
    height: int = 12
    spawn_positions = ((1, 1), (1, 10), (10, 1), (10, 10))
    needs_decay_per_tick: float = 0.02  # small decay -> drives emergence


class Simulator:
    """Continuous world-kernel simulator."""

    def __init__(
        self,
        config: Optional[SimulationConfig] = None,
        agents: Optional[Dict[str, Agent]] = None,
        rule_engine: Optional[RuleEngine] = None,
        task_emergence: Optional[TaskEmergence] = None,
    ) -> None:
        self.config = config or SimulationConfig()
        self.clock = Clock()
        self.state = WorldState(width=self.config.width, height=self.config.height)
        self.agents = agents or default_agents()
        self.engine = rule_engine or RuleEngine()
        self.emergence = task_emergence or TaskEmergence(EmergenceConfig())
        self.bus = EventBus()
        self._bootstrap()

    # ---------------------------------------------------------------- bootstrap

    def _bootstrap(self) -> None:
        """Initial world event log: grid + resources + agents."""
        # init event
        self.state.apply_event(Event(
            kind="world.init",
            payload={"width": self.state.width, "height": self.state.height},
            tick=0,
        ))
        # scatter some resource tiles
        seed_tiles = [
            ((3, 3), "wood", 5),
            ((6, 6), "wood", 3),
            ((8, 2), "ore", 4),
            ((2, 8), "ore", 2),
            ((5, 5), "food", 6),
        ]
        for pos, res, amt in seed_tiles:
            self.state.apply_event(Event(
                kind="world.tile",
                payload={"pos": list(pos), "kind": "ground", "resource": res, "amount": amt},
                tick=0,
            ))
        # register agents
        events = register_agents(self.state, self.agents, self.config.spawn_positions)
        for e in events:
            self.state.apply_event(e)
        self.bus.publish(events)

    # ------------------------------------------------------------------ tick

    def step(self) -> List[Event]:
        """Advance the world by one tick.  Returns all Events produced."""
        tick = self.clock.advance()
        new_events: List[Event] = []

        # 1) needs decay (drives emergence)
        self._decay_needs()

        # 2) each agent submits Intents
        intents = self._gather_intents(tick)

        # 3) rule engine arbitrates
        outcome = self.engine.arbitrate(self.state, intents, tick)
        new_events.extend(outcome.accepted)
        new_events.extend(outcome.rejected)

        # 4) task emergence (also produces events)
        emergent = self.emergence.scan(self.state, tick)
        new_events.extend(emergent)
        for e in emergent:
            self.state.apply_event(e)

        # 5) fan out
        if new_events:
            self.bus.publish(new_events)
        return new_events

    # -------------------------------------------------------------- helpers

    def _decay_needs(self) -> None:
        # decay hunger/social to drive emergence
        decay = self.config.needs_decay_per_tick
        for agent in self.state.agents.values():
            for need in ("hunger", "social"):
                if need in agent.needs:
                    agent.needs[need] = min(1.0, agent.needs[need] + decay)

    def _gather_intents(self, tick: int) -> List[Intent]:
        intents: List[Intent] = []
        for agent_id, agent in self.agents.items():
            if agent.policy is None:
                continue
            try:
                intents.extend(agent.policy.decide(self.state.agents[agent_id], self.state, tick))
            except Exception as e:  # noqa: BLE001 — never crash the world
                log.warning("agent %s policy raised: %s", agent_id, e)
        return intents

    def run(self, ticks: int) -> List[Event]:
        all_events: List[Event] = []
        for _ in range(ticks):
            all_events.extend(self.step())
        return all_events

    # ------------------------------------------------------------- analytics

    def event_kinds(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in self.state.event_log:
            counts[e.kind] = counts.get(e.kind, 0) + 1
        return counts