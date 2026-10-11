import type { AudioFailCode } from '../protocol/types';

export type AudioKind = 'sdk' | 'preview' | 'fake';

export type AudioInitErrorKind = 'account' | 'auth' | 'init' | 'timeout';

export class AudioInitError extends Error {
  readonly kind: AudioInitErrorKind;
  constructor(kind: AudioInitErrorKind, message: string) {
    super(message);
    this.kind = kind;
  }
}

export interface AudioEvents {
  /** El audio empieza o se detiene de verdad. */
  onPlaying: (playing: boolean) => void;
  /** Error posterior a `init`. */
  onError: (code: AudioFailCode) => void;
}

export interface AudioProvider {
  readonly kind: AudioKind;
  /** Prepara el reproductor y devuelve el identificador del dispositivo. */
  init(events: AudioEvents): Promise<{ deviceId: string }>;
  /** Llamar DENTRO de un gesto del usuario (AudioGate). */
  unlock(): Promise<void>;
  /** Reanuda dentro de un gesto («Toca para que suene»). */
  resume(): Promise<void>;
  pause(): Promise<void>;
  /** Salta `deltaMs` desde la posición actual, limitado a [0, duración]. */
  seekBy(deltaMs: number): Promise<void>;
  /** Vuelve al principio de la canción y deja que suene. */
  restart(): Promise<void>;
  /** El servidor ha ordenado reproducir; el proveedor puede reaccionar (solo el falso). */
  onPrepare?(): void;
  dispose(): void;
}
