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
  hintsEnabled: boolean;
  objectionCost: 'always';
  objectionWindowS: number;
  tokenRequiresCorrectSlot: true;
  placementTimeoutS: null;
  disconnectGraceS: number;
  startPositionMs: number;
  audioSource: AudioSource;
  /** Slugs de los packs de géneros elegidos. */
  packs: string[];
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

export type SlotReason = 'inside' | 'equal_left' | 'equal_right' | 'equal_both' | 'too_early' | 'too_late';

/** Comprobación de un hueco sobre la línea del equipo activo, antes de insertar la carta (PROTOCOL 3.2.1). */
export interface SlotCheck {
  index: number;
  leftYear: number | null;
  rightYear: number | null;
  ok: boolean;
  reason: SlotReason;
  validFrom: number;
  validTo: number;
}

export type TokenReason = 'awarded' | 'wrong_slot' | 'title_wrong' | 'artist_wrong' | 'title_and_artist_wrong';
export type Headline = 'kept' | 'kept_objection_failed' | 'stolen' | 'discarded' | 'discarded_objection_failed';

export interface TurnResult {
  songYear: number;
  placement: SlotCheck;
  objection: (SlotCheck & { slot: number; tokenSpent: boolean }) | null;
  token: { awarded: boolean; reason: TokenReason };
  headline: Headline;
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

export type HintKind = 'artist' | 'title';
/** `masked` solo existe para el equipo del turno. */
export interface HintUsed {
  kind: HintKind;
  masked?: string;
}
export interface HintsView {
  deadlineTs: number | null;
  used: HintUsed[];
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
  hints: HintsView | null;
  /** 3 menos los `place_cancel` usados. Opcional por si el servidor aún no lo envía. */
  placeChangesLeft?: number;
  /** El servidor confirmó el hueco al vencer el límite de la pista: no se puede cambiar. */
  placedAuto?: boolean;
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
  /** Posición con empates (1, 1, 3). Solo cuentan las cartas. */
  rank: number;
}

export interface RoomView {
  code: string;
  phase: Phase;
  settings: SettingsView;
  you: { slot: number | null; isHost: boolean };
  teams: TeamView[];
  turn: TurnView | null;
  deckRemaining: number;
  audio: { hostReady: boolean; playing: boolean; paused: boolean; source: AudioSource };
  pause: PauseView | null;
  winners: number[] | null;
  gameOverReason: 'target' | 'deck_exhausted' | 'host_ended' | null;
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
  packs: string[];
  hints_enabled: boolean;
  initial_tokens: number;
}

export type AudioControlAction = 'seek' | 'pause' | 'resume' | 'restart';

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
  place_cancel: Record<string, never>;
  guess_submit: { title: string; artist: string };
  voice_confirm: Record<string, never>;
  objection: { index: number };
  objection_pass: Record<string, never>;
  honor_claim: { title_ok: boolean; artist_ok: boolean };
  accept_guess: Record<string, never>;
  next_turn: Record<string, never>;
  rematch: Record<string, never>;
  end_game: Record<string, never>;
  audio_control: { action: AudioControlAction; delta_ms?: number };
  use_hint: { kind: HintKind };
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

export type AudioCommandAction =
  | 'prepare'
  | 'tap_required'
  | 'play_preview'
  | 'stop'
  | 'seek'
  | 'pause'
  | 'resume'
  | 'restart';

export interface GameOverPayload {
  winners: number[];
  reason: 'target' | 'deck_exhausted' | 'host_ended';
  standings: Standing[];
}

export interface ServerPayloads {
  state: { version: number; view: RoomView };
  ack: { ref_id: string };
  error: { ref_id: string; code: string; message: string };
  countdown: { deadline_ts: number; first_slot: number };
  audio_command: { action: AudioCommandAction; delta_ms?: number };
  hint_used: { slot: number; kind: HintKind };
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
/** `GET /api/catalog/packs`. `count` son las canciones habilitadas del pack. */
export interface CatalogPack {
  slug: string;
  name: string;
  description: string;
  icon: string;
  count: number;
}
export interface SpotifyToken {
  access_token: string;
  expires_at: number;
}
