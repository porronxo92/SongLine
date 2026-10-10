// Tipos del contrato cliente-servidor. Copia fiel de docs/PROTOCOL.md.
// Payload WS en snake_case; RoomView y cartas de `reveal` en camelCase.

export type Phase =
  | 'lobby'
  | 'countdown'
  | 'turn_ready'
  | 'placing'
  | 'guessing'
  | 'objection'
  | 'reveal'
  | 'paused'
  | 'game_over';

export type GameMode = 'app' | 'voice';
export type AudioSource = 'spotify' | 'preview';

export interface CardPublic {
  instanceId: string;
  year: number;
  title: string;
  artist: string;
  note: string | null;
}
export interface MysteryCardData {
  instanceId: string;
  hidden: true;
}

export interface SettingsView {
  teamCount: number;
  mode: GameMode;
  targetCards: number;
  initialCardCounts: true;
  initialTokens: number;
  objectionCost: 'always';
  objectionWindowS: number;
  tokenRequiresCorrectSlot: true;
  placementTimeoutS: null;
  disconnectGraceS: number;
  startPositionMs: number;
  audioSource: AudioSource;
}

export interface TeamView {
  slot: number;
  name: string | null;
  color: string | null;
  claimed: boolean;
  connected: boolean;
  isHost: boolean;
  timeline: CardPublic[];
  tokens: number;
  cardCount: number;
}

export type Outcome = 'kept' | 'stolen' | 'discarded';

export interface TurnResult {
  placedOk: boolean;
  objectionSlot: number | null;
  objectionOk: boolean | null;
  outcome: Outcome;
  toSlot: number | null;
  titleOk: boolean;
  artistOk: boolean;
  tokenAwarded: boolean;
  tokenDelta: Record<string, number>;
}

export interface TurnView {
  teamSlot: number;
  card: MysteryCardData | CardPublic;
  placedIndex: number | null;
  previewIndex: number | null;
  objection: { slot: number; index: number } | null;
  eligibleObjectors: number[] | null;
  deadlineTs: number | null;
  guess: { title: string; artist: string } | null;
  audioSource: AudioSource;
  startedPlaying: boolean;
  result: TurnResult | null;
  revealUnlocksAt: number | null;
}

export type PauseReason = 'audio_host_offline' | 'team_offline';

export interface PauseView {
  reason: PauseReason;
  slot: number | null;
  deadlineTs: number | null;
  resumePhase: Phase | null;
}

export interface Standing {
  slot: number;
  name: string | null;
  cards: number;
  tokens: number;
}

export interface RoomView {
  code: string;
  phase: Phase;
  settings: SettingsView;
  you: { slot: number | null; isHost: boolean };
  teams: TeamView[];
  turn: TurnView | null;
  deckRemaining: number;
  audio: { hostReady: boolean; playing: boolean; source: AudioSource };
  pause: PauseView | null;
  winners: number[] | null;
  gameOverReason: 'target' | 'deck_exhausted' | null;
  standings: Standing[] | null;
}

// ---- Cliente a servidor ----

export type AudioFailCode = 'premium_required' | 'device_gone' | 'rate_limited' | 'unknown';

export interface EditableSettings {
  team_count: number;
  mode: GameMode;
  target_cards: number;
  objection_window_s: number;
  audio_source: AudioSource;
}

export interface ClientPayloads {
  hello: { session_token: string; last_version?: number };
  claim_slot: { slot: number; name: string; color?: string };
  device_ready: { device_id: string; provider: 'sdk' | 'connect' | 'preview' | 'fake' };
  audio_unlocked: Record<string, never>;
  audio_report: { playing: boolean };
  audio_failed: { code: AudioFailCode };
  kick: { slot: number };
  update_settings: Partial<EditableSettings>;
  start_game: Record<string, never>;
  play_request: Record<string, never>;
  place_preview: { index: number };
  place_confirm: { index: number };
  guess_submit: { title: string; artist: string };
  voice_confirm: Record<string, never>;
  objection: { index: number };
  objection_pass: Record<string, never>;
  honor_claim: { title_ok: boolean; artist_ok: boolean };
  accept_guess: Record<string, never>;
  next_turn: Record<string, never>;
  rematch: Record<string, never>;
  ping: { t?: number };
}
export type ClientMessageType = keyof ClientPayloads;

// ---- Servidor a cliente ----

export interface RevealPayload {
  card: CardPublic;
  correct_slot: boolean;
  outcome: Outcome;
  to_slot: number | null;
  objection_result: { slot: number; index: number; correct: boolean } | null;
  guess_auto: { title_ok: boolean; artist_ok: boolean; score: number } | null;
  reveal_unlocks_at: number;
}

export type AudioCommandAction = 'prepare' | 'tap_required' | 'play_preview' | 'stop';

export interface GameOverPayload {
  winners: number[];
  reason: 'target' | 'deck_exhausted';
  standings: Standing[];
}

export interface ServerPayloads {
  state: { version: number; view: RoomView };
  ack: { ref_id: string };
  error: { ref_id: string; code: string; message: string };
  countdown: { deadline_ts: number; first_slot: number };
  audio_command: { action: AudioCommandAction };
  audio_status: { playing: boolean; source: AudioSource };
  audio_error: { code: AudioFailCode; retry: boolean };
  reveal: RevealPayload;
  turn_resolved: { to_slot: number | null; token_delta: Record<string, number> };
  deck_low: { remaining: number };
  kicked: { reason: 'host' };
  game_over: GameOverPayload;
  pong: { t: number | null; server_ts: number };
}
export type ServerMessageType = keyof ServerPayloads;

export type ServerMessage = {
  [K in ServerMessageType]: { type: K; id: string; payload: ServerPayloads[K] };
}[ServerMessageType];

// ---- REST ----

/** `POST /api/auth/spotify/start`: el servidor devuelve la URL de Spotify (o una interna en modo fake). */
export interface SpotifyStartRequest {
  return_to: string;
}
export interface SpotifyStartResponse {
  url: string;
}

/** Códigos de cierre del WS: 4401 sesión inválida, 4404 sala inexistente, 4429 límite, 4403 expulsado. */
export type WsCloseCode = 4401 | 4403 | 4404 | 4429;

export interface AuthStatus {
  auth_mode: 'fake' | 'spotify';
  logged_in: boolean;
  premium_verified: boolean;
}
export type PremiumReason =
  | 'premium_required'
  | 'user_not_registered'
  | 'no_session'
  | 'device_gone'
  | 'rate_limited'
  | 'unknown';
export type VerifyPremiumResponse = { premium: true } | { premium: false; reason: PremiumReason };

export interface CreateRoomRequest {
  settings: Partial<EditableSettings>;
  name?: string;
  color?: string;
}
export interface CreateRoomResponse {
  code: string;
  ws_url: string;
  ws_path: string;
  slot: number;
}
export interface RoomInfoSlot {
  slot: number;
  taken: boolean;
  name: string | null;
  color: string | null;
  suggested_color: string;
  is_host: boolean;
}
export interface RoomInfo {
  status: 'open' | 'started' | 'full';
  mode: GameMode;
  team_count: number;
  target_cards: number;
  slots: RoomInfoSlot[];
  your_slot: number | null;
}
export interface SpotifyToken {
  access_token: string;
  expires_at: number;
}
