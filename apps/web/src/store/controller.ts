import { ensureSession } from '../api/client';
import { audioHost } from '../audio/host';
import { getStoredToken, setStoredRoom } from '../lib/session';
import type { ClientMessageType, ClientPayloads, ServerMessage } from '../protocol/types';
import { GameSocket, WsError, type ConnStatus, type FatalReason } from '../ws/client';
import { initialRoomState, useRoom } from './room';

let socket: GameSocket | null = null;
let toastSeq = 0;
let joinGen = 0;

function toast(text: string): void {
  toastSeq += 1;
  useRoom.setState({ toast: { id: toastSeq, text } });
}

function handleMessage(msg: ServerMessage): void {
  switch (msg.type) {
    case 'state': {
      const { version, view } = msg.payload;
      const cur = useRoom.getState();
      if (version <= cur.version && cur.code === view.code) return;
      const patch: Partial<typeof cur> = { view, version };
      if (view.phase !== 'reveal' && view.phase !== 'paused') patch.reveal = null;
      if (view.phase === 'turn_ready' || view.phase === 'lobby') patch.turnResolved = null;
      if (view.phase !== 'game_over') patch.gameOver = null;
      if (view.phase !== 'countdown') patch.countdown = null;
      useRoom.setState(patch);
      break;
    }
    case 'pong':
      useRoom.setState({ clockOffset: msg.payload.server_ts - Date.now() / 1000 });
      break;
    case 'reveal':
      useRoom.setState({ reveal: msg.payload });
      break;
    case 'turn_resolved':
      useRoom.setState({ turnResolved: msg.payload });
      break;
    case 'countdown':
      useRoom.setState({
        countdown: { deadlineTs: msg.payload.deadline_ts, firstSlot: msg.payload.first_slot },
      });
      break;
    case 'game_over':
      useRoom.setState({ gameOver: msg.payload });
      break;
    case 'audio_status':
      useRoom.setState({ audioStatus: msg.payload });
      break;
    case 'audio_error':
      useRoom.setState({ audioError: msg.payload });
      break;
    case 'deck_low':
      useRoom.setState({ deckLow: msg.payload.remaining });
      break;
    case 'kicked':
      break;
    case 'audio_command':
      if (useRoom.getState().view?.you.isHost) audioHost.handleCommand(msg.payload.action);
      break;
    case 'ack':
    case 'error':
      break;
  }
}

function onFatal(reason: FatalReason): void {
  if (reason === 'not_found' || reason === 'destroyed') setStoredRoom(null);
  useRoom.setState({ fatal: reason, status: 'idle' });
}

/** Abre (o reutiliza) la conexión con la sala. */
export async function joinRoom(code: string): Promise<void> {
  if (socket && useRoom.getState().code === code && useRoom.getState().fatal === null) return;
  leaveRoom(false);
  const gen = joinGen;
  await ensureSession();
  if (gen !== joinGen) return;
  useRoom.setState({ ...initialRoomState, code, status: 'connecting' });
  setStoredRoom(code);
  const s = new GameSocket(
    code,
    () => getStoredToken() ?? '',
    () => useRoom.getState().version,
    {
      onMessage: handleMessage,
      onStatus: (st: ConnStatus) => {
        useRoom.setState({ status: st });
      },
      onOpen: () => {
        void audioHost.onSocketOpen();
      },
      onFatal,
    },
  );
  socket = s;
  audioHost.configure((type, payload) => s.send(type, payload), code);
  s.start();
}

export function leaveRoom(forget: boolean): void {
  joinGen += 1;
  socket?.stop();
  socket = null;
  audioHost.reset();
  if (forget) setStoredRoom(null);
  useRoom.setState({ ...initialRoomState });
}

/** Envía y devuelve el error (si lo hay) en vez de lanzar. */
export async function request<T extends ClientMessageType>(
  type: T,
  payload: ClientPayloads[T],
): Promise<WsError | null> {
  if (!socket) return new WsError('closed', 'Sin conexión');
  try {
    await socket.send(type, payload);
    return null;
  } catch (e) {
    return e instanceof WsError ? e : new WsError('unknown', 'Error desconocido');
  }
}

/** Envía y muestra el error como aviso. */
export async function act<T extends ClientMessageType>(
  type: T,
  payload: ClientPayloads[T],
): Promise<boolean> {
  const err = await request(type, payload);
  if (err) {
    toast(err.message || err.code);
    return false;
  }
  return true;
}

export function showToast(text: string): void {
  toast(text);
}
