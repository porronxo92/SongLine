import { describe, expect, it } from 'vitest';
import type { Headline, SlotCheck, TokenReason, TurnResult } from '../protocol/types';
import { explainResult, gapText, type ExplainContext } from './explain';

const ctx = (over: Partial<ExplainContext> = {}): ExplainContext => ({
  activeName: 'Rojos',
  objectorName: 'Azules',
  mode: 'app',
  honorAnswered: true,
  viewerIsActive: false,
  lineYears: [2012, 2015],
  ...over,
});

function slot(over: Partial<SlotCheck>): SlotCheck {
  return { index: 1, leftYear: 2012, rightYear: 2015, ok: true, reason: 'inside', validFrom: 1, validTo: 1, ...over };
}

function result(over: Partial<TurnResult> & { headline?: Headline; tokenReason?: TokenReason }): TurnResult {
  const { tokenReason = 'awarded', ...rest } = over;
  return {
    songYear: 2013,
    placement: slot({}),
    objection: null,
    token: { awarded: tokenReason === 'awarded', reason: tokenReason },
    headline: 'kept',
    placedOk: true,
    objectionSlot: null,
    objectionOk: null,
    outcome: 'kept',
    toSlot: 0,
    titleOk: true,
    artistOk: true,
    tokenAwarded: tokenReason === 'awarded',
    tokenDelta: {},
    ...rest,
  };
}

const all = (e: ReturnType<typeof explainResult>): string =>
  [e.headline.text, ...e.placement.lines, ...(e.objection?.lines ?? []), e.token.text].join('\n');

describe('gapText', () => {
  it('describe huecos y extremos', () => {
    expect(gapText(2012, 2015)).toBe('entre 2012 y 2015');
    expect(gapText(null, 2012)).toBe('antes de 2012');
    expect(gapText(2015, null)).toBe('después de 2015');
  });
});

describe('hueco del equipo activo', () => {
  it('inside: estrictamente entre vecinos', () => {
    const e = explainResult(result({}), ctx());
    expect(e.placement.ok).toBe(true);
    expect(e.placement.lines).toEqual(['La canción es de 2013. Quedaba entre 2012 y 2015.']);
  });

  it('inside en los extremos, con su año', () => {
    const old = explainResult(
      result({ songYear: 1990, placement: slot({ index: 0, leftYear: null, rightYear: 2012, validFrom: 0, validTo: 0 }) }),
      ctx(),
    );
    expect(old.placement.lines[0]).toBe('La canción es de 1990, la más antigua de la línea. Iba antes de 2012.');
    const recent = explainResult(
      result({ songYear: 2020, placement: slot({ index: 2, leftYear: 2015, rightYear: null, validFrom: 2, validTo: 2 }) }),
      ctx(),
    );
    expect(recent.placement.lines[0]).toBe('La canción es de 2020, la más reciente de la línea. Iba después de 2015.');
  });

  it('línea de una sola carta: primer y último hueco', () => {
    const first = explainResult(
      result({ songYear: 1980, placement: slot({ index: 0, leftYear: null, rightYear: 2000, validFrom: 0, validTo: 0 }) }),
      ctx({ lineYears: [2000] }),
    );
    expect(first.placement.lines[0]).toContain('antes de 2000');
    const last = explainResult(
      result({ songYear: 2010, placement: slot({ index: 1, leftYear: 2000, rightYear: null, validFrom: 1, validTo: 1 }) }),
      ctx({ lineYears: [2000] }),
    );
    expect(last.placement.lines[0]).toContain('después de 2000');
  });

  it('equal_left: explica la regla y los otros huecos válidos', () => {
    const e = explainResult(
      result({
        songYear: 2012,
        placement: slot({ reason: 'equal_left', validFrom: 0, validTo: 1 }),
      }),
      ctx({ viewerIsActive: true }),
    );
    expect(e.placement.lines).toEqual([
      'La canción es de 2012. Es el mismo año que vuestra carta de 2012, y los años iguales valen a ambos lados.',
      'Por eso el hueco entre 2012 y 2015 era correcto.',
      'También valía ponerla antes de 2012.',
    ]);
  });

  it('equal_right: habla de la carta del vecino derecho', () => {
    const e = explainResult(
      result({
        songYear: 2015,
        placement: slot({ reason: 'equal_right', validFrom: 1, validTo: 2 }),
      }),
      ctx(),
    );
    expect(e.placement.lines[0]).toContain('el mismo año que la carta de 2015');
    expect(e.placement.lines.at(-1)).toBe('También valía ponerla después de 2015.');
  });

  it('equal_both: dos cartas del mismo año', () => {
    const e = explainResult(
      result({
        songYear: 2012,
        placement: slot({ leftYear: 2012, rightYear: 2012, reason: 'equal_both', index: 1, validFrom: 0, validTo: 2 }),
      }),
      ctx({ lineYears: [2012, 2012] }),
    );
    expect(e.placement.lines[0]).toContain('las dos cartas vecinas');
    expect(e.placement.lines.at(-1)).toBe('También valía ponerla antes de 2012 o después de 2012.');
  });

  it('too_early: debía ir antes y dónde', () => {
    const e = explainResult(
      result({
        songYear: 2005,
        headline: 'discarded',
        outcome: 'discarded',
        toSlot: null,
        placedOk: false,
        tokenReason: 'wrong_slot',
        placement: slot({ ok: false, reason: 'too_early', validFrom: 0, validTo: 0 }),
      }),
      ctx(),
    );
    expect(e.placement.ok).toBe(false);
    expect(e.placement.lines[0]).toBe('La canción es de 2005. Es anterior a 2012, así que debía ir antes.');
    expect(e.placement.lines[1]).toBe('El hueco correcto era antes de 2012.');
  });

  it('too_late: debía ir después y entre qué años (línea sin la carta nueva)', () => {
    const e = explainResult(
      result({
        songYear: 2020,
        headline: 'discarded',
        outcome: 'discarded',
        placement: slot({ index: 0, leftYear: null, rightYear: 2012, ok: false, reason: 'too_late', validFrom: 2, validTo: 2 }),
        tokenReason: 'wrong_slot',
      }),
      ctx(),
    );
    expect(e.placement.lines[0]).toContain('posterior a 2012');
    expect(e.placement.lines[1]).toBe('El hueco correcto era después de 2015.');
  });

  it('hueco incorrecto con varios correctos', () => {
    const e = explainResult(
      result({
        songYear: 2012,
        headline: 'discarded',
        placement: slot({ index: 3, leftYear: 2020, rightYear: null, ok: false, reason: 'too_early', validFrom: 0, validTo: 1 }),
        tokenReason: 'wrong_slot',
      }),
      ctx(),
    );
    expect(e.placement.lines).toContain('Los huecos correctos eran antes de 2012 o entre 2012 y 2015.');
  });
});

describe('titular y objeción', () => {
  it('kept: sin objeción', () => {
    const e = explainResult(result({}), ctx());
    expect(e.headline).toEqual({ text: 'Rojos se queda la carta.', kind: 'keep' });
    expect(e.objection).toBeNull();
  });

  it('kept_objection_failed: el objetor gasta ficha', () => {
    const e = explainResult(
      result({
        headline: 'kept_objection_failed',
        objection: { ...slot({ index: 0, leftYear: null, rightYear: 2012, ok: false, reason: 'too_late', validFrom: 1, validTo: 1 }), slot: 1, tokenSpent: true },
        objectionSlot: 1,
        objectionOk: false,
      }),
      ctx(),
    );
    expect(e.headline.text).toBe('Rojos se queda la carta.');
    expect(e.objection?.ok).toBe(false);
    expect(e.objection?.lines[0]).toBe('Azules objetó antes de 2012, pero el hueco de Rojos era correcto.');
    expect(e.objection?.lines.at(-1)).toBe('Azules gasta una ficha.');
  });

  it('caso límite: los dos huecos valen', () => {
    const e = explainResult(
      result({
        songYear: 2012,
        headline: 'kept_objection_failed',
        placement: slot({ reason: 'equal_left', validFrom: 0, validTo: 1 }),
        objection: { ...slot({ index: 0, leftYear: null, rightYear: 2012, ok: true, reason: 'equal_right', validFrom: 0, validTo: 1 }), slot: 1, tokenSpent: true },
        objectionSlot: 1,
        objectionOk: true,
      }),
      ctx(),
    );
    expect(e.objection?.bothValid).toBe(true);
    expect(e.objection?.lines).toEqual([
      'Los dos huecos valían, porque hay años iguales.',
      'La carta se queda con Rojos, que la colocó primero.',
      'Azules gasta una ficha.',
    ]);
  });

  it('stolen: el objetor acierta y gasta ficha', () => {
    const e = explainResult(
      result({
        songYear: 2005,
        headline: 'stolen',
        outcome: 'stolen',
        toSlot: 1,
        placedOk: false,
        tokenReason: 'wrong_slot',
        placement: slot({ index: 2, leftYear: 2015, rightYear: null, ok: false, reason: 'too_early', validFrom: 0, validTo: 0 }),
        objection: { ...slot({ index: 0, leftYear: null, rightYear: 2012, reason: 'inside', validFrom: 0, validTo: 0 }), slot: 1, tokenSpent: true },
        objectionSlot: 1,
        objectionOk: true,
      }),
      ctx({ lineYears: [2012, 2015] }),
    );
    expect(e.headline).toEqual({ text: 'Azules se lleva la carta.', kind: 'steal' });
    expect(e.objection?.lines).toEqual([
      'Azules acierta: el hueco correcto estaba antes de 2012.',
      'Se queda la carta.',
      'Azules gasta una ficha.',
    ]);
  });

  it('stolen con años iguales explica la regla', () => {
    const e = explainResult(
      result({
        songYear: 2012,
        headline: 'stolen',
        outcome: 'stolen',
        toSlot: 1,
        placement: slot({ index: 2, leftYear: 2015, rightYear: null, ok: false, reason: 'too_early', validFrom: 0, validTo: 1 }),
        objection: { ...slot({ index: 1, ok: true, reason: 'equal_left', validFrom: 0, validTo: 1 }), slot: 1, tokenSpent: true },
        tokenReason: 'wrong_slot',
      }),
      ctx(),
    );
    expect(e.objection?.lines[1]).toBe('Es el mismo año que la carta de 2012, y los años iguales valen a ambos lados.');
  });

  it('discarded: nadie objetó', () => {
    const e = explainResult(
      result({
        songYear: 2005,
        headline: 'discarded',
        outcome: 'discarded',
        toSlot: null,
        placedOk: false,
        tokenReason: 'wrong_slot',
        placement: slot({ ok: false, reason: 'too_early', validFrom: 0, validTo: 0 }),
      }),
      ctx({ objectorName: null }),
    );
    expect(e.headline).toEqual({ text: 'La carta se descarta.', kind: 'discard' });
    expect(e.objection).toBeNull();
    expect(e.placement.lines.at(-1)).toBe('Nadie objetó.');
  });

  it('discarded_objection_failed: fallan los dos', () => {
    const e = explainResult(
      result({
        songYear: 2005,
        headline: 'discarded_objection_failed',
        outcome: 'discarded',
        toSlot: null,
        placedOk: false,
        tokenReason: 'wrong_slot',
        placement: slot({ ok: false, reason: 'too_early', validFrom: 0, validTo: 0 }),
        objection: { ...slot({ index: 2, leftYear: 2015, rightYear: null, ok: false, reason: 'too_early', validFrom: 0, validTo: 0 }), slot: 1, tokenSpent: true },
      }),
      ctx(),
    );
    expect(e.headline.kind).toBe('discard');
    expect(e.objection?.lines[0]).toBe('Azules objetó después de 2015, pero tampoco era el hueco correcto.');
    expect(e.objection?.lines.at(-1)).toBe('Azules gasta una ficha.');
  });
});

describe('ficha del equipo activo', () => {
  it.each([
    ['awarded', 'good', 'Ficha para Rojos'],
    ['wrong_slot', 'bad', 'el hueco era incorrecto'],
    ['title_wrong', 'bad', 'el título no coincide'],
    ['artist_wrong', 'bad', 'el artista no coincide'],
    ['title_and_artist_wrong', 'bad', 'fallaron el título y el artista'],
  ] as const)('modo app: %s', (reason, tone, fragment) => {
    const e = explainResult(result({ tokenReason: reason }), ctx());
    expect(e.token.tone).toBe(tone);
    expect(e.token.text).toContain(fragment);
  });

  it.each([
    ['title_wrong', 'no acertó la canción'],
    ['artist_wrong', 'no acertó el artista'],
    ['title_and_artist_wrong', 'no acertó ni canción ni artista'],
  ] as const)('modo voz respondido: %s', (reason, fragment) => {
    const e = explainResult(result({ tokenReason: reason }), ctx({ mode: 'voice', honorAnswered: true }));
    expect(e.token.tone).toBe('bad');
    expect(e.token.text).toContain(fragment);
  });

  it('modo voz: estado provisional hasta la reclamación', () => {
    const mine = explainResult(result({ tokenReason: 'title_and_artist_wrong' }), ctx({ mode: 'voice', honorAnswered: false, viewerIsActive: true }));
    expect(mine.token).toEqual({ text: 'Falta que digáis si acertasteis canción y artista.', tone: 'pending' });
    const other = explainResult(result({ tokenReason: 'title_and_artist_wrong' }), ctx({ mode: 'voice', honorAnswered: false }));
    expect(other.token.text).toBe('Falta que Rojos diga si acertó canción y artista.');
  });

  it('modo voz: con hueco incorrecto la ficha ya está cerrada', () => {
    const e = explainResult(
      result({
        tokenReason: 'wrong_slot',
        headline: 'discarded',
        placement: slot({ ok: false, reason: 'too_early', validFrom: 0, validTo: 0 }),
      }),
      ctx({ mode: 'voice', honorAnswered: false }),
    );
    expect(e.token.tone).toBe('bad');
  });

  it('no deja texto sin resolver', () => {
    const e = explainResult(result({}), ctx());
    expect(all(e)).not.toMatch(/undefined|NaN|null/);
  });
});
