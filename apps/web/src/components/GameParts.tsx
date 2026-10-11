import { useState } from 'react';
import { es } from '../i18n/es';
import { useCountdown } from '../hooks/hooks';
import { act } from '../store/controller';
import { Modal } from './Modal';
import { Button, Card } from './ui';

/** Modo app: título y artista. */
export function GuessModal() {
  const [title, setTitle] = useState('');
  const [artist, setArtist] = useState('');
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
      </form>
    </Modal>
  );
}

/** Modo voz alta, antes de revelar. */
export function VoiceConfirmModal() {
  const [busy, setBusy] = useState(false);
  return (
    <Modal title={es.game.voiceConfirmTitle}>
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
    <div className="flex items-center justify-between gap-3">
      <span className="font-bold">{label}</span>
      <div role="radiogroup" aria-label={label} className="flex gap-2">
        {[true, false].map((v) => (
          <button
            key={String(v)}
            type="button"
            role="radio"
            aria-checked={value === v}
            className={`btn !min-w-[72px] ${value === v ? (v ? 'btn-accent' : 'btn-primary') : 'btn-secondary'}`}
            onClick={() => {
              onChange(v);
            }}
          >
            {v ? es.common.yes : es.common.no}
          </button>
        ))}
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
    <Card className="flex flex-col gap-3">
      <h2 className="h2">{es.game.honorTitle}</h2>
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

export function ObjectionBanner({
  deadlineTs,
  totalS,
  title,
  body,
}: {
  deadlineTs: number | null;
  totalS: number;
  title: string;
  body?: string;
}) {
  return (
    <Card className="flex items-center gap-4">
      <CountdownRing deadlineTs={deadlineTs} totalS={totalS} />
      <div role="status">
        <p className="h2">{title}</p>
        {body ? <p className="mt-1 text-sm text-muted-foreground">{body}</p> : null}
      </div>
    </Card>
  );
}
