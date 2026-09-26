"""Tests for RuleEngine — Intent arbitration and consistency invariants."""

import pytest

from openworld.events import Event, Intent
from openworld.rule_engine import RuleEngine
from openworld.world_state import WorldState


def _setup():
    ws = WorldState(width=4, height=4)
    ws.apply_event(Event(kind="world.init", payload={"width": 4, "height": 4}, tick=0))
    ws.apply_event(Event(kind="agent.register",
                          payload={"agent_id": "alice", "name": "Alice",
                                   "pos": [0, 0], "inventory": {"food": 2, "wood": 0}},
                          tick=0))
    ws.apply_event(Event(kind="agent.register",
                          payload={"agent_id": "bob", "name": "Bob",
                                   "pos": [3, 3], "inventory": {"food": 0, "wood": 2}},
                          tick=0))
    ws.apply_event(Event(kind="world.tile",
                          payload={"pos": [0, 0], "kind": "ground",
                                   "resource": "wood", "amount": 5}, tick=0))
    return ws


def test_move_accepted_within_bounds():
    ws = _setup()
    re = RuleEngine()
    outcome = re.arbitrate(ws, [Intent(agent_id="alice", action="move",
                                        payload={"to": [1, 0]}, tick=1)], tick=1)
    assert any(e.kind == "agent.moved" for e in outcome.accepted)
    assert outcome.rejected == []


def test_move_rejected_out_of_bounds():
    ws = _setup()
    re = RuleEngine()
    outcome = re.arbitrate(ws, [Intent(agent_id="alice", action="move",
                                        payload={"to": [99, 99]}, tick=1)], tick=1)
    assert any(e.kind == "intent.rejected" for e in outcome.rejected)
    assert all(e.kind != "agent.moved" for e in outcome.accepted)


def test_move_rejected_unknown_agent():
    ws = _setup()
    re = RuleEngine()
    outcome = re.arbitrate(ws, [Intent(agent_id="ghost", action="move",
                                        payload={"to": [1, 1]}, tick=1)], tick=1)
    assert any(e.kind == "intent.rejected" for e in outcome.rejected)


def test_gather_consumes_tile_resource():
    ws = _setup()
    re = RuleEngine()
    outcome = re.arbitrate(ws, [Intent(agent_id="alice", action="gather",
                                        payload={"qty": 2}, tick=1)], tick=1)
    kinds = [e.kind for e in outcome.accepted]
    assert "agent.gathered" in kinds
    # tile depleted by 2
    assert ws.get_tile((0, 0)).amount == 3
    assert ws.agents["alice"].inventory["wood"] == 2


def test_gather_rejected_when_no_resource():
    ws = _setup()
    # move alice to (1,1) — a free cell with no resource
    re = RuleEngine()
    move_outcome = re.arbitrate(ws, [Intent(agent_id="alice", action="move",
                                             payload={"to": [1, 1]}, tick=1)], tick=1)
    assert any(e.kind == "agent.moved" for e in move_outcome.accepted), \
        "alice should be able to move to (1,1)"
    outcome = re.arbitrate(ws, [Intent(agent_id="alice", action="gather",
                                        payload={"qty": 1}, tick=2)], tick=2)
    assert any(e.kind == "intent.rejected" for e in outcome.rejected)


def test_consume_decreases_inventory_and_need():
    ws = _setup()
    re = RuleEngine()
    outcome = re.arbitrate(ws, [Intent(agent_id="alice", action="consume",
                                        payload={"resource": "food", "need": "hunger"},
                                        tick=1)], tick=1)
    assert any(e.kind == "agent.consumed" for e in outcome.accepted)
    assert ws.agents["alice"].inventory["food"] == 1


def test_consume_rejected_when_missing_item():
    ws = _setup()
    re = RuleEngine()
    outcome = re.arbitrate(ws, [Intent(agent_id="alice", action="consume",
                                        payload={"resource": "ore", "need": "hunger"},
                                        tick=1)], tick=1)
    assert any(e.kind == "intent.rejected" for e in outcome.rejected)


def test_trade_requires_both_parties_have_items():
    ws = _setup()
    re = RuleEngine()
    # valid: alice gives food, bob gives wood
    outcome = re.arbitrate(ws, [Intent(agent_id="alice", action="trade",
                                        target="bob",
                                        payload={"give": {"food": 1}, "recv": {"wood": 1}},
                                        tick=1)], tick=1)
    assert any(e.kind == "trade.completed" for e in outcome.accepted)
    assert ws.agents["alice"].inventory["food"] == 1
    assert ws.agents["alice"].inventory["wood"] == 1
    assert ws.agents["bob"].inventory["wood"] == 1
    assert ws.agents["bob"].inventory["food"] == 1


def test_trade_rejected_when_alice_lacks_item():
    ws = _setup()
    re = RuleEngine()
    outcome = re.arbitrate(ws, [Intent(agent_id="alice", action="trade",
                                        target="bob",
                                        payload={"give": {"ore": 5}, "recv": {"wood": 1}},
                                        tick=1)], tick=1)
    assert any(e.kind == "intent.rejected" for e in outcome.rejected)


def test_speak_with_empty_text_rejected():
    ws = _setup()
    re = RuleEngine()
    outcome = re.arbitrate(ws, [Intent(agent_id="alice", action="speak",
                                        payload={"text": ""}, tick=1)], tick=1)
    assert any(e.kind == "intent.rejected" for e in outcome.rejected)


def test_speak_with_long_text_rejected():
    ws = _setup()
    re = RuleEngine()
    outcome = re.arbitrate(ws, [Intent(agent_id="alice", action="speak",
                                        payload={"text": "x" * 300}, tick=1)], tick=1)
    assert any(e.kind == "intent.rejected" for e in outcome.rejected)


def test_move_conflict_two_agents_same_cell():
    ws = _setup()
    # move bob to (1,0) so alice can move to (1,0) too — conflict
    re = RuleEngine()
    intents = [
        Intent(agent_id="alice", action="move", payload={"to": [1, 0]}, tick=1),
        Intent(agent_id="bob",   action="move", payload={"to": [1, 0]}, tick=1),
    ]
    outcome = re.arbitrate(ws, intents, tick=1)
    assert any(e.kind == "conflict.broke" for e in outcome.accepted)
    # exactly one agent.moved accepted
    moved = [e for e in outcome.accepted if e.kind == "agent.moved"]
    assert len(moved) == 1
    # the loser was rejected
    assert any(e.kind == "intent.rejected" for e in outcome.rejected)


def test_unknown_action_rejected():
    ws = _setup()
    re = RuleEngine()
    outcome = re.arbitrate(ws, [Intent(agent_id="alice", action="fly_to_moon",
                                        payload={}, tick=1)], tick=1)
    assert any(e.kind == "intent.rejected" for e in outcome.rejected)


def test_intent_causality_event_has_caused_by():
    ws = _setup()
    re = RuleEngine()
    intent = Intent(agent_id="alice", action="move", payload={"to": [1, 0]}, tick=1)
    outcome = re.arbitrate(ws, [intent], tick=1)
    moved = next(e for e in outcome.accepted if e.kind == "agent.moved")
    assert moved.caused_by == intent.intent_id