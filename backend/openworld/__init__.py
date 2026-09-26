"""OpenWorld Sim — backend package.

Layered architecture:
    clock       — tick / wall-clock scheduling
    events      — append-only Event & Intent dataclasses
    world_state — event-sourced state (replay -> snapshot)
    rule_engine — deterministic Intent arbitration
    agents      — first-class citizens: perceive, decide, submit Intent
    task_emergence — tasks emerge from world-state diffs (not scripts)
    policies    — heuristic (default) + LLM (optional, env-gated)
    simulator   — orchestrates a tick
    server      — FastAPI + WebSocket
    headless    — CLI batch runner
"""

__version__ = "0.1.0"