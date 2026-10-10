import type { AudioEvents, AudioProvider } from './AudioProvider';

/** WAV de silencio muy corto para desbloquear el elemento <audio> con un gesto. */
function silentWavUrl(): string {
  const samples = 800;
  const buf = new ArrayBuffer(44 + samples * 2);
  const v = new DataView(buf);
  const str = (o: number, s: string) => {
    for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i));
  };
  str(0, 'RIFF');
  v.setUint32(4, 36 + samples * 2, true);
  str(8, 'WAVE');
  str(12, 'fmt ');
  v.setUint32(16, 16, true);
  v.setUint16(20, 1, true);
  v.setUint16(22, 1, true);
  v.setUint32(24, 8000, true);
  v.setUint32(28, 16000, true);
  v.setUint16(32, 2, true);
  v.setUint16(34, 16, true);
  str(36, 'data');
  v.setUint32(40, samples * 2, true);
  return URL.createObjectURL(new Blob([buf], { type: 'audio/wav' }));
}

/** Reserva (D7): reproduce el MP3 de 30 s que sirve `/api/turn/audio` en un <audio>. */
export class PreviewAudioProvider implements AudioProvider {
  readonly kind = 'preview' as const;
  private audio: HTMLAudioElement | null = null;
  private events: AudioEvents | null = null;
  private currentUrl: string | null = null;

  private ensure(): HTMLAudioElement {
    if (!this.audio) {
      const a = new Audio();
      a.preload = 'auto';
      a.addEventListener('playing', () => {
        this.events?.onPlaying(true);
      });
      a.addEventListener('pause', () => {
        this.events?.onPlaying(false);
      });
      a.addEventListener('ended', () => {
        this.events?.onPlaying(false);
      });
      this.audio = a;
    }
    return this.audio;
  }

  init(events: AudioEvents): Promise<{ deviceId: string }> {
    this.events = events;
    this.ensure();
    return Promise.resolve({ deviceId: 'preview' });
  }

  async unlock(): Promise<void> {
    const a = this.ensure();
    const url = silentWavUrl();
    const mute = this.events;
    this.events = null; // el desbloqueo no cuenta como «sonando»
    try {
      a.src = url;
      await a.play();
      a.pause();
    } catch {
      /* si el navegador lo rechaza, saldrá «Toca para que suene» */
    } finally {
      this.events = mute;
      URL.revokeObjectURL(url);
    }
  }

  /** Carga el audio del turno y lo reproduce desde el segundo 0. */
  async playBlob(blob: Blob): Promise<void> {
    const a = this.ensure();
    if (this.currentUrl) URL.revokeObjectURL(this.currentUrl);
    this.currentUrl = URL.createObjectURL(blob);
    a.src = this.currentUrl;
    a.currentTime = 0;
    await a.play();
  }

  async resume(): Promise<void> {
    await this.ensure().play();
  }

  pause(): Promise<void> {
    this.audio?.pause();
    return Promise.resolve();
  }

  dispose(): void {
    this.audio?.pause();
    if (this.currentUrl) URL.revokeObjectURL(this.currentUrl);
    this.currentUrl = null;
    this.audio = null;
    this.events = null;
  }
}
