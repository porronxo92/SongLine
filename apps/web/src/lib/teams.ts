import type { TeamView } from '../protocol/types';
import { es } from '../i18n/es';

export type Shape = 'circle' | 'triangle' | 'square' | 'diamond';

export interface TeamColor {
  hex: string;
  shape: Shape;
  name: string;
}

/** Cuatro colores con forma propia (● ▲ ■ ◆): el color nunca es la única señal. */
export const TEAM_COLORS: readonly TeamColor[] = [
  { hex: '#FF6B4A', shape: 'circle', name: es.identity.colors[0] },
  { hex: '#4D8DFF', shape: 'triangle', name: es.identity.colors[1] },
  { hex: '#4ADE80', shape: 'square', name: es.identity.colors[2] },
  { hex: '#C084FC', shape: 'diamond', name: es.identity.colors[3] },
];

const SHAPES: Shape[] = ['circle', 'triangle', 'square', 'diamond'];

const HEX = /^#[0-9a-fA-F]{6}$/;

/** Devuelve el color solo si es `#RRGGBB`; si no, `null`. Nunca se usa un color sin pasar por aquí. */
export function safeColor(value: string | null | undefined): string | null {
  return value && HEX.test(value) ? value : null;
}

export function colorFor(team: Pick<TeamView, 'slot' | 'color'>): TeamColor {
  const safe = safeColor(team.color);
  const found = TEAM_COLORS.find((c) => c.hex.toLowerCase() === safe?.toLowerCase());
  if (found) return found;
  const fallback = TEAM_COLORS[team.slot % 4] ?? TEAM_COLORS[0];
  return {
    hex: safe ?? fallback?.hex ?? '#FF6B4A',
    shape: SHAPES[team.slot % 4] ?? 'circle',
    name: '',
  };
}

export function teamName(team: Pick<TeamView, 'slot' | 'name'> | undefined, slot?: number): string {
  if (team?.name) return team.name;
  return es.common.team(team?.slot ?? slot ?? 0);
}

/** Texto del hueco `i` de una línea del tiempo. */
export function gapLabel(years: number[], i: number): string {
  const t = es.timeline;
  if (years.length === 0) return t.first;
  const prev = years[i - 1];
  const next = years[i];
  if (prev === undefined && next !== undefined) return t.before(next);
  if (prev !== undefined && next === undefined) return t.after(prev);
  if (prev !== undefined && next !== undefined) {
    return prev === next ? t.sameYear(prev) : t.between(prev, next);
  }
  return t.first;
}
