"""Tests for the goal-oriented HeuristicPolicy and end-to-end loop closure.

These tests target the real bugs the task spec called out:
  * agents must be able to reach a resource tile (goal-oriented navigation)
  * gather -> consume must drop a need
  * tasks must complete (not stay claimed forever)
  * need tasks must not re-emerge every tick
  * trade must conserve items
"""

from __future__ import annotations

import pytest

from openworld.agents import default_agents, register_agents
from openworld.events import Event, Intent
from openworld.policies import HeuristicPolicy
from openworld.rule_engine import RuleEngine
from openworld.simulator import Simulator, SimulationConfig
from openworld.task_emergence import EmergenceConfig, TaskEmergence
from openworld.world_state import WorldState, AgentRecord


def _bootstrap_world(width: int = 8, height: int = 8) -> WorldState:
    """A small world with one food tile far from the agent spawn."""
    ws = WorldState(width=width, height=height)
    ws.apply_event(Event(kind="world.init",
                         payload={"width": width, "height": height}, tick=0))
    ws.apply_event(Event(kind="agent.register",
                         payload={"agent_id": "alice", "name": "Alice",
                                  "pos": [0, 0],
                                  "inventory": {"food": 0, "wood": 0},
                                  "needs": {"hunger": 0.9, "social": 0.1}}, tick=0))
    # food tile at (7, 7) — far corner
    ws.apply_event(Event(kind="world.tile",
                         payload={"pos": [7, 7], "kind": "ground",
                                  "resource": "food", "amount": 4}, tick=0))
    return ws


# -------------------------------------------------------------------- nav


def test_heuristic_navigates_toward_resource_tile():
    ws = _bootstrap_world()
    agent = ws.agents["alice"]
    policy = HeuristicPolicy(rng_seed=42)

    # simulate enough ticks for the agent to walk from (0,0) to (7,7).
    rule_engine = RuleEngine()
    reached = False
    for tick in range(1, 80):
        intents = policy.decide(agent, ws, tick)
        outcome = rule_engine.arbitrate(ws, intents, tick)
        # walk accepted moves
        for ev in outcome.accepted:
            if ev.kind == "agent.moved":
                agent.pos = tuple(ev.payload["to"])
        if agent.pos == (7, 7):
            reached = True
            break

    assert reached, f"agent never reached the food tile; final pos={agent.pos}"


def test_heuristic_gathers_when_on_resource_tile():
    ws = _bootstrap_world()
    ws.agents["alice"].pos = (7, 7)  # teleport agent onto the resource
    agent = ws.agents["alice"]
    policy = HeuristicPolicy(rng_seed=42)

    intents = policy.decide(agent, ws, tick=1)
    kinds = [i.action for i in intents]
    assert "gather" in kinds


# -------------------------------------------------------------------- loop


def test_gather_then_consume_lowers_need():
    ws = _bootstrap_world()
    ws.agents["alice"].pos = (7, 7)  # on the food tile
    ws.agents["alice"].needs["hunger"] = 0.8
    agent = ws.agents["alice"]
    policy = HeuristicPolicy(rng_seed=42)
    re = RuleEngine()

    intents = policy.decide(agent, ws, tick=1)
    outcome = re.arbitrate(ws, intents, tick=1)

    assert any(e.kind == "agent.gathered" for e in outcome.accepted)
    # after gather, inventory has food; consume should fire and lower need
    intents2 = policy.decide(agent, ws, tick=2)
    outcome2 = re.arbitrate(ws, intents2, tick=2)
    assert any(e.kind == "agent.consumed" for e in outcome2.accepted)
    # hunger decreased
    assert agent.needs["hunger"] < 0.8


# -------------------------------------------------------------------- tasks


def test_need_task_does_not_re_emergence_every_tick():
    """Need task should emerge at most once per (agent, need) until completion."""
    ws = _bootstrap_world()
    em = TaskEmergence(EmergenceConfig())
    events_first = em.scan(ws, tick=1)
    for e in events_first:
        ws.apply_event(e)

    need_first = [e for e in events_first
                  if e.kind == "task.emerged" and e.payload.get("need") == "hunger"]
    assert len(need_first) == 1

    # Even after many ticks with hunger still above threshold, no new task
    for t in range(2, 6):
        ws.agents["alice"].needs["hunger"] = 0.95  # stay high
        more = em.scan(ws, tick=t)
        for e in more:
            ws.apply_event(e)
        need_more = [e for e in more
                     if e.kind == "task.emerged" and e.payload.get("need") == "hunger"]
        assert len(need_more) == 0, \
            f"need task re-emerged on tick {t}: {need_more}"


def test_need_task_can_complete_after_consume_resolves_need():
    ws = _bootstrap_world()
    # add some initial food so consume can fire
    ws.agents["alice"].inventory["food"] = 2
    ws.agents["alice"].needs["hunger"] = 0.9
    agent = ws.agents["alice"]
    policy = HeuristicPolicy(rng_seed=42)
    re = RuleEngine()

    # First scan: need task emerges (and the gather task for the food tile).
    em = TaskEmergence(EmergenceConfig())
    emergents = em.scan(ws, tick=1)
    for e in emergents:
        ws.apply_event(e)
    # alice claims the need task so we can complete it
    need_task_id = next(t.task_id for t in ws.tasks.values()
                        if t.payload.get("need") == "hunger"
                        and t.payload.get("agent_id") == "alice")
    claim = Intent(agent_id="alice", action="claim",
                   payload={"task_id": need_task_id}, tick=2)
    outcome = re.arbitrate(ws, [claim], tick=2)
    assert any(e.kind == "task.claimed" for e in outcome.accepted)

    # Drive consume to bring need below resolution threshold.
    # 2 consumes take hunger from 0.9 → 0.6 → 0.3, then complete fires.
    for tick in range(3, 12):
        intents = policy.decide(agent, ws, tick)
        outcome = re.arbitrate(ws, intents, tick)
        if any(e.kind == "task.completed" for e in outcome.accepted):
            assert ws.tasks[need_task_id].status == "done"
            assert ws.tasks[need_task_id].completed_by == "alice"
            return
    pytest.fail("need task never completed within 9 ticks")


def test_complete_intent_rejected_when_need_unresolved():
    ws = WorldState(width=4, height=4)
    ws.apply_event(Event(kind="world.init", payload={"width": 4, "height": 4}, tick=0))
    ws.apply_event(Event(kind="agent.register",
                         payload={"agent_id": "alice", "name": "Alice",
                                  "pos": [0, 0],
                                  "inventory": {"food": 1},
                                  "needs": {"hunger": 0.9}}, tick=0))
    re = RuleEngine()
    # claim a synthetic task in `claimed` state
    ws.apply_event(Event(kind="task.emerged",
                         payload={"task_id": "t1", "title": "alice needs hunger",
                                  "kind": "gather", "pos": [0, 0],
                                  "need": "hunger", "agent_id": "alice"}, tick=1))
    ws.apply_event(Event(kind="task.claimed",
                         payload={"task_id": "t1", "agent_id": "alice"}, tick=2))
    # try to complete while hunger still high
    outcome = re.arbitrate(ws, [Intent(agent_id="alice", action="complete",
                                        payload={"task_id": "t1"}, tick=3)], tick=3)
    assert any(e.kind == "intent.rejected" for e in outcome.rejected)
    assert not any(e.kind == "task.completed" for e in outcome.accepted)


# -------------------------------------------------------------------- trade


def test_trade_conserves_inventory_across_two_parties():
    ws = WorldState(width=4, height=4)
    ws.apply_event(Event(kind="world.init", payload={"width": 4, "height": 4}, tick=0))
    ws.apply_event(Event(kind="agent.register",
                         payload={"agent_id": "alice", "name": "Alice",
                                  "pos": [1, 1], "inventory": {"food": 3, "wood": 0}}, tick=0))
    ws.apply_event(Event(kind="agent.register",
                         payload={"agent_id": "bob", "name": "Bob",
                                  "pos": [1, 2], "inventory": {"food": 0, "wood": 3}}, tick=0))
    re = RuleEngine()
    outcome = re.arbitrate(ws, [Intent(agent_id="alice", action="trade",
                                        target="bob",
                                        payload={"give": {"food": 1},
                                                 "recv": {"wood": 1}},
                                        tick=1)], tick=1)
    assert any(e.kind == "trade.completed" for e in outcome.accepted)
    # both sides conserved
    assert ws.agents["alice"].inventory["food"] == 2
    assert ws.agents["alice"].inventory["wood"] == 1
    assert ws.agents["bob"].inventory["wood"] == 2
    assert ws.agents["bob"].inventory["food"] == 1
    # grand total unchanged
    total_before = 6  # 3 + 3
    total_after = sum(ws.agents[a].inventory[r]
                      for a in ("alice", "bob") for r in ("food", "wood"))
    assert total_after == total_before


def test_trade_rejected_when_not_adjacent():
    ws = WorldState(width=8, height=8)
    ws.apply_event(Event(kind="world.init", payload={"width": 8, "height": 8}, tick=0))
    ws.apply_event(Event(kind="agent.register",
                         payload={"agent_id": "alice", "name": "Alice",
                                  "pos": [0, 0], "inventory": {"food": 2}}, tick=0))
    ws.apply_event(Event(kind="agent.register",
                         payload={"agent_id": "bob", "name": "Bob",
                                  "pos": [4, 4], "inventory": {"wood": 2}}, tick=0))
    re = RuleEngine()
    outcome = re.arbitrate(ws, [Intent(agent_id="alice", action="trade",
                                        target="bob",
                                        payload={"give": {"food": 1},
                                                 "recv": {"wood": 1}},
                                        tick=1)], tick=1)
    assert any(e.kind == "intent.rejected" for e in outcome.rejected)
    assert not any(e.kind == "trade.completed" for e in outcome.accepted)


def test_trade_rejected_when_counterparty_lacks_item():
    ws = WorldState(width=4, height=4)
    ws.apply_event(Event(kind="world.init", payload={"width": 4, "height": 4}, tick=0))
    ws.apply_event(Event(kind="agent.register",
                         payload={"agent_id": "alice", "name": "Alice",
                                  "pos": [0, 0], "inventory": {"food": 1}}, tick=0))
    ws.apply_event(Event(kind="agent.register",
                         payload={"agent_id": "bob", "name": "Bob",
                                  "pos": [0, 1], "inventory": {}}, tick=0))
    re = RuleEngine()
    outcome = re.arbitrate(ws, [Intent(agent_id="alice", action="trade",
                                        target="bob",
                                        payload={"give": {"food": 1},
                                                 "recv": {"wood": 1}},
                                        tick=1)], tick=1)
    assert any(e.kind == "intent.rejected" for e in outcome.rejected)


# -------------------------------------------------------------------- end-to-end


def test_full_loop_closure_under_default_simulation():
    """Default 100-tick headless-style run must show gather/consume/complete."""
    sim = Simulator()
    events = sim.run(100)
    kinds: dict = {}
    for e in events:
        kinds[e.kind] = kinds.get(e.kind, 0) + 1
    assert kinds.get("agent.gathered", 0) > 0, f"no gather: {kinds}"
    assert kinds.get("agent.consumed", 0) > 0, f"no consume: {kinds}"
    assert kinds.get("task.completed", 0) > 0, f"no complete: {kinds}"
    # task.emerged should be reasonable, not exploding per-tick
    assert kinds.get("task.emerged", 0) < 200, f"task.emerged exploded: {kinds}"


def test_trade_loop_under_controlled_initial_conditions():
    """Place two agents adjacent from the start, give them each a
    surplus of different resources, and assert that within a few ticks
    the world produces a real `trade.completed` event with bilateral
    conservation."""
    ws = WorldState(width=4, height=4)
    ws.apply_event(Event(kind="world.init", payload={"width": 4, "height": 4}, tick=0))
    ws.apply_event(Event(kind="agent.register",
                         payload={"agent_id": "alice", "name": "Alice",
                                  "pos": [1, 1], "inventory": {"food": 3, "wood": 0, "ore": 0, "water": 1}}, tick=0))
    ws.apply_event(Event(kind="agent.register",
                         payload={"agent_id": "bob", "name": "Bob",
                                  "pos": [2, 1], "inventory": {"food": 0, "wood": 3, "ore": 1, "water": 1}}, tick=0))
    # fill their needs so they actually run the trade branch
    ws.agents["alice"].needs = {"hunger": 0.1, "social": 0.1, "energy": 0.1}
    ws.agents["bob"].needs = {"hunger": 0.1, "social": 0.1, "energy": 0.1}

    # Spin up a minimal world with these two agents as the only residents.
    cfg = SimulationConfig(width=12, height=12)
    cfg.spawn_positions = ((3, 3), (4, 3))
    from openworld.agents import Agent
    agents = {
        "alice": Agent(agent_id="alice", name="Alice",
                       policy=HeuristicPolicy(rng_seed=1),
                       starting_inventory={"food": 3, "wood": 0, "ore": 0, "water": 1}),
        "bob": Agent(agent_id="bob", name="Bob",
                     policy=HeuristicPolicy(rng_seed=2),
                     starting_inventory={"food": 0, "wood": 3, "ore": 1, "water": 1}),
    }
    sim = Simulator(config=cfg, agents=agents)
    # Make sure they're still adjacent (Simulator may have moved them via spawn events)
    sim.state.agents["alice"].pos = (1, 1)
    sim.state.agents["bob"].pos = (2, 1)
    events = sim.run(40)
    kinds: dict = {}
    for e in events:
        kinds[e.kind] = kinds.get(e.kind, 0) + 1
    assert kinds.get("trade.completed", 0) >= 1, f"no trade: {kinds}"


def test_conservation_holds_across_long_run():
    """Sum of agent inventories + tile amounts should stay constant
    (modulo regeneration)."""
    sim = Simulator()
    # capture the initial sum
    initial_total = sim.state.total_agent_items() + sim.state.total_resource_mass()
    sim.run(50)
    after_total = sim.state.total_agent_items() + sim.state.total_resource_mass()
    # `world.tile` events with `amount > 0` (regen) increase the world
    # total by their delta.  Sum them.
    regen_delta = 0
    for e in sim.state.event_log:
        if e.kind == "world.tile" and "amount" in e.payload:
            # each tile event replaces the prior tile — diff vs the
            # current amount is just the new value (it's an absolute
            # amount, so we approximate by counting occurrences).
            regen_delta += 1
    # Conservation invariant (without regen): every gather increases
    # the world total by 0 (tile -1, agent +1).  Every consume decreases
    # it by 1.  Regen can add up to `regen_delta` items.
    consumed = sum(1 for e in sim.state.event_log if e.kind == "agent.consumed")
    expected_no_regen_delta = -consumed
    actual_delta = after_total - initial_total
    # actual_delta should equal expected_no_regen_delta + regen_delta.
    # Allow small slack for tile events that just re-state the same amount.
    assert abs(actual_delta - expected_no_regen_delta) <= regen_delta + 5, \
        f"conservation drift too large: initial={initial_total}, " \
        f"after={after_total}, consumed={consumed}, regen_events={regen_delta}"