/**
 * OpenWorld Sim — frontend entry.
 *
 * Connects to backend via WebSocket (`/stream`); renders the world snapshot
 * to a canvas; shows agent/task/event panels.
 *
 * Pure TS + DOM.  No framework.  No bundler runtime magic beyond Vite.
 */

import './styles.css';

interface AgentView {
  agent_id: string;
  name: string;
  pos: [number, number];
  inventory: Record<string, number>;
  needs: Record<string, number>;
  memory_short: string[];
}

interface TaskView {
  task_id: string;
  title: string;
  kind: string;
  pos: [number, number];
  status: string;
  claimed_by: string | null;
}

interface Snapshot {
  tick: number;
  width: number;
  height: number;
  agents: AgentView[];
  tasks: TaskView[];
  event_count: number;
}

interface StreamEvent {
  kind: string;
  payload: Record<string, unknown>;
  tick: number;
}

interface StreamMessage {
  type: 'hello' | 'tick';
  snapshot?: Snapshot;
  events?: StreamEvent[];
}

const CELL_PX = 40;
const MAX_EVENT_LOG = 50;

class WorldRenderer {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d')!;
  }

  resize(width: number, height: number): void {
    this.canvas.width = width * CELL_PX;
    this.canvas.height = height * CELL_PX;
  }

  render(snap: Snapshot): void {
    const { width, height } = snap;
    this.resize(width, height);
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    // tiles
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const tile = this.tileAt(snap, x, y);
        ctx.fillStyle = tileColor(tile);
        ctx.fillRect(x * CELL_PX, y * CELL_PX, CELL_PX, CELL_PX);
        ctx.strokeStyle = 'rgba(0,0,0,0.07)';
        ctx.strokeRect(x * CELL_PX, y * CELL_PX, CELL_PX, CELL_PX);
      }
    }

    // tasks (markers)
    for (const t of snap.tasks) {
      if (t.status !== 'open') continue;
      const [x, y] = t.pos;
      const cx = x * CELL_PX + CELL_PX / 2;
      const cy = y * CELL_PX + CELL_PX / 2;
      ctx.fillStyle = taskColor(t.kind);
      ctx.beginPath();
      ctx.arc(cx, cy, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#000';
      ctx.font = 'bold 12px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(taskGlyph(t.kind), cx, cy);
    }

    // agents
    for (const a of snap.agents) {
      const [x, y] = a.pos;
      const cx = x * CELL_PX + CELL_PX / 2;
      const cy = y * CELL_PX + CELL_PX / 2;
      const color = invColor(a.inventory);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(cx, cy, 16, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#1a1a1a';
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 14px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(a.name[0]!, cx, cy);
    }
  }

  private tileAt(snap: Snapshot, x: number, y: number): { kind: string; resource?: string } {
    // We don't get tile data in the snapshot (optimization: world view is small).
    // Render agents / tasks first; assume ground everywhere else.
    // Resource dots are drawn separately below.
    for (const a of snap.agents) {
      if (a.pos[0] === x && a.pos[1] === y && Object.keys(a.inventory).length === 0) {
        return { kind: 'occupied' };
      }
    }
    return { kind: 'ground' };
  }
}

// ------------------------- helpers / pure -------------------------------

function tileColor(_tile: { kind: string }): string {
  switch (_tile.kind) {
    case 'wall': return '#3a3a3a';
    case 'water': return '#9bc4e2';
    case 'occupied': return '#d8d4c8';
    default: return '#e8e6e1';
  }
}

function taskColor(kind: string): string {
  switch (kind) {
    case 'gather': return '#4caf50';
    case 'trade': return '#ff9800';
    case 'rest': return '#9e9e9e';
    default: return '#ba68c8';
  }
}

function taskGlyph(kind: string): string {
  switch (kind) {
    case 'gather': return '⛏';
    case 'trade': return '⇄';
    case 'rest': return '☾';
    default: return '?';
  }
}

function invColor(inv: Record<string, number>): string {
  const total = Object.values(inv).reduce((a, b) => a + b, 0);
  if (total === 0) return '#9aa0a6';
  if (total > 4) return '#f5c84b';
  if (total > 2) return '#a78bfa';
  return '#5e7ce2';
}

function kindColor(kind: string): string {
  if (kind.startsWith('trade')) return '#ff9800';
  if (kind.startsWith('agent.spoke')) return '#3f51b5';
  if (kind.startsWith('agent.moved')) return '#2196f3';
  if (kind.startsWith('agent.gathered')) return '#4caf50';
  if (kind.startsWith('agent.consumed')) return '#009688';
  if (kind.startsWith('task.emerged')) return '#ba68c8';
  if (kind.startsWith('task.claimed')) return '#7b1fa2';
  if (kind.startsWith('conflict')) return '#f44336';
  if (kind.startsWith('intent.rejected')) return '#795548';
  return '#607d8b';
}

// ------------------------- app -----------------------------------------

class App {
  private renderer: WorldRenderer;
  private eventListEl: HTMLElement;
  private statsEl: HTMLElement;
  private connectionEl: HTMLElement;
  private agentListEl: HTMLElement;
  private taskListEl: HTMLElement;
  private ws: WebSocket | null = null;
  private reconnectTimer: number | null = null;
  private readonly wsUrl: string;

  constructor(root: HTMLElement) {
    root.innerHTML = `
      <div class="layout">
        <header class="topbar">
          <h1>OpenWorld Sim <span class="sub">— live sandbox</span></h1>
          <div class="conn" id="conn">disconnected</div>
        </header>
        <main class="main">
          <section class="world">
            <canvas id="canvas"></canvas>
            <div class="legend">
              <span><i class="dot inv-full"></i>rich</span>
              <span><i class="dot inv-mid"></i>ok</span>
              <span><i class="dot inv-empty"></i>empty</span>
              <span><i class="dot task-gather"></i>gather</span>
              <span><i class="dot task-trade"></i>trade</span>
            </div>
          </section>
          <aside class="side">
            <div class="panel">
              <h3>Stats</h3>
              <div id="stats">—</div>
            </div>
            <div class="panel">
              <h3>Agents</h3>
              <ul id="agents" class="list"></ul>
            </div>
            <div class="panel">
              <h3>Open tasks</h3>
              <ul id="tasks" class="list"></ul>
            </div>
            <div class="panel grow">
              <h3>Event stream</h3>
              <ul id="events" class="list events"></ul>
            </div>
          </aside>
        </main>
      </div>`;

    const canvas = root.querySelector<HTMLCanvasElement>('#canvas')!;
    this.renderer = new WorldRenderer(canvas);
    this.eventListEl = root.querySelector<HTMLElement>('#events')!;
    this.statsEl = root.querySelector<HTMLElement>('#stats')!;
    this.connectionEl = root.querySelector<HTMLElement>('#conn')!;
    this.agentListEl = root.querySelector<HTMLElement>('#agents')!;
    this.taskListEl = root.querySelector<HTMLElement>('#tasks')!;

    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const host = location.hostname || 'localhost';
    const port = '8000';
    this.wsUrl = `${proto}://${host}:${port}/stream`;
  }

  start(): void {
    this.connect();
  }

  private connect(): void {
    if (this.ws) return;
    this.setConn('connecting…');
    try {
      this.ws = new WebSocket(this.wsUrl);
    } catch (e) {
      this.setConn('ws error: ' + String(e));
      this.scheduleReconnect();
      return;
    }
    this.ws.onopen = () => this.setConn('connected');
    this.ws.onclose = () => {
      this.setConn('disconnected (retry in 2s)');
      this.ws = null;
      this.scheduleReconnect();
    };
    this.ws.onerror = () => this.setConn('ws error');
    this.ws.onmessage = (ev) => this.onMessage(ev);
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 2000);
  }

  private setConn(text: string): void {
    this.connectionEl.textContent = text;
    this.connectionEl.className = 'conn ' + (text.startsWith('connected') ? 'ok' : 'bad');
  }

  private onMessage(ev: MessageEvent): void {
    let msg: StreamMessage;
    try {
      msg = JSON.parse(ev.data);
    } catch {
      return;
    }
    if (msg.type === 'hello' && msg.snapshot) {
      this.applySnapshot(msg.snapshot);
    } else if (msg.type === 'tick') {
      if (msg.snapshot) this.applySnapshot(msg.snapshot);
      if (msg.events) this.appendEvents(msg.events);
    }
  }

  private applySnapshot(snap: Snapshot): void {
    this.renderer.render(snap);
    this.updateStats(snap);
    this.updateAgentList(snap);
    this.updateTaskList(snap);
  }

  private updateStats(snap: Snapshot): void {
    this.statsEl.innerHTML = `
      <div>tick: <b>${snap.tick}</b></div>
      <div>events: <b>${snap.event_count}</b></div>
      <div>agents: <b>${snap.agents.length}</b></div>
      <div>tasks: <b>${snap.tasks.length}</b></div>
    `;
  }

  private updateAgentList(snap: Snapshot): void {
    this.agentListEl.innerHTML = snap.agents.map((a) => {
      const inv = Object.entries(a.inventory).map(([r, q]) => `${r}=${q}`).join(' ');
      const topNeed = Object.entries(a.needs).sort((x, y) => y[1] - x[1])[0];
      return `<li>
        <div class="row"><b>${escapeHtml(a.name)}</b> <span class="pos">@(${a.pos[0]},${a.pos[1]})</span></div>
        <div class="meta">inv: ${escapeHtml(inv) || '—'}</div>
        <div class="meta">need: ${topNeed ? `${topNeed[0]}=${topNeed[1].toFixed(2)}` : '—'}</div>
      </li>`;
    }).join('');
  }

  private updateTaskList(snap: Snapshot): void {
    const open = snap.tasks.filter((t) => t.status === 'open');
    if (open.length === 0) {
      this.taskListEl.innerHTML = '<li class="muted">no open tasks</li>';
      return;
    }
    this.taskListEl.innerHTML = open.slice(0, 12).map((t) => `
      <li>
        <div class="row"><b>${taskGlyph(t.kind)} ${escapeHtml(t.kind)}</b> <span class="pos">@(${t.pos[0]},${t.pos[1]})</span></div>
        <div class="meta">${escapeHtml(t.title)}</div>
      </li>
    `).join('');
  }

  private appendEvents(events: StreamEvent[]): void {
    const li = events.map((e) => {
      const color = kindColor(e.kind);
      const payload = JSON.stringify(e.payload).slice(0, 100);
      return `<li style="border-left-color:${color}">
        <span class="tick">t${e.tick}</span>
        <span class="kind" style="color:${color}">${escapeHtml(e.kind)}</span>
        <span class="payload">${escapeHtml(payload)}</span>
      </li>`;
    }).reverse();
    this.eventListEl.insertAdjacentHTML('afterbegin', li.join(''));
    while (this.eventListEl.children.length > MAX_EVENT_LOG) {
      this.eventListEl.removeChild(this.eventListEl.lastChild!);
    }
  }
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!));
}

// boot
const root = document.getElementById('app')!;
const app = new App(root);
app.start();