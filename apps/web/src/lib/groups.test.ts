import { describe, expect, it } from 'vitest';
import { boundaries, groupByYear, isInsideGroup, snapIndex, toRealIndex, toStop } from './groups';

describe('groupByYear', () => {
  it('línea vacía: ningún grupo y un solo límite', () => {
    const g = groupByYear([]);
    expect(g).toEqual([]);
    expect(boundaries(g)).toEqual([0]);
    expect(toStop(g, 5)).toBe(0);
    expect(toRealIndex(g, 3)).toBe(0);
  });

  it('agrupa solo años iguales consecutivos', () => {
    const g = groupByYear([1999, 2012, 2012, 2012, 2015, 2012]);
    expect(g.map((x) => [x.year, x.start, x.end])).toEqual([
      [1999, 0, 1],
      [2012, 1, 4],
      [2015, 4, 5],
      [2012, 5, 6],
    ]);
    expect(boundaries(g)).toEqual([0, 1, 4, 5, 6]);
  });

  it('un solo grupo: dos límites', () => {
    const g = groupByYear([2000, 2000, 2000]);
    expect(g).toHaveLength(1);
    expect(boundaries(g)).toEqual([0, 3]);
  });

  it('sin repetidos: un límite por hueco real', () => {
    const g = groupByYear([1980, 1990, 2000]);
    expect(boundaries(g)).toEqual([0, 1, 2, 3]);
    expect(toStop(g, 2)).toBe(2);
    expect(toRealIndex(g, 2)).toBe(2);
  });
});

describe('mapeo índice real <-> parada', () => {
  const years = [1999, 2012, 2012, 2012, 2015];
  const g = groupByYear(years);

  it('los límites van y vuelven', () => {
    for (const real of boundaries(g)) expect(toRealIndex(g, toStop(g, real))).toBe(real);
  });

  it('un índice dentro de un grupo se ajusta al límite más cercano', () => {
    expect(isInsideGroup(years, 2)).toBe(true);
    expect(isInsideGroup(years, 1)).toBe(false);
    expect(snapIndex(years, 2)).toBe(1);
    expect(snapIndex(years, 3)).toBe(4);
  });

  it('fuera de rango se acota', () => {
    expect(toStop(g, -4)).toBe(0);
    expect(toStop(g, 99)).toBe(boundaries(g).length - 1);
    expect(toRealIndex(g, 99)).toBe(5);
    expect(toRealIndex(g, -1)).toBe(0);
  });

  it('todas del mismo año: cualquier interior cae en un extremo', () => {
    const same = [2001, 2001, 2001, 2001];
    expect(snapIndex(same, 1)).toBe(0);
    expect(snapIndex(same, 3)).toBe(4);
    expect(snapIndex(same, 0)).toBe(0);
    expect(snapIndex(same, 4)).toBe(4);
  });
});
