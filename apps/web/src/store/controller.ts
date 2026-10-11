import { es } from '../i18n/es';
import { teamName } from '../lib/teams';
import { ensureSession } from '../api/client';
import { audioHost } from '../audio/host';
import { errorMessage } from '../lib/errors';
import { getStoredToken, setStoredRoom } from '../lib/session';
import type { ClientMessageType, ClientPayloads, ServerMessage } from '../protocol/types';
import { GameSocket, WsError, type ConnStatus, type FatalReason } from '../ws/client';
import type { TurnView } from '../protocol/types';
import { initialRoomState, useRoom, type RoomState } from './room';

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
    case 'hint_used': {
      const { view } = useRoom.getState();
      const { slot, kind } = msg.payload;
      if (view && slot !== view.you.slot) {
        toast(es.hints.usedBy(teamName(view.teams[slot], slot), kind));
      }
      break;
    }
    case 'kicked':
      break;
    case 'audio_command': {
      const view = useRoom.getState().view;
      if (!view?.you.isHost) break;
      // Si el equipo del turno pausó a propósito, «Toca para que suene» sobra.
      if (msg.payload.action === 'tap_required' && view.audio.paused) break;
      audioHost.handleCommand(msg.payload.action, msg.payload.delta_ms);
      break;
    }
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
    toast(errorMessage(err.code));
    return false;
  }
  return true;
}

const MAX_PLACE_CHANGES = 3;

function trackPlace(card: string, patch: (p: NonNullable<RoomState['place']>) => Partial<NonNullable<RoomState['place']>>): void {
  const cur = useRoom.getState().place;
  const base = cur?.card === card ? cur : { card, confirmedByMe: false, changes: 0, locked: false };
  useRoom.setState({ place: { ...base, ...patch(base), card } });
}

/** `place_confirm` que recuerda que el hueco lo puso este equipo (no el servidor al vencer el plazo). */
export async function confirmPlace(card: string, index: number): Promise<boolean> {
  const ok = await act('place_confirm', { index });
  if (ok) trackPlace(card, () => ({ confirmedByMe: true }));
  return ok;
}

/** `place_cancel`: vuelve a colocar. Si el servidor ya no lo permite, deja de ofrecerlo. */
export async function cancelPlace(card: string): Promise<boolean> {
  const err = await request('place_cancel', {});
  if (!err) {
    trackPlace(card, (p) => ({ changes: p.changes + 1, confirmedByMe: false }));
    return true;
  }
  if (['wrong_phase', 'too_many_changes', 'already_guessed'].includes(err.code)) {
    trackPlace(card, () => ({ locked: true }));
  }
  toast(errorMessage(err.code));
  return false;
}

/** ¿Se puede ofrecer «Cambiar hueco»? */
export function canChangePlace(
  place: RoomState['place'],
  card: string,
  turn?: Pick<TurnView, 'placeChangesLeft' | 'placedAuto'>,
): boolean {
  if (turn?.placedAuto === true) return false;
  if (turn?.placeChangesLeft !== undefined) {
    return turn.placeChangesLeft > 0 && !(place?.card === card && place.locked);
  }
  return place?.card === card && place.confirmedByMe && !place.locked && place.changes < MAX_PLACE_CHANGES;
}

export function showToast(text: string): void {
  toast(text);
}
