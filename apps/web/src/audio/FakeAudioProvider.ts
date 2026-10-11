import type { AudioEvents, AudioProvider } from './AudioProvider';

/** Proveedor para AUTH_MODE=fake, desarrollo y E2E. No suena nada. */
declare global {
  interface Window {
    /** Comandos de audio recibidos por el proveedor falso (para los E2E). */
    __fakeAudioLog?: { action: string; deltaMs?: number }[];
  }
}

function log(action: string, deltaMs?: number): void {
  const list = (window.__fakeAudioLog ??= []);
  list.push(deltaMs === undefined ? { action } : { action, deltaMs });
}

export class FakeAudioProvider implements AudioProvider {
  readonly kind = 'fake' as const;
  private events: AudioEvents | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;

  init(events: AudioEvents): Promise<{ deviceId: string }> {
    this.events = events;
    return Promise.resolve({ deviceId: 'fake' });
  }

  unlock(): Promise<void> {
    return Promise.resolve();
  }

  resume(): Promise<void> {
    log('resume');
    this.events?.onPlaying(true);
    return Promise.resolve();
  }

  pause(): Promise<void> {
    log('pause');
    this.events?.onPlaying(false);
    return Promise.resolve();
  }

  seekBy(deltaMs: number): Promise<void> {
    log('seek', deltaMs);
    return Promise.resolve();
  }

  restart(): Promise<void> {
    log('restart');
    this.events?.onPlaying(true);
    return Promise.resolve();
  }

  onPrepare(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      this.events?.onPlaying(true);
    }, 150);
  }

  dispose(): void {
    if (this.timer) clearTimeout(this.timer);
    this.events = null;
  }
}
