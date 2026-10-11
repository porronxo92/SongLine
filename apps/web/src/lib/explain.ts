import { es } from '../i18n/es';
import type { Headline, SlotCheck, TurnResult } from '../protocol/types';

export interface ExplainContext {
  activeName: string;
  /** Nombre del equipo que objetó (si hubo objeción). */
  objectorName: string | null;
  mode: 'app' | 'voice';
  /** Modo voz: el activo ya respondió al `honor_claim` (o el servidor ya trae aciertos). */
  honorAnswered: boolean;
  /** Quien mira es el equipo activo (se le habla de «vosotros»). */
  viewerIsActive: boolean;
  /** Años de la línea del equipo activo ANTES de insertar la carta, en orden. */
  lineYears: number[];
}

export type Tone = 'good' | 'bad' | 'neutral' | 'pending';

export interface SlotExplanation {
  ok: boolean;
  title: string;
  lines: string[];
}

export interface ResultExplanation {
  headline: { text: string; kind: 'keep' | 'steal' | 'discard' };
  placement: SlotExplanation;
  objection: (SlotExplanation & { bothValid: boolean }) | null;
  token: { text: string; tone: Tone };
}

/** Texto de un hueco a partir de los años de sus vecinos. */
export function gapText(left: number | null, right: number | null): string {
  const t = es.explain;
  if (left !== null && right !== null) return t.gapBetween(left, right);
  if (left !== null) return t.gapAfter(left);
  if (right !== null) return t.gapBefore(right);
  return t.gapEmpty;
}

/** Huecos correctos (validFrom..validTo) leídos sobre la línea original. */
export function validGaps(check: Pick<SlotCheck, 'validFrom' | 'validTo'>, lineYears: number[]): string[] {
  const out: string[] = [];
  if (check.validTo > lineYears.length || check.validFrom < 0) return out;
  for (let i = check.validFrom; i <= check.validTo; i++) {
    out.push(gapText(lineYears[i - 1] ?? null, lineYears[i] ?? null));
  }
  return out;
}

function joinOr(items: string[]): string {
  return items.join(es.explain.or);
}

function cardRef(year: number, own: boolean): string {
  return own ? es.explain.cardOwn(year) : es.explain.cardOther(year);
}

/** Por qué un hueco no valía y dónde estaba el correcto. */
function wrongLines(check: SlotCheck, songYear: number, lineYears: number[]): string[] {
  const t = es.explain;
  const lines: string[] = [];
  if (check.reason === 'too_early' && check.leftYear !== null) lines.push(t.tooEarly(songYear, check.leftYear));
  else if (check.reason === 'too_late' && check.rightYear !== null) lines.push(t.tooLate(songYear, check.rightYear));
  const gaps = validGaps(check, lineYears);
  if (gaps.length > 0) lines.push(t.correctGap(joinOr(gaps), gaps.length > 1));
  return lines;
}

function explainPlacement(r: TurnResult, ctx: ExplainContext): SlotExplanation {
  const t = es.explain;
  const p = r.placement;
  if (!p.ok) {
    return { ok: false, title: t.placementKo, lines: wrongLines(p, r.songYear, ctx.lineYears) };
  }
  const lines: string[] = [];
  const gap = gapText(p.leftYear, p.rightYear);
  switch (p.reason) {
    case 'equal_both':
      lines.push(t.equalTwo(r.songYear), t.equalConclusion(gap));
      break;
    case 'equal_left':
      lines.push(t.equalOne(r.songYear, cardRef(p.leftYear ?? r.songYear, ctx.viewerIsActive)), t.equalConclusion(gap));
      break;
    case 'equal_right':
      lines.push(t.equalOne(r.songYear, cardRef(p.rightYear ?? r.songYear, ctx.viewerIsActive)), t.equalConclusion(gap));
      break;
    default:
      if (p.leftYear === null && p.rightYear === null) lines.push(t.insideFirst(r.songYear));
      else if (p.leftYear === null) lines.push(t.insideOldest(r.songYear, gap));
      else if (p.rightYear === null) lines.push(t.insideNewest(r.songYear, gap));
      else lines.push(t.insideMid(r.songYear, gap));
  }
  if (p.validFrom < p.validTo) {
    const others: string[] = [];
    for (let i = p.validFrom; i <= p.validTo; i++) {
      if (i !== p.index && i <= ctx.lineYears.length) {
        others.push(gapText(ctx.lineYears[i - 1] ?? null, ctx.lineYears[i] ?? null));
      }
    }
    if (others.length > 0) lines.push(t.alsoValid(joinOr(others)));
  }
  return { ok: true, title: t.placementOk, lines };
}

function explainObjection(r: TurnResult, ctx: ExplainContext): (SlotExplanation & { bothValid: boolean }) | null {
  const o = r.objection;
  if (!o) return null;
  const t = es.explain;
  const x = ctx.objectorName ?? '';
  const y = ctx.activeName;
  const gap = gapText(o.leftYear, o.rightYear);
  const bothValid = r.headline === 'kept_objection_failed' && o.ok;
  const spent = t.tokenSpent(x);

  if (bothValid) {
    return { ok: true, bothValid: true, title: t.bothValidTitle, lines: [t.bothValid, t.bothValidKeep(y), spent] };
  }
  if (r.headline === 'stolen') {
    const lines = [t.objStolen(x, gap)];
    if (o.reason === 'equal_left' && o.leftYear !== null) lines.push(t.objEqual(cardRef(o.leftYear, false)));
    else if (o.reason === 'equal_right' && o.rightYear !== null) lines.push(t.objEqual(cardRef(o.rightYear, false)));
    else if (o.reason === 'equal_both') lines.push(t.equalTwo(r.songYear));
    lines.push(t.objStolenKeep, spent);
    return { ok: true, bothValid: false, title: t.objectionRight, lines };
  }
  const why: string[] = [];
  if (o.reason === 'too_early' && o.leftYear !== null) why.push(t.objTooEarly(r.songYear, o.leftYear));
  else if (o.reason === 'too_late' && o.rightYear !== null) why.push(t.objTooLate(r.songYear, o.rightYear));
  const head = r.headline === 'kept_objection_failed' ? t.objFailedKept(x, gap, y) : t.objBothFailed(x, gap);
  return { ok: false, bothValid: false, title: t.objectionWrong, lines: [head, ...why, spent] };
}

function explainToken(r: TurnResult, ctx: ExplainContext): { text: string; tone: Tone } {
  const t = es.explain;
  const y = ctx.activeName;
  const reason = r.token.reason;
  if (reason === 'awarded') return { text: t.tokenWon(y), tone: 'good' };
  if (reason === 'wrong_slot') return { text: t.tokenWrongSlot(y), tone: 'bad' };
  const voice = ctx.mode === 'voice';
  if (voice && !ctx.honorAnswered && reason === 'title_and_artist_wrong') {
    return { text: ctx.viewerIsActive ? t.tokenPendingActive : t.tokenPendingOther(y), tone: 'pending' };
  }
  const table = voice
    ? { title_wrong: t.tokenTitleVoice, artist_wrong: t.tokenArtistVoice, title_and_artist_wrong: t.tokenBothVoice }
    : { title_wrong: t.tokenTitleApp, artist_wrong: t.tokenArtistApp, title_and_artist_wrong: t.tokenBothApp };
  return { text: table[reason](y), tone: 'bad' };
}

function headlineText(h: Headline, ctx: ExplainContext): ResultExplanation['headline'] {
  const t = es.explain;
  if (h === 'kept' || h === 'kept_objection_failed') return { text: t.keeps(ctx.activeName), kind: 'keep' };
  if (h === 'stolen') return { text: t.steals(ctx.objectorName ?? ''), kind: 'steal' };
  return { text: t.discards, kind: 'discard' };
}

/** Textos listos para mostrar en la revelación. Pura: no lee el store ni el DOM. */
export function explainResult(result: TurnResult, ctx: ExplainContext): ResultExplanation {
  const placement = explainPlacement(result, ctx);
  if (result.headline === 'discarded') placement.lines.push(es.explain.noObjection);
  return {
    headline: headlineText(result.headline, ctx),
    placement,
    objection: explainObjection(result, ctx),
    token: explainToken(result, ctx),
  };
}
