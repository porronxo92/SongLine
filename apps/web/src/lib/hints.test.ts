import { describe, expect, it } from 'vitest';
import { autoSendFor, maskCells, maskedAria, maskWords, shouldAutoSend } from './hints';

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
