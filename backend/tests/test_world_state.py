"""Tests for WorldState (event log replay, snapshot)."""

from openworld.events import Event
from openworld.world_state import WorldState


def _bootstrap_state() -> WorldState:
    ws = WorldState(width=4, height=4)
    ws.apply_event(Event(kind="world.init",
                          payload={"width": 4, "height": 4}, tick=0))
    return ws


def test_world_init_event_resizes_grid():
    ws = WorldState(width=8, height=8)
    ws.apply_event(Event(kind="world.init",
                          payload={"width": 3, "height": 3}, tick=0))
    assert ws.width == 3
    assert ws.height == 3


def test_event_log_is_append_only():
    ws = _bootstrap_state()
    initial = len(ws.event_log)
    ws.apply_event(Event(kind="agent.register",
                          payload={"agent_id": "a1", "name": "Alice"}, tick=1))
    assert len(ws.event_log) == initial + 1
    # events have unique ids
    assert len({e.event_id for e in ws.event_log}) == len(ws.event_log)


def test_snapshot_contains_required_fields():
    ws = _bootstrap_state()
    ws.apply_event(Event(kind="agent.register",
                          payload={"agent_id": "a1", "name": "Alice",
                                   "pos": [1, 1]}, tick=1))
    snap = ws.snapshot()
    assert "tick" in snap
    assert "width" in snap and snap["width"] == 4
    assert "height" in snap and snap["height"] == 4
    assert len(snap["agents"]) == 1
    assert snap["agents"][0]["agent_id"] == "a1"


def test_replay_from_log_reproduces_state():
    events = [
        Event(kind="world.init", payload={"width": 4, "height": 4}, tick=0),
        Event(kind="agent.register",
              payload={"agent_id": "a1", "name": "Alice", "pos": [0, 0],
                       "inventory": {"food": 1}, "needs": {"hunger": 0.5}},
              tick=0),
        Event(kind="agent.moved",
              payload={"agent_id": "a1", "from": [0, 0], "to": [1, 1]}, tick=1),
        Event(kind="agent.consumed",
              payload={"agent_id": "a1", "resource": "food", "need": "hunger"}, tick=2),
    ]
    ws = WorldState.replay(events)
    assert ws.agents["a1"].pos == (1, 1)
    assert ws.agents["a1"].inventory.get("food") == 0
    assert ws.agents["a1"].needs.get("hunger", 1.0) < 0.5
    # replay from subset
    ws2 = WorldState.replay(events[:2])
    assert ws2.agents["a1"].pos == (0, 0)
    assert ws2.agents["a1"].inventory.get("food") == 1


def test_in_bounds_check():
    ws = WorldState(width=4, height=4)
    assert ws.in_bounds((0, 0))
    assert ws.in_bounds((3, 3))
    assert not ws.in_bounds((-1, 0))
    assert not ws.in_bounds((4, 0))


def test_tile_set_and_get():
    ws = WorldState(width=4, height=4)
    from openworld.world_state import Tile
    ws.set_tile((1, 1), Tile(kind="water"))
    assert ws.get_tile((1, 1)).kind == "water"