import clsx from 'clsx';
import { Check, Hand, Undo2, X } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { es } from '../i18n/es';
import { useCountdown } from '../hooks/hooks';
import { act } from '../store/controller';
import { Modal } from './Modal';
import { Button, Card } from './ui';

function ChangeSlotButton({ disabled, onClick }: { disabled?: boolean; onClick: () => void }) {
  return (
    <Button variant="ghost" className="w-full" disabled={disabled} onClick={onClick} data-testid="change-slot">
      <Undo2 size={18} aria-hidden />
      {es.game.changeSlot}
    </Button>
  );
}

/** Modo app: título y artista. */
export function GuessModal({
  summary,
  tools,
  title,
  artist,
  onTitle: setTitle,
  onArtist: setArtist,
  onChangeSlot,
}: {
  summary?: ReactNode;
  tools?: ReactNode;
  title: string;
  artist: string;
  onTitle: (v: string) => void;
  onArtist: (v: string) => void;
  onChangeSlot?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const send = (t: string, a: string) => {
    setBusy(true);
    void act('guess_submit', { title: t.trim(), artist: a.trim() }).then((ok) => {
      if (!ok) setBusy(false);
    });
  };
  return (
    <Modal title={es.game.guessTitle}>
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          send(title, artist);
        }}
      >
        {summary}
        {tools}
        <p className="text-muted-foreground">{es.game.guessSubtitle}</p>
        <label className="flex flex-col gap-1 font-bold">
          {es.game.fieldTitle}
          <input
            className="input"
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
            }}
            autoComplete="off"
            autoCapitalize="words"
            autoCorrect="off"
            spellCheck={false}
            maxLength={120}
            name="title"
          />
        </label>
        <label className="flex flex-col gap-1 font-bold">
          {es.game.fieldArtist}
          <input
            className="input"
            value={artist}
            onChange={(e) => {
              setArtist(e.target.value);
            }}
            autoComplete="off"
            autoCapitalize="words"
            autoCorrect="off"
            spellCheck={false}
            maxLength={120}
            name="artist"
          />
        </label>
        <Button type="submit" variant="primary" busy={busy}>
          {es.common.send}
        </Button>
        <Button
          variant="secondary"
          disabled={busy}
          onClick={() => {
            send('', '');
          }}
        >
          {es.game.dontKnow}
        </Button>
        {onChangeSlot ? <ChangeSlotButton disabled={busy} onClick={onChangeSlot} /> : null}
      </form>
    </Modal>
  );
}

/** Modo voz alta, antes de revelar. */
export function VoiceConfirmModal({
  summary,
  tools,
  onChangeSlot,
}: {
  summary?: ReactNode;
  tools?: ReactNode;
  onChangeSlot?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <Modal title={es.game.voiceConfirmTitle}>
      {summary ? <div className="mb-4">{summary}</div> : null}
      {tools ? <div className="mb-4">{tools}</div> : null}
      <p className="mb-5 text-lg">{es.game.voiceConfirmBody}</p>
      <Button
        xl
        busy={busy}
        onClick={() => {
          setBusy(true);
          void act('voice_confirm', {}).then((ok) => {
            if (!ok) setBusy(false);
          });
        }}
      >
        {es.game.voiceConfirm}
      </Button>
      {onChangeSlot ? (
        <div className="mt-3">
          <ChangeSlotButton disabled={busy} onClick={onChangeSlot} />
        </div>
      ) : null}
    </Modal>
  );
}

function Toggle({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="honor-row">
      <span>{label}</span>
      <div role="radiogroup" aria-label={label} className="honor-opts">
        {[true, false].map((v) => {
          const on = value === v;
          const Icon = v ? Check : X;
          return (
            <button
              key={String(v)}
              type="button"
              role="radio"
              aria-checked={on}
              className={clsx('btn', on ? (v ? 'btn-accent' : 'btn-danger') : 'btn-secondary')}
              onClick={() => {
                onChange(v);
              }}
            >
              <Icon size={18} aria-hidden />
              {v ? es.common.yes : es.common.no}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Modo voz alta, tras revelar: reclamación por honor. Se puede corregir hasta pulsar «Siguiente». */
export function HonorClaim({
  initialTitle,
  initialArtist,
  onClaim,
}: {
  initialTitle: boolean;
  initialArtist: boolean;
  onClaim?: () => void;
}) {
  const [titleOk, setTitleOk] = useState(initialTitle);
  const [artistOk, setArtistOk] = useState(initialArtist);
  const send = (t: boolean, a: boolean) => {
    onClaim?.();
    void act('honor_claim', { title_ok: t, artist_ok: a });
  };
  return (
    <Card className="flex flex-col gap-3" data-testid="honor-claim">
      <div>
        <h2 className="h2">{es.game.honorTitle}</h2>
        <p className="help mt-1">{es.game.honorHelp}</p>
      </div>
      <Toggle
        label={es.game.honorTitleOk}
        value={titleOk}
        onChange={(v) => {
          setTitleOk(v);
          send(v, artistOk);
        }}
      />
      <Toggle
        label={es.game.honorArtistOk}
        value={artistOk}
        onChange={(v) => {
          setArtistOk(v);
          send(titleOk, v);
        }}
      />
    </Card>
  );
}

/** Anillo con la cuenta atrás de la ventana de objeción. */
export function CountdownRing({
  deadlineTs,
  totalS,
  size = 64,
}: {
  deadlineTs: number | null;
  totalS: number;
  size?: number;
}) {
  const s = useCountdown(deadlineTs) ?? 0;
  const r = size / 2 - 6;
  const circ = 2 * Math.PI * r;
  const frac = Math.min(1, s / Math.max(1, totalS));
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-surface-3)" strokeWidth={6} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--color-accent)"
          strokeWidth={6}
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - frac)}
          transform={`rotate(-90 ${String(size / 2)} ${String(size / 2)})`}
          style={{ transition: 'stroke-dashoffset 250ms linear' }}
        />
      </svg>
      <span className="year absolute inset-0 flex items-center justify-center text-lg">{s}</span>
    </div>
  );
}

/** Aviso «te toca objetar»: borde y brillo del color del equipo. Solo se monta cuando puede objetar. */
export function ObjectionBanner({
  deadlineTs,
  totalS,
  title,
  body,
  kicker,
  color,
}: {
  deadlineTs: number | null;
  totalS: number;
  title: string;
  body?: string;
  kicker?: string;
  color?: string;
}) {
  return (
    <Card
      className="obj-banner flex items-center gap-4"
      style={color ? ({ '--tc': color } as React.CSSProperties) : undefined}
      data-testid="objection-banner"
    >
      <CountdownRing deadlineTs={deadlineTs} totalS={totalS} />
      <div role="status" aria-live="polite">
        {kicker ? (
          <span className="obj-kicker">
            <Hand size={16} aria-hidden />
            {kicker}
          </span>
        ) : null}
        <p className="h2">{title}</p>
        {body ? <p className="mt-1 text-sm text-muted-foreground">{body}</p> : null}
      </div>
    </Card>
  );
}
