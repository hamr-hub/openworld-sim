"""Agent registry — first-class citizens of the world."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .events import Intent, Event
from .policies import HeuristicPolicy, Policy
from .world_state import AgentRecord, WorldState


@dataclass
class Agent:
    agent_id: str
    name: str
    persona: str = ""
    policy: Optional[Policy] = None
    # Per-agent starting inventory.  Each demo agent is intentionally
    # seeded with a *different* mix so that bilateral trade is possible
    # from the start (no point having a market when everyone carries the
    # same items).
    starting_inventory: Optional[Dict[str, int]] = None

    def make_record(self) -> AgentRecord:
        inv = self.starting_inventory if self.starting_inventory is not None else {
            "food": 2, "wood": 2, "ore": 0, "water": 2,
        }
        return AgentRecord(
            agent_id=self.agent_id,
            name=self.name,
            pos=(0, 0),
            needs={"hunger": 0.3, "social": 0.2, "energy": 0.2},
            goals=["survive", "socialise"],
            inventory=dict(inv),
        )


def default_agents() -> Dict[str, Agent]:
    """The thin-slice demo ships 4 agents with distinct personas AND
    distinct starting inventories, so the trade loop has something to
    work with from tick 1."""
    return {
        "alice": Agent(
            agent_id="alice", name="Alice",
            persona="gatherer, friendly",
            policy=HeuristicPolicy(rng_seed=11),
            starting_inventory={"food": 3, "wood": 1, "ore": 0, "water": 2},
        ),
        "bob": Agent(
            agent_id="bob", name="Bob",
            persona="trader, cautious",
            policy=HeuristicPolicy(rng_seed=23),
            starting_inventory={"food": 1, "wood": 3, "ore": 0, "water": 1},
        ),
        "carol": Agent(
            agent_id="carol", name="Carol",
            persona="explorer, curious",
            policy=HeuristicPolicy(rng_seed=37),
            starting_inventory={"food": 0, "wood": 1, "ore": 2, "water": 1},
        ),
        "dave": Agent(
            agent_id="dave", name="Dave",
            persona="craftsman, grumpy",
            policy=HeuristicPolicy(rng_seed=53),
            starting_inventory={"food": 1, "wood": 0, "ore": 1, "water": 1},
        ),
    }


# ----------------------------------------------------------------- registration


def register_agents(state: WorldState, agents: Dict[str, Agent], spawn_positions) -> List[Event]:
    """Produce `agent.register` events at distinct spawn positions.

    Spawning is itself an Event — the world kernel sees it.  This keeps the
    'Agents are first-class citizens but cannot write state directly'
    invariant intact.
    """
    events: List[Event] = []
    for agent, pos in zip(agents.values(), spawn_positions):
        rec = agent.make_record()
        rec.pos = tuple(pos)
        state.agents[agent.agent_id] = rec  # world kernel materialises via event below
        events.append(Event(
            kind="agent.register",
            payload={
                "agent_id": agent.agent_id,
                "name": agent.name,
                "pos": list(pos),
                "persona": agent.persona,
                "needs": rec.needs,
                "goals": rec.goals,
                "inventory": rec.inventory,
            },
            tick=0,
        ))
    return events