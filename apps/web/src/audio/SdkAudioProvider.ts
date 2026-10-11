import { api } from '../api/client';
import { AudioInitError, type AudioEvents, type AudioProvider } from './AudioProvider';

const SDK_URL = 'https://sdk.scdn.co/spotify-player.js';

// Tipos mínimos del SDK. Solo se declaran los campos que se pueden leer.
// `track_window` no se declara a propósito: nunca se lee (antitrampas).
interface SdkPlayerState {
  paused: boolean;
  position: number;
  duration: number;
  loading: boolean;
}
interface SdkError {
  message: string;
}
interface SdkPlayer {
  connect(): Promise<boolean>;
  disconnect(): void;
  activateElement(): Promise<void>;
  resume(): Promise<void>;
  pause(): Promise<void>;
  seek(positionMs: number): Promise<void>;
  getCurrentState(): Promise<SdkPlayerState | null>;
  addListener(event: 'ready' | 'not_ready', cb: (d: { device_id: string }) => void): void;
  addListener(
    event:
      | 'account_error'
      | 'authentication_error'
      | 'initialization_error'
      | 'playback_error',
    cb: (e: SdkError) => void,
  ): void;
  addListener(event: 'player_state_changed', cb: (s: SdkPlayerState | null) => void): void;
}
interface SdkNamespace {
  Player: new (opts: {
    name: string;
    getOAuthToken: (cb: (token: string) => void) => void;
    volume: number;
  }) => SdkPlayer;
}
declare global {
  interface Window {
    Spotify?: SdkNamespace;
    onSpotifyWebPlaybackSDKReady?: () => void;
  }
}

let sdkLoading: Promise<SdkNamespace> | null = null;

/** Carga el SDK bajo demanda. Solo el móvil del anfitrión llega aquí. */
function loadSdk(): Promise<SdkNamespace> {
  if (window.Spotify) return Promise.resolve(window.Spotify);
  sdkLoading ??= new Promise<SdkNamespace>((resolve, reject) => {
    window.onSpotifyWebPlaybackSDKReady = () => {
      if (window.Spotify) resolve(window.Spotify);
      else reject(new AudioInitError('init', 'SDK sin espacio de nombres'));
    };
    const s = document.createElement('script');
    s.src = SDK_URL;
    s.async = true;
    s.onerror = () => {
      sdkLoading = null;
      reject(new AudioInitError('init', 'No se pudo cargar el SDK de Spotify'));
    };
    document.head.appendChild(s);
  });
  return sdkLoading;
}

export class SdkAudioProvider implements AudioProvider {
  readonly kind = 'sdk' as const;
  private player: SdkPlayer | null = null;
  private events: AudioEvents | null = null;

  async init(events: AudioEvents): Promise<{ deviceId: string }> {
    this.events = events;
    const sdk = await loadSdk();
    const player = new sdk.Player({
      name: 'SongLine',
      volume: 0.8,
      getOAuthToken: (cb) => {
        void api.spotifyToken().then((t) => {
          cb(t.access_token);
        });
      },
    });
    this.player = player;

    return new Promise<{ deviceId: string }>((resolve, reject) => {
      let ready = false;
      const timeout = setTimeout(() => {
        if (!ready) reject(new AudioInitError('timeout', 'El reproductor no responde'));
      }, 15000);
      const fail = (kind: 'account' | 'auth' | 'init', msg: string) => {
        if (!ready) {
          clearTimeout(timeout);
          reject(new AudioInitError(kind, msg));
        }
      };

      player.addListener('ready', ({ device_id }) => {
        ready = true;
        clearTimeout(timeout);
        resolve({ deviceId: device_id });
      });
      player.addListener('not_ready', () => {
        if (ready) this.events?.onError('device_gone');
      });
      player.addListener('account_error', (e) => {
        fail('account', e.message);
        this.events?.onError('premium_required');
      });
      player.addListener('authentication_error', (e) => {
        fail('auth', e.message);
        this.events?.onError('unknown');
      });
      player.addListener('initialization_error', (e) => {
        fail('init', e.message);
        this.events?.onError('unknown');
      });
      player.addListener('playback_error', () => {
        this.events?.onError('unknown');
      });
      // Solo `paused`, `position` y `loading`. Nunca el resto del estado.
      player.addListener('player_state_changed', (state) => {
        if (!state) return;
        const { paused, loading } = state;
        this.events?.onPlaying(!paused && !loading);
      });
      void player.connect().then((ok) => {
        if (!ok) fail('init', 'No se pudo conectar el reproductor');
      });
    });
  }

  async unlock(): Promise<void> {
    await this.player?.activateElement();
  }

  async resume(): Promise<void> {
    await this.player?.resume();
  }

  async pause(): Promise<void> {
    await this.player?.pause();
  }

  /** Lee solo `position` y `duration`. Nunca el resto del estado. */
  async seekBy(deltaMs: number): Promise<void> {
    const player = this.player;
    if (!player) return;
    const state = await player.getCurrentState();
    if (!state) return;
    const { position, duration } = state;
    const target = Math.min(Math.max(0, position + deltaMs), Math.max(0, duration));
    await player.seek(target);
  }

  async restart(): Promise<void> {
    const player = this.player;
    if (!player) return;
    await player.seek(0);
    const state = await player.getCurrentState();
    if (state?.paused ?? true) await player.resume();
  }

  dispose(): void {
    this.player?.disconnect();
    this.player = null;
    this.events = null;
  }
}
