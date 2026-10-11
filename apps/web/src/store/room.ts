import { create } from 'zustand';
import type {
  AudioFailCode,
  AudioSource,
  GameOverPayload,
  RevealPayload,
  RoomView,
} from '../protocol/types';
import type { ConnStatus, FatalReason } from '../ws/client';

export interface RoomState {
  code: string | null;
  view: RoomView | null;
  version: number;
  status: 'idle' | ConnStatus;
  fatal: FatalReason | null;
  /** serverTime - clientTime en segundos (de `pong.server_ts`). */
  clockOffset: number;
  reveal: RevealPayload | null;
  turnResolved: { to_slot: number | null; token_delta: Record<string, number> } | null;
  countdown: { deadlineTs: number; firstSlot: number } | null;
  gameOver: GameOverPayload | null;
  audioStatus: { playing: boolean; source: AudioSource } | null;
  audioError: { code: AudioFailCode; retry: boolean } | null;
  deckLow: number | null;
  toast: { id: number; text: string } | null;
  /** Seguimiento local del hueco de este equipo en el turno: sirve para ofrecer «Cambiar hueco». */
  place: { card: string; confirmedByMe: boolean; changes: number; locked: boolean } | null;
}

export const initialRoomState: RoomState = {
  code: null,
  view: null,
  version: 0,
  status: 'idle',
  fatal: null,
  clockOffset: 0,
  reveal: null,
  turnResolved: null,
  countdown: null,
  gameOver: null,
  audioStatus: null,
  audioError: null,
  deckLow: null,
  toast: null,
  place: null,
};

export const useRoom = create<RoomState>(() => ({ ...initialRoomState }));

/** Hora del servidor en segundos, corregida con el desfase del último `pong`. */
export function serverNow(): number {
  return Date.now() / 1000 + useRoom.getState().clockOffset;
}
