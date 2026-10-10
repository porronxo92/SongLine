import type { AudioEvents, AudioProvider } from './AudioProvider';

/** Proveedor para AUTH_MODE=fake, desarrollo y E2E. No suena nada. */
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
    this.events?.onPlaying(true);
    return Promise.resolve();
  }

  pause(): Promise<void> {
    this.events?.onPlaying(false);
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
