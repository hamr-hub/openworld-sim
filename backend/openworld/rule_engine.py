"""RuleEngine — deterministic arbitration of Intents.

The RuleEngine is the only place that *creates Events from Intents*.  It is
intentionally small and boring — it does not call out to anything
non-deterministic.  This makes the simulator replayable and the world
consistent (an Agent cannot teleport by lying about coordinates).

For each Intent the engine produces:
    accept  -> one or more Events
    reject  -> an `intent.rejected` Event (audit)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .events import Event, Intent
from .world_state import WorldState, AgentRecord


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@dataclass
class RuleOutcome:
    accepted: List[Event]
    rejected: List[Event]


# Threshold under which a "need" is considered resolved (post-consume).
# Kept in sync with `_NEED_RESOLVED` in policies.py — both must agree
# on what "resolved enough to complete" means, or the heuristic will
# emit `complete` intents that the rule engine then rejects.
_NEED_RESOLVED_BELOW = 0.4


class RuleEngine:
    """Pure function over (state, intent-list) -> (events, new-events-list)."""

    def arbitrate(self, state: WorldState, intents: List[Intent], tick: int) -> RuleOutcome:
        accepted: List[Event] = []
        rejected: List[Event] = []
        # 1) detect move conflicts (multiple intents targeting same cell)
        contested: Dict[Tuple[int, int], List[Intent]] = {}
        for it in intents:
            if it.action == "move":
                to = tuple(it.payload.get("to", ()))
                if to:
                    contested.setdefault(to, []).append(it)

        # 2) resolve: lowest agent_id wins; losers get a conflict.broke event
        losers: set = set()
        for cell, group in contested.items():
            if len(group) > 1:
                winner = min(group, key=lambda i: i.agent_id)
                for it in group:
                    if it is not winner:
                        losers.add(it.intent_id)
                accepted.append(Event(
                    kind="conflict.broke",
                    payload={"cell": list(cell),
                             "agents": [i.agent_id for i in group],
                             "winner": winner.agent_id},
                    tick=tick,
                ))

        # 3) arbitrate remaining intents
        for intent in intents:
            if intent.intent_id in losers:
                rejected.append(Event(
                    kind="intent.rejected",
                    payload={"intent_id": intent.intent_id,
                             "agent_id": intent.agent_id,
                             "action": intent.action,
                             "reason": "lost movement contest"},
                    tick=tick,
                    caused_by=intent.intent_id,
                ))
                continue
            outcome = self._arbitrate_one(state, intent, tick)
            accepted.extend(outcome.accepted)
            rejected.extend(outcome.rejected)
            for ev in outcome.accepted:
                state.apply_event(ev)
        return RuleOutcome(accepted=accepted, rejected=rejected)

    # ------------------------------------------------------------------ main

    def _arbitrate_one(self, state: WorldState, intent: Intent, tick: int) -> RuleOutcome:
        a = intent.action
        aid = intent.agent_id
        agent = state.agents.get(aid)
        if agent is None:
            return self._reject(intent, tick, "unknown agent")

        handler = {
            "move": self._rule_move,
            "speak": self._rule_speak,
            "gather": self._rule_gather,
            "consume": self._rule_consume,
            "trade": self._rule_trade,
            "claim": self._rule_claim,
            "complete": self._rule_complete,
        }.get(a)
        if handler is None:
            return self._reject(intent, tick, f"unknown action {a}")

        try:
            events = handler(state, agent, intent, tick)
            return RuleOutcome(accepted=events, rejected=[])
        except _RuleReject as r:
            return self._reject(intent, tick, str(r))

    # ----------------------------------------------------------------- helpers

    def _reject(self, intent: Intent, tick: int, reason: str) -> RuleOutcome:
        return RuleOutcome(
            accepted=[],
            rejected=[Event(
                kind="intent.rejected",
                payload={"intent_id": intent.intent_id, "agent_id": intent.agent_id,
                         "action": intent.action, "reason": reason},
                tick=tick,
                caused_by=intent.intent_id,
            )],
        )

    # ----------------------------------------------------------------- actions

    def _rule_move(self, state: WorldState, agent: AgentRecord, intent: Intent, tick: int) -> List[Event]:
        to = tuple(intent.payload.get("to", agent.pos))
        if not state.in_bounds(to):
            raise _RuleReject("out of bounds")
        tile = state.get_tile(to)
        if tile.kind == "wall":
            raise _RuleReject("blocked by wall")
        if tile.kind == "water":
            raise _RuleReject("blocked by water")
        # cell occupancy: someone already there this tick?
        for other in state.agents.values():
            if other.agent_id == agent.agent_id:
                continue
            if other.pos == to:
                raise _RuleReject(f"cell occupied by {other.agent_id}")
        return [Event(
            kind="agent.moved",
            payload={"agent_id": agent.agent_id, "from": agent.pos, "to": to},
            tick=tick,
            caused_by=intent.intent_id,
        )]

    def _rule_speak(self, state: WorldState, agent: AgentRecord, intent: Intent, tick: int) -> List[Event]:
        text = str(intent.payload.get("text", ""))
        if not text.strip():
            raise _RuleReject("empty utterance")
        if len(text) > 200:
            raise _RuleReject("utterance too long")
        return [Event(
            kind="agent.spoke",
            payload={"agent_id": agent.agent_id, "text": text, "target": intent.target},
            tick=tick,
            caused_by=intent.intent_id,
        )]

    def _rule_gather(self, state: WorldState, agent: AgentRecord, intent: Intent, tick: int) -> List[Event]:
        pos = agent.pos
        tile = state.get_tile(pos)
        if tile.resource is None or tile.amount <= 0:
            raise _RuleReject("nothing to gather here")
        qty = min(int(intent.payload.get("qty", 1)), tile.amount)
        events = [Event(
            kind="agent.gathered",
            payload={"agent_id": agent.agent_id, "resource": tile.resource, "qty": qty},
            tick=tick,
            caused_by=intent.intent_id,
        )]
        # tile depletion event
        events.append(Event(
            kind="world.tile",
            payload={"pos": list(pos), "kind": tile.kind,
                     "resource": tile.resource, "amount": tile.amount - qty},
            tick=tick,
        ))
        return events

    def _rule_consume(self, state: WorldState, agent: AgentRecord, intent: Intent, tick: int) -> List[Event]:
        res = intent.payload.get("resource")
        if not res:
            raise _RuleReject("missing resource")
        if agent.inventory.get(res, 0) <= 0:
            raise _RuleReject("not in inventory")
        need = intent.payload.get("need", "hunger")
        return [Event(
            kind="agent.consumed",
            payload={"agent_id": agent.agent_id, "resource": res, "need": need},
            tick=tick,
            caused_by=intent.intent_id,
        )]

    def _rule_trade(self, state: WorldState, agent: AgentRecord, intent: Intent, tick: int) -> List[Event]:
        other_id = intent.target
        if not other_id or other_id not in state.agents:
            raise _RuleReject("no counterparty")
        other = state.agents[other_id]
        # adjacency is part of the world physics — must be co-located (incl. same cell)
        if abs(other.pos[0] - agent.pos[0]) + abs(other.pos[1] - agent.pos[1]) > 1:
            raise _RuleReject("not adjacent to counterparty")
        give = dict(intent.payload.get("give", {}))
        recv = dict(intent.payload.get("recv", {}))
        if not give or not recv:
            raise _RuleReject("empty trade")
        # conservation: both sides must hold what they "give up"
        for r, q in give.items():
            if agent.inventory.get(r, 0) < q:
                raise _RuleReject(f"missing {r} for trade")
        for r, q in recv.items():
            if other.inventory.get(r, 0) < q:
                raise _RuleReject(f"counterparty missing {r}")
        return [Event(
            kind="trade.completed",
            payload={"from": agent.agent_id, "to": other_id, "give": give, "recv": recv},
            tick=tick,
            caused_by=intent.intent_id,
        )]

    def _rule_claim(self, state: WorldState, agent: AgentRecord, intent: Intent, tick: int) -> List[Event]:
        tid = intent.payload.get("task_id")
        t = state.tasks.get(tid) if tid else None
        if t is None:
            raise _RuleReject("no such task")
        if t.status != "open":
            raise _RuleReject(f"task already {t.status}")
        return [Event(
            kind="task.claimed",
            payload={"task_id": tid, "agent_id": agent.agent_id},
            tick=tick,
            caused_by=intent.intent_id,
        )]

    def _rule_complete(self, state: WorldState, agent: AgentRecord, intent: Intent, tick: int) -> List[Event]:
        tid = intent.payload.get("task_id")
        t = state.tasks.get(tid) if tid else None
        if t is None:
            raise _RuleReject("no such task")
        if t.status != "claimed":
            raise _RuleReject(f"task is {t.status}, not claimed")
        if t.claimed_by != agent.agent_id:
            raise _RuleReject("not the claimer")
        # per-kind completion gate
        need = t.payload.get("need") if isinstance(t.payload, dict) else None
        if need is not None:
            # need task — agent's need must be below resolution threshold
            if agent.needs.get(need, 0.0) >= _NEED_RESOLVED_BELOW:
                raise _RuleReject(f"need '{need}' not yet resolved")
        elif t.kind == "gather":
            # gather task — agent must be standing on the resource tile
            if tuple(t.pos) != agent.pos:
                raise _RuleReject("not at gather site")
        return [Event(
            kind="task.completed",
            payload={"task_id": tid, "completed_by": agent.agent_id,
                     "kind": t.kind, "need": need},
            tick=tick,
            caused_by=intent.intent_id,
        )]


class _RuleReject(Exception):
    pass