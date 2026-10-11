/**
 * Agrupa las cartas consecutivas del mismo año en una sola parada del carrusel.
 * Los huecos interiores de un grupo no se pueden elegir: con años iguales, el hueco justo antes o
 * después del grupo vale lo mismo, así que quitar los interiores no cambia ningún acierto.
 */

export interface YearGroup {
  year: number;
  /** Índice de la primera carta del grupo en la línea. */
  start: number;
  /** Índice siguiente a la última carta (exclusivo). */
  end: number;
}

/** Cartas consecutivas con el mismo año, en orden. */
export function groupByYear(years: readonly number[]): YearGroup[] {
  const groups: YearGroup[] = [];
  years.forEach((year, i) => {
    const last = groups[groups.length - 1];
    if (last && last.year === year) last.end = i + 1;
    else groups.push({ year, start: i, end: i + 1 });
  });
  return groups;
}

/** Índices reales de hueco que se pueden elegir: 0, el final de cada grupo. Siempre hay al menos uno. */
export function boundaries(groups: readonly YearGroup[]): number[] {
  return [0, ...groups.map((g) => g.end)];
}

/** Hueco real -> parada (posición en `boundaries`). Si cae dentro de un grupo, usa el límite más cercano. */
export function toStop(groups: readonly YearGroup[], realIndex: number): number {
  const b = boundaries(groups);
  const last = b[b.length - 1] ?? 0;
  const i = Math.max(0, Math.min(last, Math.round(realIndex)));
  let best = 0;
  let bestDist = Infinity;
  b.forEach((value, stop) => {
    const d = Math.abs(value - i);
    if (d < bestDist) {
      best = stop;
      bestDist = d;
    }
  });
  return best;
}

/** Parada -> hueco real de la línea. */
export function toRealIndex(groups: readonly YearGroup[], stop: number): number {
  const b = boundaries(groups);
  const s = Math.max(0, Math.min(b.length - 1, stop));
  return b[s] ?? 0;
}

/** Hueco real ajustado al límite de grupo más cercano. */
export function snapIndex(years: readonly number[], realIndex: number): number {
  const groups = groupByYear(years);
  return toRealIndex(groups, toStop(groups, realIndex));
}

/** ¿El hueco real cae dentro de un grupo (entre dos cartas del mismo año)? */
export function isInsideGroup(years: readonly number[], realIndex: number): boolean {
  return realIndex > 0 && realIndex < years.length && years[realIndex - 1] === years[realIndex];
}
