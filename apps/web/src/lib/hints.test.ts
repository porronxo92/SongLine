import { describe, expect, it } from 'vitest';
import { autoSendFor, hintCost, hintKindsFor, maskCells, maskedAria, maskWords, nextHintCost, shouldAutoSend } from './hints';

describe('maskCells', () => {
  it('separa letras, huecos, espacios y signos', () => {
    const cells = maskCells('A_ b-1');
    expect(cells.map((c) => c.type)).toEqual(['letter', 'gap', 'space', 'letter', 'sign', 'sign']);
  });

  it('trata las letras acentuadas como letras', () => {
    expect(maskCells('ñé')[0]).toEqual({ type: 'letter', char: 'ñ' });
  });
});

describe('maskWords', () => {
  it('agrupa por palabras', () => {
    const words = maskWords('A___a __z');
    expect(words).toHaveLength(2);
    expect(words[0]).toHaveLength(5);
    expect(words[1]).toHaveLength(3);
  });
});

describe('maskedAria', () => {
  it('lee huecos y espacios', () => {
    expect(maskedAria('artist', 'A__ z')).toBe('Pista del artista: A, hueco, hueco, espacio, z');
    expect(maskedAria('title', '_a')).toBe('Pista del título: hueco, a');
  });
});

describe('autoSendFor', () => {
  it('elige la acción según fase y modo', () => {
    expect(autoSendFor('placing', 'app')).toBe('place_confirm');
    expect(autoSendFor('placing', 'voice')).toBe('place_confirm');
    expect(autoSendFor('guessing', 'app')).toBe('guess_submit');
    expect(autoSendFor('guessing', 'voice')).toBe('voice_confirm');
    expect(autoSendFor('objection', 'app')).toBeNull();
    expect(autoSendFor('reveal', 'voice')).toBeNull();
  });
});

describe('shouldAutoSend', () => {
  it('no envía antes de llegar a 0', () => {
    expect(shouldAutoSend(1000, 12, null, false)).toBe(false);
  });
  it('envía una vez al llegar a 0', () => {
    expect(shouldAutoSend(1000, 0, null, false)).toBe(true);
    expect(shouldAutoSend(1000, 0, 1000, false)).toBe(false);
  });
  it('un plazo nuevo (ventana de 8 s tras vencer en colocación) vuelve a enviar', () => {
    expect(shouldAutoSend(1008, 0, 1000, false)).toBe(true);
  });
  it('no envía en pausa ni sin plazo', () => {
    expect(shouldAutoSend(1000, 0, null, true)).toBe(false);
    expect(shouldAutoSend(null, null, null, false)).toBe(false);
  });
});


describe('disponibilidad de la pista del año', () => {
  it('solo ofrece el año al colocar y con datos confirmados por el servidor', () => {
    expect(hintKindsFor('placing', true)).toEqual(['artist', 'title', 'year']);
    expect(hintKindsFor('placing', false)).toEqual(['artist', 'title']);
    expect(hintKindsFor('placing', null)).toEqual(['artist', 'title']);
    expect(hintKindsFor('placing')).toEqual(['artist', 'title']);
  });

  it('retira la opción del año después de confirmar el hueco', () => {
    expect(hintKindsFor('guessing', true)).toEqual(['artist', 'title']);
  });

  it('cuesta dos fichas frente a una por título o artista', () => {
    expect(hintCost('year')).toBe(2);
    expect(hintCost('artist')).toBe(1);
    expect(hintCost('title')).toBe(1);
  });

  it('permite la tercera pista y exige su saldo cuando ya se pidieron las letras', () => {
    expect(nextHintCost('placing', ['artist', 'title'], true)).toBe(2);
    expect(nextHintCost('placing', ['artist', 'title', 'year'], true)).toBeNull();
  });

  it('mantiene disponibles las letras después de pedir el año', () => {
    expect(nextHintCost('placing', ['year'], true)).toBe(1);
    expect(nextHintCost('placing', ['year', 'artist'], true)).toBe(1);
  });

  it('no ofrece una tercera pista con servidor antiguo o después de colocar', () => {
    expect(nextHintCost('placing', ['artist', 'title'])).toBeNull();
    expect(nextHintCost('guessing', ['artist', 'title'], true)).toBeNull();
  });
});
