"""World state — event-sourced materialised view.

The state is a pure function of the Event log:
    state_n+1 = reduce(apply_event, state_n, events_n)

This gives us:
    * replay-ability: any prefix of the log reproduces any past state
    * deterministic simulation: given the same Intents and rules, the same
      Event sequence always yields the same state
    * audit-ability: who did what when, traceable to an Intent id
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .events import Event


Coord = Tuple[int, int]


@dataclass
class Tile:
    kind: str = "ground"          # ground | water | wall | resource
    resource: Optional[str] = None  # e.g. "wood", "ore", "food", "water"
    amount: int = 0


@dataclass
class AgentRecord:
    agent_id: str
    name: str = ""
    pos: Coord = (0, 0)
    inventory: Dict[str, int] = field(default_factory=dict)
    needs: Dict[str, float] = field(default_factory=dict)  # hunger, social, energy, ...
    goals: List[str] = field(default_factory=list)
    memory_short: List[str] = field(default_factory=list)   # last few observed events
    relationships: Dict[str, float] = field(default_factory=dict)  # affinity by agent_id


@dataclass
class TaskRecord:
    task_id: str
    title: str
    kind: str                  # "gather", "mediate", "deliver", "explore", ...
    pos: Coord
    status: str = "open"       # open | claimed | done | failed
    claimed_by: Optional[str] = None
    completed_by: Optional[str] = None
    reward: Dict[str, Any] = field(default_factory=dict)
    # Original `task.emerged` payload — kept so RuleEngine/heuristic can inspect
    # `need` / `agent_id` / `resource` etc. without grepping the event log.
    payload: Dict[str, Any] = field(default_factory=dict)


class WorldState:
    """Materialised world state, reducible from an Event log."""

    def __init__(self, width: int = 12, height: int = 12) -> None:
        self.width = width
        self.height = height
        self.grid: List[List[Tile]] = [
            [Tile(kind="ground") for _ in range(width)] for _ in range(height)
        ]
        self.agents: Dict[str, AgentRecord] = {}
        self.tasks: Dict[str, TaskRecord] = {}
        self.event_log: List[Event] = []

    # ------------------------------------------------------------------ tiles

    def in_bounds(self, pos: Coord) -> bool:
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height

    def get_tile(self, pos: Coord) -> Tile:
        x, y = pos
        return self.grid[y][x]

    def set_tile(self, pos: Coord, tile: Tile) -> None:
        x, y = pos
        self.grid[y][x] = tile

    # ------------------------------------------------------------- apply log

    def apply_event(self, event: Event) -> None:
        """Fold one event into the state.  Pure — depends only on `event`."""
        self.event_log.append(event)
        kind = event.kind
        p = event.payload

        if kind == "world.init":
            self._init_grid(p.get("width", self.width), p.get("height", self.height))
        elif kind == "world.tile":
            x, y = p["pos"]
            self.set_tile((x, y), Tile(kind=p.get("kind", "ground"),
                                       resource=p.get("resource"),
                                       amount=int(p.get("amount", 0))))
        elif kind == "agent.register":
            self.agents[p["agent_id"]] = AgentRecord(
                agent_id=p["agent_id"],
                name=p.get("name", p["agent_id"]),
                pos=tuple(p.get("pos", (0, 0))),
                inventory=dict(p.get("inventory", {})),
                needs=dict(p.get("needs", {"hunger": 0.2, "social": 0.2, "energy": 0.2})),
                goals=list(p.get("goals", [])),
            )
        elif kind == "agent.moved":
            aid = p["agent_id"]
            if aid in self.agents:
                self.agents[aid].pos = tuple(p["to"])
                self.agents[aid].memory_short.append(
                    f"moved to {p['to']} @ t{event.tick}"
                )
        elif kind == "agent.spoke":
            aid = p["agent_id"]
            target = p.get("target")
            if aid in self.agents:
                self.agents[aid].memory_short.append(
                    f"said {p['text']!r} to {target or 'all'} @ t{event.tick}"
                )
            if target and target in self.agents:
                # receiving agent hears
                self.agents[target].memory_short.append(
                    f"heard {p['text']!r} from {aid} @ t{event.tick}"
                )
                # relationship nudge — positive if content carries offer/help word
                if any(w in p["text"].lower() for w in ("help", "share", "trade", "please")):
                    self.agents[target].relationships[aid] = \
                        self.agents[target].relationships.get(aid, 0.0) + 0.1
        elif kind == "agent.gathered":
            aid = p["agent_id"]
            res = p["resource"]
            qty = int(p.get("qty", 1))
            if aid in self.agents:
                self.agents[aid].inventory[res] = self.agents[aid].inventory.get(res, 0) + qty
        elif kind == "agent.consumed":
            aid = p["agent_id"]
            res = p["resource"]
            if aid in self.agents and self.agents[aid].inventory.get(res, 0) > 0:
                self.agents[aid].inventory[res] -= 1
                self.agents[aid].needs[p.get("need", "hunger")] = max(
                    0.0, self.agents[aid].needs.get(p.get("need", "hunger"), 0.0) - 0.3
                )
        elif kind == "trade.completed":
            a, b = p["from"], p["to"]
            give, recv = p["give"], p["recv"]
            if a in self.agents and b in self.agents:
                for r, q in give.items():
                    self.agents[a].inventory[r] = self.agents[a].inventory.get(r, 0) - q
                for r, q in recv.items():
                    self.agents[a].inventory[r] = self.agents[a].inventory.get(r, 0) + q
                for r, q in give.items():
                    self.agents[b].inventory[r] = self.agents[b].inventory.get(r, 0) + q
                for r, q in recv.items():
                    self.agents[b].inventory[r] = self.agents[b].inventory.get(r, 0) - q
                # mutual relationship bump
                self.agents[a].relationships[b] = self.agents[a].relationships.get(b, 0.0) + 0.2
                self.agents[b].relationships[a] = self.agents[b].relationships.get(a, 0.0) + 0.2
        elif kind == "task.emerged":
            # Store the full payload (sans structural keys) so subsequent
            # heuristics / rule checks can read e.g. `need`, `agent_id`.
            stored_payload = {
                k: v for k, v in p.items()
                if k not in ("task_id", "title", "kind", "pos", "reward")
            }
            self.tasks[p["task_id"]] = TaskRecord(
                task_id=p["task_id"], title=p["title"], kind=p["kind"],
                pos=tuple(p["pos"]), reward=dict(p.get("reward", {})),
                payload=stored_payload,
            )
        elif kind == "task.claimed":
            if p["task_id"] in self.tasks:
                self.tasks[p["task_id"]].status = "claimed"
                self.tasks[p["task_id"]].claimed_by = p["agent_id"]
        elif kind == "task.completed":
            if p["task_id"] in self.tasks:
                self.tasks[p["task_id"]].status = "done"
                self.tasks[p["task_id"]].completed_by = p.get("completed_by")
                # social bump for the resolver
                resolver = p.get("completed_by")
                if resolver and resolver in self.agents:
                    self.agents[resolver].relationships[resolver] = \
                        self.agents[resolver].relationships.get(resolver, 0.0) + 0.05
        elif kind == "task.failed":
            if p["task_id"] in self.tasks:
                self.tasks[p["task_id"]].status = "failed"
        elif kind == "conflict.broke":
            a, b = p["a"], p["b"]
            if a in self.agents and b in self.agents:
                self.agents[a].relationships[b] = self.agents[a].relationships.get(b, 0.0) - 0.4
                self.agents[b].relationships[a] = self.agents[b].relationships.get(a, 0.0) - 0.4
        # unknown kinds are kept in the log but ignored by state — forward-compat

    def _init_grid(self, w: int, h: int) -> None:
        self.width, self.height = w, h
        self.grid = [[Tile(kind="ground") for _ in range(w)] for _ in range(h)]

    # ---------------------------------------------------------------- helpers

    def snapshot(self) -> Dict[str, Any]:
        """Serialisable snapshot for the WebSocket layer."""
        return {
            "tick": len(self.event_log),
            "width": self.width,
            "height": self.height,
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "name": a.name,
                    "pos": a.pos,
                    "inventory": a.inventory,
                    "needs": a.needs,
                    "goals": a.goals,
                    "memory_short": a.memory_short[-5:],
                }
                for a in self.agents.values()
            ],
            "tasks": [
                {
                    "task_id": t.task_id,
                    "title": t.title,
                    "kind": t.kind,
                    "pos": t.pos,
                    "status": t.status,
                    "claimed_by": t.claimed_by,
                    "completed_by": t.completed_by,
                }
                for t in self.tasks.values()
            ],
            "event_count": len(self.event_log),
        }

    def total_resource_mass(self) -> int:
        """Sum of all resource amounts currently on the map (for conservation checks)."""
        return sum(t.amount for row in self.grid for t in row)

    def total_agent_items(self) -> int:
        """Sum of all items held by all agents (for conservation checks)."""
        return sum(sum(a.inventory.values()) for a in self.agents.values())

    @classmethod
    def replay(cls, events: List[Event], width: int = 12, height: int = 12) -> "WorldState":
        ws = cls(width=width, height=height)
        for e in events:
            ws.apply_event(e)
        return ws