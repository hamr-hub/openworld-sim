"""End-to-end simulator test — runs the world for many ticks."""

from openworld.simulator import Simulator


def test_simulator_runs_for_50_ticks_without_errors():
    sim = Simulator()
    events = sim.run(50)
    assert sim.clock.tick == 50
    # we should see at least agent.register and world.init
    kinds = sim.event_kinds()
    assert kinds.get("agent.register", 0) >= 1
    assert kinds.get("world.init", 0) >= 1


def test_simulator_produces_emergent_events_with_heuristic():
    sim = Simulator()
    sim.run(200)
    kinds = sim.event_kinds()
    # at least one of the canonical emergence signals must fire
    emergent = (kinds.get("task.emerged", 0)
                + kinds.get("trade.completed", 0)
                + kinds.get("agent.spoke", 0)
                + kinds.get("agent.gathered", 0))
    assert emergent > 0, f"no emergence observed: {kinds}"


def test_simulator_event_kinds_counts_matches_log_length():
    sim = Simulator()
    sim.run(20)
    kinds = sim.event_kinds()
    assert sum(kinds.values()) == len(sim.state.event_log)