"""Tick clock.

The simulator advances in discrete ticks.  Each tick is one "world step".
Wall-clock pacing is the server's job; the *kernel* advances by tick number,
which is the only canonical time dimension for causality.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Clock:
    tick: int = 0
    """Monotonic world-tick counter.  Strictly increasing."""

    started_at: float = field(default_factory=lambda: __import__("time").time())

    def advance(self) -> int:
        """Advance one tick.  Returns the new tick number."""
        self.tick += 1
        return self.tick

    def reset(self) -> None:
        self.tick = 0
        self.started_at = __import__("time").time()