"""Tests for TaskEmergence — tasks emerge from state, not scripts."""

from openworld.events import Event
from openworld.task_emergence import EmergenceConfig, TaskEmergence
from openworld.world_state import WorldState


def _world_with_agent_and_resource(hunger: float = 0.1, resource: str = "wood") -> WorldState:
    ws = WorldState(width=6, height=6)
    ws.apply_event(Event(kind="world.init", payload={"width": 6, "height": 6}, tick=0))
    ws.apply_event(Event(kind="agent.register",
                          payload={"agent_id": "alice", "name": "Alice",
                                   "pos": [2, 2],
                                   "needs": {"hunger": hunger, "social": 0.1}},
                          tick=0))
    ws.apply_event(Event(kind="world.tile",
                          payload={"pos": [4, 4], "kind": "ground",
                                   "resource": resource, "amount": 3}, tick=0))
    return ws


def test_gather_task_emerge_for_resource_with_no_one_on_tile():
    ws = _world_with_agent_and_resource()
    em = TaskEmergence(EmergenceConfig())
    events = em.scan(ws, tick=1)
    kinds = [e.kind for e in events]
    assert "task.emerged" in kinds
    # check at least one gather task at the resource pos
    gather_tasks = [e.payload for e in events if e.payload.get("kind") == "gather"]
    assert len(gather_tasks) >= 1
    assert gather_tasks[0]["pos"] == [4, 4]


def test_no_duplicate_gather_task_for_same_pos():
    ws = _world_with_agent_and_resource()
    em = TaskEmergence(EmergenceConfig())
    em.scan(ws, tick=1)
    # apply first scan results
    for e in em.scan(ws, tick=1):
        ws.apply_event(e)
    events2 = em.scan(ws, tick=2)
    gather_for_resource = [e for e in events2
                            if e.kind == "task.emerged"
                            and e.payload.get("kind") == "gather"
                            and e.payload.get("pos") == [4, 4]]
    assert len(gather_for_resource) == 0


def test_no_gather_task_if_agent_already_on_tile():
    ws = WorldState(width=6, height=6)
    ws.apply_event(Event(kind="world.init", payload={"width": 6, "height": 6}, tick=0))
    ws.apply_event(Event(kind="agent.register",
                          payload={"agent_id": "alice", "name": "Alice",
                                   "pos": [4, 4]}, tick=0))
    ws.apply_event(Event(kind="world.tile",
                          payload={"pos": [4, 4], "kind": "ground",
                                   "resource": "wood", "amount": 3}, tick=0))
    em = TaskEmergence(EmergenceConfig())
    events = em.scan(ws, tick=1)
    gather_for_resource = [e for e in events
                            if e.kind == "task.emerged" and e.payload.get("kind") == "gather"]
    assert len(gather_for_resource) == 0


def test_max_open_tasks_is_respected():
    ws = WorldState(width=10, height=10)
    ws.apply_event(Event(kind="world.init", payload={"width": 10, "height": 10}, tick=0))
    # 8 agents with high hunger
    for i in range(8):
        ws.apply_event(Event(kind="agent.register",
                              payload={"agent_id": f"a{i}", "name": f"A{i}",
                                       "pos": [i, 0],
                                       "needs": {"hunger": 0.99, "social": 0.99}},
                              tick=0))
    em = TaskEmergence(EmergenceConfig(max_open_tasks=3))
    for e in em.scan(ws, tick=1):
        ws.apply_event(e)
    open_count = sum(1 for t in ws.tasks.values() if t.status == "open")
    assert open_count <= 3


def test_need_baseline_at_high_hunger_emits_gather_task():
    ws = _world_with_agent_and_resource(hunger=0.8)
    em = TaskEmergence(EmergenceConfig())
    events = em.scan(ws, tick=1)
    need_tasks = [e for e in events
                   if e.kind == "task.emerged" and "hunger" in e.payload.get("title", "").lower()]
    assert len(need_tasks) >= 1


def test_no_emergence_below_threshold():
    ws = _world_with_agent_and_resource(hunger=0.2)
    em = TaskEmergence(EmergenceConfig())
    events = em.scan(ws, tick=1)
    need_tasks = [e for e in events
                   if e.kind == "task.emerged" and "hunger" in e.payload.get("title", "").lower()]
    assert len(need_tasks) == 0