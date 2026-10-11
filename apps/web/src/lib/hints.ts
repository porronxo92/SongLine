import { es } from '../i18n/es';
import type { GameMode, HintKind, Phase } from '../protocol/types';

/** Una celda del texto enmascarado. */
export type MaskCell =
  | { type: 'letter'; char: string }
  | { type: 'gap' }
  | { type: 'space' }
  | { type: 'sign'; char: string };

/** Divide `A___a__r_ _a_z` en celdas. Cada `_` es un hueco. */
export function maskCells(masked: string): MaskCell[] {
  return Array.from(masked).map((ch): MaskCell => {
    if (ch === '_') return { type: 'gap' };
    if (/\s/.test(ch)) return { type: 'space' };
    if (/\p{L}/u.test(ch)) return { type: 'letter', char: ch };
    return { type: 'sign', char: ch };
  });
}

/** Texto para lectores de pantalla: «Pista del artista: A, hueco, hueco, espacio, z». */
export function maskedAria(kind: HintKind, masked: string): string {
  const spoken = maskCells(masked)
    .map((c) => {
      if (c.type === 'gap') return es.hints.gap;
      if (c.type === 'space') return es.hints.space;
      return c.char;
    })
    .join(', ');
  return es.hints.ariaMasked(kind, spoken);
}

/**
 * Agrupa las celdas por palabras (separadas por espacios) para poder partir líneas entre palabras
 * sin romper una palabra por la mitad.
 */
export function maskWords(masked: string): MaskCell[][] {
  const words: MaskCell[][] = [];
  let cur: MaskCell[] = [];
  for (const c of maskCells(masked)) {
    if (c.type === 'space') {
      if (cur.length > 0) words.push(cur);
      cur = [];
    } else {
      cur.push(c);
    }
  }
  if (cur.length > 0) words.push(cur);
  return words;
}

/** Qué hay que enviar cuando se acaba el límite de 60 s. */
export type AutoSend = 'place_confirm' | 'guess_submit' | 'voice_confirm';

export function autoSendFor(phase: Phase, mode: GameMode): AutoSend | null {
  if (phase === 'placing') return 'place_confirm';
  if (phase === 'guessing') return mode === 'voice' ? 'voice_confirm' : 'guess_submit';
  return null;
}

/**
 * ¿Toca enviar ya? Solo cuando la cuenta atrás llega a 0 para un plazo que aún no se ha gestionado,
 * y nunca durante la pausa de la partida. `handled` es el último `deadlineTs` ya enviado.
 */
export function shouldAutoSend(
  deadlineTs: number | null,
  secondsLeft: number | null,
  handled: number | null,
  paused: boolean,
): boolean {
  if (paused || deadlineTs === null || secondsLeft === null) return false;
  return secondsLeft <= 0 && handled !== deadlineTs;
}
