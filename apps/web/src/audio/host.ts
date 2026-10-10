import { create } from 'zustand';
import { api } from '../api/client';
import type { AudioCommandAction, AudioFailCode, ClientMessageType, ClientPayloads } from '../protocol/types';
import { AudioInitError, type AudioKind, type AudioProvider } from './AudioProvider';
import { FakeAudioProvider } from './FakeAudioProvider';
import { PreviewAudioProvider } from './PreviewAudioProvider';
import { SdkAudioProvider } from './SdkAudioProvider';

export interface AudioUiState {
  /** Reproductor listo (SDK conectado, `ready` recibido). */
  ready: boolean;
  /** El gesto del AudioGate ya ocurrió. */
  unlocked: boolean;
  kind: AudioKind | null;
  /** Hay que mostrar «Toca para que suene». */
  tapRequired: boolean;
  problem: AudioFailCode | null;
}

export const useAudioUi = create<AudioUiState>(() => ({
  ready: false,
  unlocked: false,
  kind: null,
  tapRequired: false,
  problem: null,
}));

type Sender = <T extends ClientMessageType>(type: T, payload: ClientPayloads[T]) => Promise<void>;

const MASK_TITLE = 'Canción misteriosa · SongLine';

function applyMask(): void {
  if (!('mediaSession' in navigator) || typeof MediaMetadata === 'undefined') return;
  navigator.mediaSession.metadata = new MediaMetadata({
    title: MASK_TITLE,
    artist: 'SongLine',
    album: '',
    artwork: [{ src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' }],
  });
}

/** Coordina el audio del móvil del anfitrión: proveedor principal, reserva y órdenes del servidor. */
class AudioHost {
  private primary: AudioProvider | null = null;
  private readonly preview = new PreviewAudioProvider();
  private send: Sender | null = null;
  private code: string | null = null;
  private deviceId: string | null = null;
  private reported: boolean | null = null;
  private maskTimer: ReturnType<typeof setInterval> | null = null;
  private previewActive = false;
  private initPromise: Promise<void> | null = null;
  private initKind: AudioKind | null = null;

  configure(send: Sender | null, code: string | null): void {
    this.send = send;
    this.code = code;
  }

  get isUnlocked(): boolean {
    return useAudioUi.getState().unlocked;
  }

  /** Crea el proveedor y lo conecta. No necesita gesto. */
  prepare(kind: AudioKind): Promise<void> {
    if (this.initPromise && this.initKind === kind) return this.initPromise;
    this.disposePrimary();
    this.initKind = kind;
    const events = {
      onPlaying: (p: boolean) => {
        this.handlePlaying(p);
      },
      onError: (c: AudioFailCode) => {
        this.handleError(c);
      },
    };
    const provider: AudioProvider =
      kind === 'sdk' ? new SdkAudioProvider() : kind === 'fake' ? new FakeAudioProvider() : this.preview;
    this.primary = provider;
    this.initPromise = (async () => {
      try {
        const { deviceId } = await provider.init(events);
        if (provider !== this.preview) await this.preview.init(events);
        this.deviceId = deviceId;
        useAudioUi.setState({ ready: true, kind, problem: null });
      } catch (e) {
        this.initPromise = null;
        throw e;
      }
    })();
    return this.initPromise;
  }

  /** Llamar dentro del gesto del AudioGate, antes de cualquier `await`. */
  unlock(): Promise<void> {
    const p = this.primary;
    const jobs: Promise<void>[] = [];
    if (p) jobs.push(p.unlock());
    if (p !== this.preview) jobs.push(this.preview.unlock());
    useAudioUi.setState({ unlocked: true });
    applyMask();
    return Promise.all(jobs).then(() => undefined);
  }

  /** Comprueba Premium con el servidor (solo modo Spotify real). */
  async verifyPremium(): Promise<{ ok: true } | { ok: false; reason: string }> {
    if (this.primary?.kind !== 'sdk' || !this.deviceId) return { ok: true };
    const res = await api.verifyPremium(this.deviceId);
    return res.premium ? { ok: true } : { ok: false, reason: res.reason };
  }

  /** Tras abrir el WS (y en cada reconexión): el servidor marca el audio como no listo al desconectarse. */
  async onSocketOpen(): Promise<void> {
    const { unlocked, ready } = useAudioUi.getState();
    if (!this.send || !unlocked || !ready || !this.primary || !this.deviceId) return;
    this.reported = null;
    try {
      await this.send('device_ready', { device_id: this.deviceId, provider: this.primary.kind });
      await this.send('audio_unlocked', {});
    } catch {
      /* el servidor rechaza si no somos anfitrión; no es fatal */
    }
  }

  handleCommand(action: AudioCommandAction): void {
    switch (action) {
      case 'prepare':
        this.previewActive = false;
        this.primary?.onPrepare?.();
        break;
      case 'tap_required':
        useAudioUi.setState({ tapRequired: true });
        break;
      case 'play_preview':
        void this.playPreview();
        break;
      case 'stop':
        useAudioUi.setState({ tapRequired: false });
        void this.primary?.pause();
        void this.preview.pause();
        break;
    }
  }

  /** Gesto del usuario sobre «Toca para que suene». */
  async tapToPlay(): Promise<void> {
    try {
      if (this.previewActive || this.primary === this.preview) await this.preview.resume();
      else await this.primary?.resume();
      useAudioUi.setState({ tapRequired: false });
      this.report(true);
    } catch {
      this.fail('unknown');
    }
  }

  reset(): void {
    this.configure(null, null);
    this.stopMask();
  }

  private async playPreview(): Promise<void> {
    if (!this.code) return;
    this.previewActive = true;
    try {
      await this.primary?.pause();
      const blob = await api.turnAudio(this.code);
      await this.preview.playBlob(blob);
    } catch (e) {
      if (e instanceof DOMException && e.name === 'NotAllowedError') {
        useAudioUi.setState({ tapRequired: true });
      } else {
        this.fail('unknown');
      }
    }
  }

  private handlePlaying(playing: boolean): void {
    applyMask();
    if (playing) {
      useAudioUi.setState({ tapRequired: false });
      this.startMask();
    } else {
      this.stopMask();
    }
    this.report(playing);
  }

  private handleError(code: AudioFailCode): void {
    useAudioUi.setState({ problem: code });
    if (code === 'premium_required' || code === 'device_gone') this.fail(code);
  }

  private fail(code: AudioFailCode): void {
    useAudioUi.setState({ problem: code });
    void this.send?.('audio_failed', { code }).catch(() => undefined);
  }

  private report(playing: boolean): void {
    if (this.reported === playing) return;
    const first = this.reported === null;
    this.reported = playing;
    if (first && !playing) return;
    void this.send?.('audio_report', { playing }).catch(() => undefined);
  }

  private startMask(): void {
    if (this.maskTimer) return;
    this.maskTimer = setInterval(applyMask, 2000);
  }

  private stopMask(): void {
    if (this.maskTimer) clearInterval(this.maskTimer);
    this.maskTimer = null;
  }

  private disposePrimary(): void {
    if (this.primary && this.primary !== this.preview) this.primary.dispose();
    this.primary = null;
    this.initPromise = null;
    this.initKind = null;
    useAudioUi.setState({ ready: false, unlocked: false, kind: null });
  }
}

export const audioHost = new AudioHost();

export function describeAudioInitError(e: unknown): 'account' | 'auth' | 'init' | 'timeout' {
  return e instanceof AudioInitError ? e.kind : 'init';
}
