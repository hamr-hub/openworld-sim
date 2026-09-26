"""FastAPI + WebSocket server.

* `GET /`         — health / version
* `GET /snapshot` — current world snapshot (JSON)
* `GET /events`   — paged event log
* `WS /stream`    — live tick stream: snapshot every tick + recent events

The server does *not* drive ticks; a background task advances the simulator
at `OPENWORLD_TICK_MS` (default 800ms).  Subscribers get every snapshot
they can handle — the simulator is happy if a subscriber is slow, since
the bus uses fire-and-forget with per-subscriber isolation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from .simulator import Simulator


log = logging.getLogger("openworld.server")


_simulator: Simulator | None = None
_loop_task: asyncio.Task | None = None
_subscribers: list[WebSocket] = []
_tick_ms: int = int(os.environ.get("OPENWORLD_TICK_MS", "800"))


async def _broadcast(payload: dict) -> None:
    dead: list[WebSocket] = []
    data = json.dumps(payload, default=str)
    for ws in list(_subscribers):
        try:
            await ws.send_text(data)
        except Exception:  # noqa: BLE001
            dead.append(ws)
    for ws in dead:
        try:
            _subscribers.remove(ws)
        except ValueError:
            pass


async def _drive_loop() -> None:
    assert _simulator is not None
    interval = _tick_ms / 1000.0
    while True:
        await asyncio.sleep(interval)
        events = _simulator.step()
        snapshot = _simulator.state.snapshot()
        recent = [
            {"kind": e.kind, "payload": e.payload, "tick": e.tick}
            for e in events[-20:]
        ]
        await _broadcast({"type": "tick", "snapshot": snapshot, "events": recent})


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _simulator, _loop_task
    _simulator = Simulator()
    _loop_task = asyncio.create_task(_drive_loop())
    try:
        yield
    finally:
        if _loop_task is not None:
            _loop_task.cancel()
        _subscribers.clear()


app = FastAPI(title="OpenWorld Sim", version="0.1.0", lifespan=lifespan)


@app.get("/")
def root():
    return {"service": "openworld-sim", "version": "0.1.0",
            "tick": _simulator.clock.tick if _simulator else 0}


@app.get("/snapshot")
def snapshot():
    if _simulator is None:
        return JSONResponse({"error": "not ready"}, status_code=503)
    return _simulator.state.snapshot()


@app.get("/events")
def events(limit: int = 50):
    if _simulator is None:
        return JSONResponse({"error": "not ready"}, status_code=503)
    log_list = _simulator.state.event_log[-limit:]
    return [
        {"kind": e.kind, "payload": e.payload, "tick": e.tick, "event_id": e.event_id}
        for e in log_list
    ]


@app.get("/stats")
def stats():
    if _simulator is None:
        return JSONResponse({"error": "not ready"}, status_code=503)
    return {
        "tick": _simulator.clock.tick,
        "event_count": len(_simulator.state.event_log),
        "kinds": _simulator.event_kinds(),
        "agent_count": len(_simulator.state.agents),
        "task_count": len(_simulator.state.tasks),
    }


@app.websocket("/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    _subscribers.append(ws)
    # send initial snapshot
    if _simulator is not None:
        await ws.send_text(json.dumps({
            "type": "hello",
            "snapshot": _simulator.state.snapshot(),
        }, default=str))
    try:
        while True:
            # we don't expect inbound messages; receive keeps the
            # connection alive and lets us detect a clean close.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        try:
            _subscribers.remove(ws)
        except ValueError:
            pass


def main() -> None:
    """Entrypoint for `python -m openworld.server`."""
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()