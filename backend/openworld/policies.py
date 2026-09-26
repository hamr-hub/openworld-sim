"""Agent policies — heuristic (default) and LLM (optional).

Both policies implement the same `Policy` protocol: given an observation
(the agent's local view of the world), return a list of Intents.

The heuristic policy is deterministic and self-contained — the simulator
runs end-to-end with **no external LLM**.  This is critical for:

    * reproducibility
    * offline / Jetson-class hardware
    * cost (no API bill for basic runs)

When `OPENWORLD_LLM=1` and an API key is present, the LLM policy is
constructed.  Otherwise the heuristic policy is used.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from .events import Intent
from .world_state import AgentRecord, WorldState


class Policy(Protocol):
    def decide(self, agent: AgentRecord, state: WorldState, tick: int) -> List[Intent]: ...


# ------------------------------------------------------------------ heuristic


@dataclass
class HeuristicPolicy:
    rng_seed: Optional[int] = None
    verbose: bool = False

    def __post_init__(self) -> None:
        # default seed when None so demos are deterministic
        self.rng = random.Random(self.rng_seed if self.rng_seed is not None else 42)

    def decide(self, agent: AgentRecord, state: WorldState, tick: int) -> List[Intent]:
        intents: List[Intent] = []
        # 1) satisfy the most urgent need
        if agent.needs:
            urgent_need = max(agent.needs.items(), key=lambda kv: kv[1])[0]
            intents.extend(self._satisfy_need(agent, urgent_need, tick))
        # 2) look around — find a nearby resource tile and gather if on it
        tile = state.get_tile(agent.pos)
        if tile.resource and tile.amount > 0:
            intents.append(Intent(
                agent_id=agent.agent_id,
                action="gather",
                payload={"qty": 1},
                tick=tick,
            ))
        # 3) consume if hungry
        if agent.needs.get("hunger", 0.0) > 0.4 and agent.inventory.get("food", 0) > 0:
            intents.append(Intent(
                agent_id=agent.agent_id,
                action="consume",
                payload={"resource": "food", "need": "hunger"},
                tick=tick,
            ))
        # 4) try to claim any open task that fits
        for t in state.tasks.values():
            if t.status != "open":
                continue
            if t.kind in ("gather", "trade") and abs(t.pos[0]-agent.pos[0]) + abs(t.pos[1]-agent.pos[1]) <= 3:
                intents.append(Intent(
                    agent_id=agent.agent_id,
                    action="claim",
                    payload={"task_id": t.task_id},
                    tick=tick,
                ))
                break
        # 5) trade when a neighbour has something we don't (and we have surplus)
        if self.rng.random() < 0.35:
            others = [a for a in state.agents.values()
                      if a.agent_id != agent.agent_id
                      and abs(a.pos[0]-agent.pos[0]) + abs(a.pos[1]-agent.pos[1]) <= 2]
            for other in others:
                mine_extra = {r: q for r, q in agent.inventory.items() if q >= 2}
                their_extra = {r: q for r, q in other.inventory.items() if q >= 1 and r not in mine_extra}
                if mine_extra and their_extra:
                    give_res = self.rng.choice(list(mine_extra.keys()))
                    recv_res = self.rng.choice(list(their_extra.keys()))
                    intents.append(Intent(
                        agent_id=agent.agent_id,
                        action="trade",
                        target=other.agent_id,
                        payload={"give": {give_res: 1}, "recv": {recv_res: 1}},
                        tick=tick,
                    ))
                    break
        # 6) move randomly with some probability to explore
        if not intents or self.rng.random() < 0.4:
            intents.append(self._random_move(agent, tick))
        # 7) occasionally speak (simulate social chatter)
        if self.rng.random() < 0.15 and len(state.agents) > 1:
            others = [a for a in state.agents.values() if a.agent_id != agent.agent_id]
            target = self.rng.choice(others)
            intents.append(Intent(
                agent_id=agent.agent_id,
                action="speak",
                target=target.agent_id,
                payload={"text": self._rng_utterance()},
                tick=tick,
            ))
        return intents

    # ----------------------------------------------------------------- helpers

    def _satisfy_need(self, agent: AgentRecord, need: str, tick: int) -> List[Intent]:
        # try to consume if we have it
        food_key = {"hunger": "food", "thirst": "water"}.get(need)
        if food_key and agent.inventory.get(food_key, 0) > 0:
            return [Intent(
                agent_id=agent.agent_id,
                action="consume",
                payload={"resource": food_key, "need": need},
                tick=tick,
            )]
        return []

    def _random_move(self, agent: AgentRecord, tick: int) -> Intent:
        dx, dy = self.rng.choice([(0, 1), (0, -1), (1, 0), (-1, 0), (0, 0)])
        nx, ny = agent.pos[0] + dx, agent.pos[1] + dy
        return Intent(
            agent_id=agent.agent_id,
            action="move",
            payload={"to": [nx, ny]},
            tick=tick,
        )

    def _rng_utterance(self) -> str:
        return self.rng.choice([
            "hello, anyone nearby?",
            "I'm low on food, please help",
            "let's trade wood for food",
            "wonderful day for gathering",
            "do you know where the ore is?",
        ])


# ------------------------------------------------------------------ LLM stub


@dataclass
class LLMPolicy:
    """LLM-backed policy.  Stub if no API key is configured.

    When OPENWORLD_LLM=1 and OPENAI_API_KEY is set, this would dispatch
    a structured prompt to the model.  In the thin-slice demo we ship
    a stub that emits a single speak-intent — sufficient to demonstrate
    the seam.  Replace `_call_llm` with a real client to enable.
    """

    model: str = "stub"
    enabled_via_env: bool = False

    def decide(self, agent: AgentRecord, state: WorldState, tick: int) -> List[Intent]:
        if not self.enabled_via_env:
            return []
        return [Intent(
            agent_id=agent.agent_id,
            action="speak",
            payload={"text": f"[{agent.name}] thinking about what to do at t{tick}"},
            tick=tick,
        )]


def make_default_policy() -> Policy:
    """Pick the right policy based on env.  LLM only if explicitly enabled + key set."""
    if os.environ.get("OPENWORLD_LLM") == "1" and os.environ.get("OPENAI_API_KEY"):
        return LLMPolicy(enabled_via_env=True)
    return HeuristicPolicy(rng_seed=42)