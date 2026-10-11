import { describe, expect, it } from 'vitest';
import { placementGap, placementSentence } from './placement';

describe('placementGap', () => {
  const years = [1985, 2012, 2012, 2015];
  it('entre dos años distintos', () => {
    expect(placementGap(years, 1)).toBe('entre 1985 y 2012');
    expect(placementGap(years, 3)).toBe('entre 2012 y 2015');
  });
  it('antes y después', () => {
    expect(placementGap(years, 0)).toBe('antes de 1985');
    expect(placementGap(years, 4)).toBe('después de 2015');
  });
  it('junto a años iguales lo dice claro', () => {
    expect(placementGap(years, 2)).toBe('entre dos cartas de 2012');
  });
  it('línea vacía', () => {
    expect(placementGap([], 0)).toBe('como primera de la línea');
  });
  it('acota índices fuera de rango', () => {
    expect(placementGap(years, 99)).toBe('después de 2015');
    expect(placementGap(years, -3)).toBe('antes de 1985');
  });
});

describe('placementSentence', () => {
  it('habla de vosotros al activo y nombra al equipo a los demás', () => {
    expect(placementSentence([2012, 2015], 1, 'Rojos', true)).toBe('Habéis puesto la carta entre 2012 y 2015.');
    expect(placementSentence([2012, 2015], 0, 'Rojos', false)).toBe('Rojos han puesto la carta antes de 2012.');
    expect(placementSentence([2012], 1, 'Equipo 2', false)).toBe('Equipo 2 ha puesto la carta después de 2012.');
  });
});
