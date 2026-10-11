import { describe, expect, it } from 'vitest';
import { computeRanks, groupByRank, isTotalTie, rankedStandings, type StandingInput } from './ranking';

const rows = (cards: number[], tokens: number[] = []): StandingInput[] =>
  cards.map((c, slot) => ({ slot, name: `T${String(slot)}`, cards: c, tokens: tokens[slot] ?? 0 }));
const ranksOf = (cards: number[], tokens?: number[]) =>
  rankedStandings(rows(cards, tokens))
    .sort((a, b) => a.slot - b.slot)
    .map((r) => r.rank);

describe('ranking', () => {
  it('un solo equipo es el 1.º', () => {
    expect(ranksOf([4])).toEqual([1]);
  });
  it('sin empate', () => {
    expect(ranksOf([3, 5, 4])).toEqual([3, 1, 2]);
    expect(rankedStandings(rows([3, 5, 4])).map((r) => r.slot)).toEqual([1, 2, 0]);
  });
  it('empate en el 1.º salta al 3.º', () => {
    expect(ranksOf([5, 5, 3])).toEqual([1, 1, 3]);
  });
  it('empate en el 2.º', () => {
    expect(ranksOf([5, 3, 3])).toEqual([1, 2, 2]);
  });
  it('tres equipos igualados', () => {
    expect(ranksOf([4, 4, 4])).toEqual([1, 1, 1]);
    expect(ranksOf([4, 2, 4, 4])).toEqual([1, 4, 1, 1]);
  });
  it('cuatro equipos: 1, 1, 3, 3', () => {
    expect(ranksOf([4, 2, 4, 2])).toEqual([1, 3, 1, 3]);
  });
  it('cuatro equipos igualados', () => {
    expect(ranksOf([2, 2, 2, 2])).toEqual([1, 1, 1, 1]);
  });
  it('las fichas no cambian la posición', () => {
    expect(ranksOf([3, 3, 2], [0, 9, 9])).toEqual([1, 1, 3]);
    expect(ranksOf([2, 3], [9, 0])).toEqual([2, 1]);
  });
  it('dentro de un empate ordena por hueco', () => {
    expect(rankedStandings(rows([3, 5, 5, 3])).map((r) => r.slot)).toEqual([1, 2, 0, 3]);
  });
  it('respeta el rank del servidor si viene en todas las filas', () => {
    const input = rows([3, 3]).map((r) => ({ ...r, rank: 1 }));
    expect(rankedStandings(input).map((r) => r.rank)).toEqual([1, 1]);
  });
  it('computeRanks devuelve un mapa por hueco', () => {
    expect([...computeRanks(rows([1, 2]))]).toEqual([
      [0, 2],
      [1, 1],
    ]);
  });
  it('agrupa por posición sin escalones vacíos', () => {
    const g = groupByRank(rankedStandings(rows([4, 2, 4, 2])));
    expect(g.map((x) => x.map((r) => r.slot))).toEqual([
      [0, 2],
      [1, 3],
    ]);
    expect(g.map((x) => x[0]?.rank)).toEqual([1, 3]);
  });
  it('detecta el empate total', () => {
    expect(isTotalTie(rankedStandings(rows([2, 2, 2])))).toBe(true);
    expect(isTotalTie(rankedStandings(rows([2, 2, 1])))).toBe(false);
    expect(isTotalTie(rankedStandings(rows([2])))).toBe(false);
  });
});
