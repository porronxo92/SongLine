import { setStoredToken } from '../lib/session';
import type { ClientMessageType, ClientPayloads, ServerMessage } from '../protocol/types';

export type ConnStatus = 'connecting' | 'open' | 'reconnecting';
export type FatalReason = 'not_found' | 'kicked' | 'destroyed' | 'bad_session';

export class WsError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

export interface SocketHandlers {
  onMessage: (msg: ServerMessage) => void;
  onStatus: (status: ConnStatus) => void;
  /** Se llama al abrir el socket, ya enviado `hello`. */
  onOpen: () => void;
  onFatal: (reason: FatalReason) => void;
}

interface Pending {
  resolve: () => void;
  reject: (e: Error) => void;
  timer: ReturnType<typeof setTimeout> | null;
}
interface Envelope {
  type: ClientMessageType;
  id: string;
  payload: unknown;
}

const BACKOFF_MIN_MS = 500;
const BACKOFF_MAX_MS = 8000;
const PING_EVERY_MS = 15000;
const ACK_TIMEOUT_MS = 10000;
const EPHEMERAL: ClientMessageType[] = ['place_preview', 'ping'];

/** Único sitio que construye la URL del WS. Sin token: va en el primer mensaje `hello`. */
export function buildWsUrl(code: string): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}/ws/rooms/${encodeURIComponent(code)}`;
}

function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}`;
}

export class GameSocket {
  private ws: WebSocket | null = null;
  private attempt = 0;
  private stopped = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private readonly pending = new Map<string, Pending>();
  private queue: Envelope[] = [];

  constructor(
    private readonly code: string,
    private readonly getToken: () => string,
    private readonly getLastVersion: () => number,
    private readonly handlers: SocketHandlers,
  ) {}

  start(): void {
    this.stopped = false;
    this.connect();
  }

  stop(): void {
    this.stopped = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.pingTimer) clearInterval(this.pingTimer);
    this.reconnectTimer = null;
    this.pingTimer = null;
    const ws = this.ws;
    this.ws = null;
    if (ws) {
      ws.onopen = ws.onmessage = ws.onclose = ws.onerror = null;
      ws.close();
    }
    for (const [, p] of this.pending) {
      if (p.timer) clearTimeout(p.timer);
      p.reject(new WsError('closed', 'Conexión cerrada'));
    }
    this.pending.clear();
    this.queue = [];
  }

  get isOpen(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /** Envía un mensaje. La promesa se resuelve con `ack` y se rechaza con `error`. */
  send<T extends ClientMessageType>(type: T, payload: ClientPayloads[T]): Promise<void> {
    const env: Envelope = { type, id: uuid(), payload };
    if (!this.isOpen && EPHEMERAL.includes(type)) return Promise.resolve();
    return new Promise<void>((resolve, reject) => {
      this.pending.set(env.id, { resolve, reject, timer: null });
      if (this.isOpen) this.transmit(env);
      else this.queue.push(env);
    });
  }

  private transmit(env: Envelope): void {
    const p = this.pending.get(env.id);
    if (p) {
      p.timer = setTimeout(() => {
        this.pending.delete(env.id);
        p.reject(new WsError('timeout', 'El servidor no responde'));
      }, ACK_TIMEOUT_MS);
    }
    this.ws?.send(JSON.stringify(env));
  }

  private connect(): void {
    if (this.stopped) return;
    this.handlers.onStatus(this.attempt === 0 ? 'connecting' : 'reconnecting');
    const ws = new WebSocket(buildWsUrl(this.code));
    this.ws = ws;
    let opened = false;

    ws.onopen = () => {
      opened = true;
      this.attempt = 0;
      this.handlers.onStatus('open');
      // El servidor espera `hello` como primer mensaje (máx. 5 s); si no, cierra con 4401.
      const hello: Envelope = {
        type: 'hello',
        id: uuid(),
        payload: { session_token: this.getToken(), last_version: this.getLastVersion() },
      };
      ws.send(JSON.stringify(hello));
      const q = this.queue;
      this.queue = [];
      for (const env of q) this.transmit(env);
      this.handlers.onOpen();
      if (this.pingTimer) clearInterval(this.pingTimer);
      this.pingTimer = setInterval(() => {
        void this.send('ping', { t: Date.now() }).catch(() => undefined);
      }, PING_EVERY_MS);
      void this.send('ping', { t: Date.now() }).catch(() => undefined);
    };

    ws.onmessage = (ev: MessageEvent) => {
      if (typeof ev.data !== 'string') return;
      let msg: ServerMessage;
      try {
        msg = JSON.parse(ev.data) as ServerMessage;
      } catch {
        return;
      }
      if (msg.type === 'ack') {
        this.settle(msg.payload.ref_id, null);
      } else if (msg.type === 'error') {
        this.settle(msg.payload.ref_id, new WsError(msg.payload.code, msg.payload.message));
      }
      this.handlers.onMessage(msg);
    };

    ws.onerror = () => {
      /* el cierre se gestiona en onclose */
    };

    ws.onclose = (ev: CloseEvent) => {
      if (this.ws !== ws) return;
      this.ws = null;
      if (this.pingTimer) clearInterval(this.pingTimer);
      this.pingTimer = null;
      if (this.stopped) return;
      if (ev.code === 4404) {
        this.fatal('not_found');
        return;
      }
      if (ev.code === 4401) {
        // Token ausente, mal firmado o de otro servidor: se descarta para pedir una sesión nueva.
        setStoredToken(null);
        this.fatal('bad_session');
        return;
      }
      if (ev.code === 4403) {
        this.fatal('kicked');
        return;
      }
      if (ev.code === 1000 && opened) {
        this.fatal('destroyed');
        return;
      }
      const delay = Math.min(BACKOFF_MAX_MS, BACKOFF_MIN_MS * 2 ** this.attempt);
      this.attempt += 1;
      this.handlers.onStatus('reconnecting');
      this.reconnectTimer = setTimeout(() => {
        this.connect();
      }, delay);
    };
  }

  private fatal(reason: FatalReason): void {
    this.stop();
    this.handlers.onFatal(reason);
  }

  private settle(refId: string, err: Error | null): void {
    const p = this.pending.get(refId);
    if (!p) return;
    this.pending.delete(refId);
    if (p.timer) clearTimeout(p.timer);
    if (err) p.reject(err);
    else p.resolve();
  }
}
