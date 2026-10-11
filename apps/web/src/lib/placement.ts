import { es } from '../i18n/es';

/**
 * Dónde puso la carta el equipo activo, leído sobre su línea ANTES de insertar la carta.
 * `years` va en orden y `index` es el hueco real (0..years.length).
 */
export function placementGap(years: readonly number[], index: number): string {
  const t = es.placed;
  if (years.length === 0) return t.first;
  const i = Math.max(0, Math.min(years.length, index));
  const left = years[i - 1];
  const right = years[i];
  if (left !== undefined && right !== undefined) return left === right ? t.equal(left) : t.between(left, right);
  if (left !== undefined) return t.after(left);
  if (right !== undefined) return t.before(right);
  return t.first;
}

/** Frase completa para mostrar a todos los móviles. */
export function placementSentence(years: readonly number[], index: number, name: string, mine: boolean): string {
  const gap = placementGap(years, index);
  return mine ? es.placed.own(gap) : es.placed.other(name, gap);
}
