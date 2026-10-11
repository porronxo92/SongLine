import type { Standing } from '../protocol/types';

/** Entrada de clasificación; `rank` puede faltar si el servidor aún no lo envía. */
export type StandingInput = Omit<Standing, 'rank'> & { rank?: number };

/**
 * Posiciones tipo competición (1, 1, 3) calculadas solo con las cartas.
 * Las fichas no desempatan. Devuelve un mapa `slot -> posición`.
 */
export function computeRanks(rows: readonly Pick<Standing, 'slot' | 'cards'>[]): Map<number, number> {
  const ranks = new Map<number, number>();
  for (const r of rows) {
    ranks.set(r.slot, 1 + rows.filter((o) => o.cards > r.cards).length);
  }
  return ranks;
}

/**
 * Clasificación ordenada por posición y luego por hueco.
 * Usa el `rank` del servidor si viene en todas las filas; si no, lo calcula.
 */
export function rankedStandings(rows: readonly StandingInput[]): Standing[] {
  const useServer = rows.every((r) => typeof r.rank === 'number' && r.rank >= 1);
  const ranks = computeRanks(rows);
  return rows
    .map((r) => ({ ...r, rank: useServer ? (r.rank as number) : (ranks.get(r.slot) ?? 1) }))
    .sort((a, b) => a.rank - b.rank || a.slot - b.slot);
}

/** Agrupa filas ya ordenadas por posición. Un grupo por posición distinta, en orden. */
export function groupByRank(rows: readonly Standing[]): Standing[][] {
  const groups: Standing[][] = [];
  for (const r of rows) {
    const last = groups[groups.length - 1];
    if (last && last[0]?.rank === r.rank) last.push(r);
    else groups.push([r]);
  }
  return groups;
}

/** Todos los equipos comparten la primera posición y hay más de uno. */
export function isTotalTie(rows: readonly Standing[]): boolean {
  return rows.length > 1 && rows.every((r) => r.rank === 1);
}
