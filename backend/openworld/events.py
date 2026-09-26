"""Event & Intent primitives.

Two streams, both append-only:

    Intent   — an Agent *requests* a world mutation.  Not yet a fact.
    Event    — a fact that has happened in the world.  Immutable.

RuleEngine converts accepted Intents into Events.  WorldState is derived
from the Event log (event sourcing); Intents never mutate state directly.

This is the *seam* between Agent cognition and the world.  Agents cannot
bypass it.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@dataclass
class Intent:
    """An Agent's request to mutate the world.

    The RuleEngine validates this against WorldState and either accepts,
    rejects, or transforms it into an Event (or several).
    """

    agent_id: str
    action: str               # e.g. "move", "speak", "gather", "trade"
    target: Optional[str] = None  # entity or coordinate key
    payload: Dict[str, Any] = field(default_factory=dict)
    tick: int = 0
    intent_id: str = field(default_factory=lambda: _new_id("int"))


@dataclass
class Event:
    """A fact that has happened in the world.

    Append-only.  Never mutated or deleted.  The full log is the source of
    truth; WorldState is a materialised view.
    """

    kind: str                # e.g. "agent.moved", "trade.completed", "task.emerged"
    payload: Dict[str, Any] = field(default_factory=dict)
    tick: int = 0
    caused_by: Optional[str] = None  # intent_id, for traceability
    event_id: str = field(default_factory=lambda: _new_id("evt"))
    timestamp: float = field(default_factory=time.time)


def to_dict(obj: Any) -> Dict[str, Any]:
    return asdict(obj)


class EventBus:
    """In-process pub/sub for Event fan-out (e.g. WebSocket subscribers).

    The bus never *creates* events; that is the RuleEngine's job.
    """

    def __init__(self) -> None:
        self._subscribers: List[Any] = []

    def subscribe(self, callback) -> None:
        self._subscribers.append(callback)

    def unsubscribe(self, callback) -> None:
        try:
            self._subscribers.remove(callback)
        except ValueError:
            pass

    def publish(self, events: List[Event]) -> None:
        for sub in list(self._subscribers):
            try:
                sub(events)
            except Exception:  # noqa: BLE001 — subscriber isolation
                # never let a bad subscriber break the world
                pass

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)