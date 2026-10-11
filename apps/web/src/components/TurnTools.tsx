import clsx from 'clsx';
import { ChevronDown, ChevronUp, FastForward, Lightbulb, Pause, Play, Rewind, RotateCcw } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { es } from '../i18n/es';
import { maskedAria, maskWords } from '../lib/hints';
import type { HintKind, HintsView, RoomView } from '../protocol/types';
import { act } from '../store/controller';
import { Modal } from './Modal';
import { Button } from './ui';

/** Pausa tras cada pulsación. El servidor admite 4 comandos por segundo y conexión. */
const PLAYER_COOLDOWN_MS = 350;

/** Mini reproductor del equipo del turno: −10 s, pausa o reanudar, +10 s y desde el principio. Sin datos de la canción. */
function MiniPlayer({ audio }: { audio: RoomView['audio'] }) {
  const [locked, setLocked] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  const paused = audio.paused;
  const send = (payload: { action: 'seek' | 'pause' | 'resume' | 'restart'; delta_ms?: number }) => {
    if (locked) return;
    setLocked(true);
    timer.current = setTimeout(() => {
      setLocked(false);
    }, PLAYER_COOLDOWN_MS);
    void act('audio_control', payload);
  };
  return (
    <div role="group" aria-label={es.player.label} className="mp" data-testid="mini-player">
      <button
        type="button"
        className="btn btn-secondary mp-btn"
        aria-label={es.player.back}
        disabled={locked}
        data-testid="mp-back"
        onClick={() => {
          send({ action: 'seek', delta_ms: -10000 });
        }}
      >
        <Rewind size={20} aria-hidden />
        <span>{es.player.backShort}</span>
      </button>
      <button
        type="button"
        className={clsx('btn mp-btn', paused ? 'btn-accent' : 'btn-secondary')}
        aria-label={paused ? es.player.resume : es.player.pause}
        disabled={locked}
        data-testid="mp-toggle"
        onClick={() => {
          send({ action: paused ? 'resume' : 'pause' });
        }}
      >
        {paused ? <Play size={20} aria-hidden /> : <Pause size={20} aria-hidden />}
        <span>{paused ? es.player.resumeShort : es.player.pauseShort}</span>
      </button>
      <button
        type="button"
        className="btn btn-secondary mp-btn"
        aria-label={es.player.forward}
        disabled={locked}
        data-testid="mp-forward"
        onClick={() => {
          send({ action: 'seek', delta_ms: 10000 });
        }}
      >
        <FastForward size={20} aria-hidden />
        <span>{es.player.forwardShort}</span>
      </button>
      <button
        type="button"
        className="btn btn-secondary mp-btn"
        aria-label={es.player.restart}
        disabled={locked}
        data-testid="mp-restart"
        onClick={() => {
          send({ action: 'restart' });
        }}
      >
        <RotateCcw size={20} aria-hidden />
        <span>{es.player.restartShort}</span>
      </button>
    </div>
  );
}

/** Fila de herramientas del equipo del turno: mini reproductor y botón «Pista». */
export function TurnTools({
  view,
  hints,
  onHint,
}: {
  view: RoomView;
  /** Muestra el botón de pista (fases de colocar y responder). */
  hints: boolean;
  onHint: () => void;
}) {
  const me = view.you.slot;
  const team = me !== null ? view.teams[me] : undefined;
  const tokens = team?.tokens ?? 0;
  const used = view.turn?.hints?.used ?? [];
  const canHint = hints && view.settings.hintsEnabled && used.length < 2;
  const showPlayer = view.turn?.startedPlaying ?? false;
  if (!showPlayer && !canHint) return null;
  return (
    <div className={clsx('mp-row', showPlayer && canHint && 'with-hint')} data-testid="turn-tools">
      {showPlayer ? <MiniPlayer audio={view.audio} /> : null}
      {canHint ? (
        <button
          type="button"
          className="btn btn-secondary mp-btn mp-hint"
          disabled={tokens < 1}
          aria-label={tokens < 1 ? es.hints.noTokens : es.hints.button}
          data-testid="hint-button"
          onClick={onHint}
        >
          <Lightbulb size={20} aria-hidden />
          <span>{tokens < 1 ? es.hints.noTokensShort : es.hints.button}</span>
        </button>
      ) : null}
    </div>
  );
}

/** Elección del tipo de pista. Confirma con `use_hint`. */
export function HintChooser({
  tokens,
  used,
  onClose,
}: {
  tokens: number;
  used: HintKind[];
  onClose: () => void;
}) {
  const [busy, setBusy] = useState<HintKind | null>(null);
  const options: { kind: HintKind; label: string; hint: string }[] = [
    { kind: 'artist', label: es.hints.artist, hint: es.hints.artistHint },
    { kind: 'title', label: es.hints.title, hint: es.hints.titleHint },
  ];
  return (
    <Modal title={es.hints.chooseTitle} labelledBy="hint-title" onClose={onClose} icon={<Lightbulb size={32} className="text-gold" aria-hidden />}>
      <p className="mb-4 text-muted-foreground" data-testid="hint-cost">
        {es.hints.chooseCost(tokens)}
      </p>
      <div className="mb-4 grid grid-cols-2 gap-3">
        {options.map((o) => {
          const taken = used.includes(o.kind);
          return (
            <button
              key={o.kind}
              type="button"
              className="choice"
              disabled={taken || busy !== null || tokens < 1}
              data-testid={`hint-choose-${o.kind}`}
              onClick={() => {
                setBusy(o.kind);
                void act('use_hint', { kind: o.kind }).then(() => {
                  onClose();
                });
              }}
            >
              <span>{o.label}</span>
              <small>{taken ? es.hints.alreadyUsed : o.hint}</small>
            </button>
          );
        })}
      </div>
      <Button variant="secondary" className="w-full" onClick={onClose}>
        {es.common.cancel}
      </Button>
    </Modal>
  );
}

/** Texto enmascarado en cajas: los huecos se ven como casillas vacías y las palabras se separan con claridad. */
function MaskedText({ kind, masked }: { kind: HintKind; masked: string }) {
  return (
    <div className="hint-masked" role="img" aria-label={maskedAria(kind, masked)} data-testid={`hint-masked-${kind}`}>
      {maskWords(masked).map((word, wi) => (
        <span key={wi} className="hint-word" aria-hidden>
          {word.map((c, ci) =>
            c.type === 'letter' ? (
              <b key={ci} className="hint-cell">
                {c.char}
              </b>
            ) : c.type === 'gap' ? (
              <b key={ci} className="hint-cell hint-gap">
                _
              </b>
            ) : c.type === 'sign' ? (
              <b key={ci} className="hint-sign">
                {c.char}
              </b>
            ) : null,
          )}
        </span>
      ))}
    </div>
  );
}

/** Panel con las pistas pedidas y la cuenta atrás. Se puede minimizar y volver a abrir. */
export function HintPanel({
  hints,
  secs,
  paused,
}: {
  hints: HintsView;
  secs: number | null;
  paused: boolean;
}) {
  const [open, setOpen] = useState(true);
  const shown = hints.used.filter((h) => h.masked !== undefined);
  if (shown.length === 0 && secs === null) return null;
  const urgent = secs !== null && secs <= 10;
  return (
    <section className="hint-panel" aria-label={es.hints.panelTitle} data-paused={paused} data-testid="hint-panel">
      <div className="flex items-center gap-2">
        <Lightbulb size={20} className="flex-none text-gold" aria-hidden />
        <h3 className="min-w-0 flex-1 text-base font-bold">{es.hints.panelTitle}</h3>
        {secs !== null ? (
          <span
            role="timer"
            className={clsx('hint-timer year', urgent && 'urgent')}
            aria-label={es.hints.timeLeft(secs)}
            data-testid="hint-timer"
          >
            {secs} s
          </span>
        ) : null}
        <button
          type="button"
          className="btn btn-ghost btn-icon"
          aria-expanded={open}
          aria-label={open ? es.hints.hide : es.hints.show}
          data-testid="hint-toggle"
          onClick={() => {
            setOpen((o) => !o);
          }}
        >
          {open ? <ChevronUp aria-hidden /> : <ChevronDown aria-hidden />}
        </button>
      </div>
      {open ? (
        <div className="mt-2 flex flex-col gap-3">
          {shown.map((h) => (
            <div key={h.kind}>
              <p className="overline mb-1">{h.kind === 'artist' ? es.hints.artist : es.hints.title}</p>
              <MaskedText kind={h.kind} masked={h.masked ?? ''} />
            </div>
          ))}
          {secs !== null ? <p className="help">{es.hints.timeHelp}</p> : null}
        </div>
      ) : null}
    </section>
  );
}

/** Para los demás equipos: solo los tipos usados, sin texto. */
export function HintStrip({ hints }: { hints: HintsView }) {
  if (hints.used.length === 0) return null;
  return (
    <ul className="flex flex-wrap items-center gap-2" aria-label={es.hints.usedLabel} data-testid="hint-strip">
      {hints.used.map((h) => (
        <li key={h.kind} className="chip" aria-label={es.hints.usedKind(h.kind)}>
          <Lightbulb size={14} className="text-gold" aria-hidden />
          {h.kind === 'artist' ? es.hints.artist : es.hints.title}
        </li>
      ))}
    </ul>
  );
}
