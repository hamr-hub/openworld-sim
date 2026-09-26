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
from typing import Any, Dict, List, Optional, Protocol, Tuple

from .events import Intent
from .world_state import AgentRecord, WorldState, Coord


class Policy(Protocol):
    def decide(self, agent: AgentRecord, state: WorldState, tick: int) -> List[Intent]: ...


# ------------------------------------------------------------------ heuristic


# Resource that directly satisfies a need (used for target selection).
_NEED_TO_RESOURCE = {
    "hunger": "food",
    "thirst": "water",
}

# Need level thresholds.  Calibrated so that once an agent stops
# wanting to consume (need <= _CONSUME_TRIGGER), a claimed need-task is
# also eligible for completion (need < _NEED_RESOLVED).  A single
# consume typically takes need from above 0.5 to below 0.3, so the
# gap between `_CONSUME_TRIGGER` and `_NEED_RESOLVED` is the
# "post-consume slack".
_CONSUME_TRIGGER = 0.5   # agent considers consuming if need > this
_NEED_RESOLVED = 0.4     # if need drops below this, a claimed task can complete

# Movement / interaction ranges.
_TRADE_DISTANCE = 1        # adjacency (incl. same cell) — rule_engine enforces too
_TRADE_RANDOM_P = 0.85     # trade when conditions met (with this prob)


@dataclass
class HeuristicPolicy:
    rng_seed: Optional[int] = None
    verbose: bool = False

    def __post_init__(self) -> None:
        self.rng = random.Random(self.rng_seed if self.rng_seed is not None else 42)

    def decide(self, agent: AgentRecord, state: WorldState, tick: int) -> List[Intent]:
        intents: List[Intent] = []

        # 1) gather immediately if standing on a resource tile
        tile = state.get_tile(agent.pos)
        if tile.resource and tile.amount > 0:
            intents.append(Intent(
                agent_id=agent.agent_id,
                action="gather",
                payload={"qty": 1},
                tick=tick,
            ))

        # 2) consume if we have a satisfier and the need is urgent
        urgent_need = self._most_urgent_need(agent)
        if urgent_need is not None and agent.needs[urgent_need] > _CONSUME_TRIGGER:
            res = _NEED_TO_RESOURCE.get(urgent_need)
            if res and agent.inventory.get(res, 0) > 0:
                intents.append(Intent(
                    agent_id=agent.agent_id,
                    action="consume",
                    payload={"resource": res, "need": urgent_need},
                    tick=tick,
                ))

        # 3) complete any claimed task whose condition is now satisfied
        self._maybe_complete(agent, state, tick, intents)

        # 4) claim an open task we can pursue (only one claim per tick)
        self._maybe_claim(agent, state, tick, intents)

        # 5) trade only when adjacent and both sides hold useful surplus
        if self.rng.random() < _TRADE_RANDOM_P:
            self._maybe_trade(agent, state, tick, intents)

        # 6) navigate toward the current goal — but with a small chance of
        #    an "explore" random walk so idle agents test the boundary and
        #    produce realistic intent.rejected examples.
        if not any(i.action == "move" for i in intents):
            target = self._compute_target(agent, state)
            # 25% chance of an exploratory random walk; remainder goes
            # toward the goal.  The random branch occasionally lands on
            # an out-of-bounds cell when the agent is near a corner,
            # surfacing `intent.rejected` in the audit log.
            if self.rng.random() < 0.25:
                intents.append(self._random_move(agent, tick))
            elif target is not None and target != agent.pos:
                intents.append(self._move_toward(agent, target, tick))
            else:
                intents.append(self._random_move(agent, tick))

        # 7) occasional speak
        if self.rng.random() < 0.1 and len(state.agents) > 1:
            others = [a for a in state.agents.values() if a.agent_id != agent.agent_id]
            if others:
                target_a = self.rng.choice(others)
                intents.append(Intent(
                    agent_id=agent.agent_id,
                    action="speak",
                    target=target_a.agent_id,
                    payload={"text": self._rng_utterance()},
                    tick=tick,
                ))

        return intents

    # ------------------------------------------------------------------ goals

    def _compute_target(self, agent: AgentRecord, state: WorldState) -> Optional[Coord]:
        # a) pursue a task we've already claimed
        for t in state.tasks.values():
            if t.status == "claimed" and t.claimed_by == agent.agent_id:
                return tuple(t.pos)
        # b) urgent need → nearest resource that satisfies it (fallback: any resource)
        urgent = self._most_urgent_need(agent)
        if urgent is not None and agent.needs[urgent] > _CONSUME_TRIGGER:
            preferred = _NEED_TO_RESOURCE.get(urgent)
            t = self._nearest_resource_tile(state, agent.pos, preferred=preferred)
            if t is not None:
                return t
        # c) nearest open gather task (any kind, since gather is the canonical
        #    "do work for someone" task — heuristic doesn't second-guess it)
        gather_tasks = [t for t in state.tasks.values()
                        if t.status == "open" and t.kind == "gather"]
        if gather_tasks:
            nearest = min(gather_tasks,
                          key=lambda t: self._mdist(t.pos, agent.pos))
            return tuple(nearest.pos)
        # d) exploration: any remaining resource
        return self._nearest_resource_tile(state, agent.pos)

    # ------------------------------------------------------------ tasking

    def _maybe_complete(self, agent: AgentRecord, state: WorldState,
                        tick: int, intents: List[Intent]) -> None:
        for t in state.tasks.values():
            if t.status != "claimed" or t.claimed_by != agent.agent_id:
                continue
            if self._can_complete(t, agent, state, intents):
                intents.append(Intent(
                    agent_id=agent.agent_id,
                    action="complete",
                    payload={"task_id": t.task_id},
                    tick=tick,
                ))

    def _can_complete(self, t, agent: AgentRecord, state: WorldState,
                      intents: Optional[List[Intent]] = None) -> bool:
        need = t.payload.get("need") if isinstance(t.payload, dict) else None
        if need is not None:
            cur = agent.needs.get(need, 0.0)
            # If a consume intent for this need is queued in the same
            # tick, the post-consume need will be 0.3 lower.
            will_consume = any(
                i.action == "consume" and i.payload.get("need") == need
                for i in (intents or [])
            )
            post = cur - 0.3 if will_consume else cur
            return post < _NEED_RESOLVED
        if t.kind == "gather":
            return tuple(t.pos) == agent.pos
        return False

    def _maybe_claim(self, agent: AgentRecord, state: WorldState,
                     tick: int, intents: List[Intent]) -> None:
        # don't double-claim if we already have one
        for t in state.tasks.values():
            if t.status == "claimed" and t.claimed_by == agent.agent_id:
                return
        candidates = []
        for t in state.tasks.values():
            if t.status != "open":
                continue
            if t.kind == "trade":
                continue  # trade fires opportunistically below
            d = self._mdist(t.pos, agent.pos)
            candidates.append((d, t))
        if not candidates:
            return
        candidates.sort(key=lambda x: x[0])
        _, target = candidates[0]
        intents.append(Intent(
            agent_id=agent.agent_id,
            action="claim",
            payload={"task_id": target.task_id},
            tick=tick,
        ))

    def _maybe_trade(self, agent: AgentRecord, state: WorldState,
                     tick: int, intents: List[Intent]) -> None:
        # find an adjacent agent (Manhattan <= 1) that we can trade with.
        # We give a resource we hold at >=2 (so we keep at least one),
        # and receive a resource the other holds that we have *less* of
        # — strict inequality so we never refuse an item we already
        # dominate in.
        for other in state.agents.values():
            if other.agent_id == agent.agent_id:
                continue
            if self._mdist(agent.pos, other.pos) > _TRADE_DISTANCE:
                continue
            give_candidates = sorted(r for r, q in agent.inventory.items() if q >= 2)
            if not give_candidates:
                continue
            recv_candidates = sorted(
                r for r, q in other.inventory.items()
                if q >= 1 and agent.inventory.get(r, 0) < q
            )
            if not recv_candidates:
                continue
            intents.append(Intent(
                agent_id=agent.agent_id,
                action="trade",
                target=other.agent_id,
                payload={"give": {give_candidates[0]: 1},
                         "recv": {recv_candidates[0]: 1}},
                tick=tick,
            ))
            return  # one trade per tick

    # ------------------------------------------------------------ navigation

    def _move_toward(self, agent: AgentRecord, target: Coord, tick: int) -> Intent:
        ax, ay = agent.pos
        tx, ty = target
        dx = 0 if tx == ax else (1 if tx > ax else -1)
        dy = 0 if ty == ay else (1 if ty > ay else -1)
        # randomly pick axis to break ties / avoid gridlock (Manhattan greedy w/ jitter)
        if dx != 0 and (dy == 0 or self.rng.random() < 0.5):
            nx, ny = ax + dx, ay
        elif dy != 0:
            nx, ny = ax, ay + dy
        else:
            return self._random_move(agent, tick)
        return Intent(
            agent_id=agent.agent_id,
            action="move",
            payload={"to": [nx, ny]},
            tick=tick,
        )

    def _random_move(self, agent: AgentRecord, tick: int) -> Intent:
        dx, dy = self.rng.choice([(0, 1), (0, -1), (1, 0), (-1, 0), (0, 0)])
        nx, ny = agent.pos[0] + dx, agent.pos[1] + dy
        return Intent(
            agent_id=agent.agent_id,
            action="move",
            payload={"to": [nx, ny]},
            tick=tick,
        )

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _most_urgent_need(agent: AgentRecord) -> Optional[str]:
        if not agent.needs:
            return None
        return max(agent.needs.items(), key=lambda kv: kv[1])[0]

    @staticmethod
    def _mdist(a: Coord, b: Coord) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    @staticmethod
    def _nearest_resource_tile(state: WorldState, agent_pos: Coord,
                               preferred: Optional[str] = None) -> Optional[Coord]:
        best: Optional[Tuple[int, Coord]] = None
        for y in range(state.height):
            for x in range(state.width):
                tile = state.get_tile((x, y))
                if not tile.resource or tile.amount <= 0:
                    continue
                if preferred is not None and tile.resource != preferred:
                    continue
                d = abs(x - agent_pos[0]) + abs(y - agent_pos[1])
                if best is None or d < best[0]:
                    best = (d, (x, y))
        return best[1] if best else None

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