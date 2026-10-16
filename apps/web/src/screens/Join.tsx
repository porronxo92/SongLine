import { Delete } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ApiError, api } from '../api/client';
import { Button, Screen } from '../components/ui';
import { es } from '../i18n/es';

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9'] as const;

export default function Join() {
  const navigate = useNavigate();
  const params = useParams();
  const [code, setCode] = useState(() => (params.code ?? '').replace(/\D/g, '').slice(0, 4));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = (value: string) => {
    setBusy(true);
    setError(null);
    api.roomInfo(value).then(
      (info) => {
        if (info.status !== 'open' && info.your_slot === null) {
          setError(info.status === 'full' ? es.join.full : es.join.started);
          setBusy(false);
          return;
        }
        navigate(`/sala/${value}`);
      },
      (e: unknown) => {
        setBusy(false);
        setError(
          e instanceof ApiError && e.status === 429
            ? es.join.rate
            : e instanceof ApiError && e.status === 404
              ? es.join.notFound
              : es.common.unknownError,
        );
      },
    );
  };

  // Enlace compartido (/unirse/1234): entra solo, sin teclear. El ref evita la doble llamada de StrictMode.
  const autoTried = useRef(false);
  useEffect(() => {
    if (autoTried.current || code.length !== 4) return;
    autoTried.current = true;
    submit(code);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo al abrir la pantalla
  }, []);

  const press = (d: string) => {
    if (busy || code.length >= 4) return;
    const next = code + d;
    setCode(next);
    setError(null);
    if (next.length === 4) submit(next);
  };

  return (
    <Screen title={es.join.title} back="/">
      <p className="text-muted-foreground">{es.join.hint}</p>
      <div
        className="flex justify-center gap-3"
        role="status"
        aria-label={`${es.join.title}: ${code || '—'}`}
        data-testid="code-display"
      >
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="panel year flex h-20 w-16 items-center justify-center text-5xl"
            style={{
              borderColor: i === code.length ? 'var(--color-accent)' : undefined,
              borderWidth: 2,
              boxShadow: i === code.length ? 'var(--glow-accent)' : undefined,
              color: 'var(--color-accent)',
            }}
          >
            {code[i] ?? ''}
          </div>
        ))}
      </div>
      <p role="alert" className="min-h-[1.5rem] text-center font-bold text-magenta-light">
        {error}
      </p>
      {code.length === 4 ? (
        <Button
          xl
          busy={busy}
          className="mx-auto w-full max-w-xs"
          data-testid="join-enter"
          onClick={() => {
            submit(code);
          }}
        >
          {es.join.enter}
        </Button>
      ) : null}
      <div className="mx-auto grid w-full max-w-xs grid-cols-3 gap-3">
        {KEYS.map((k) => (
          <button
            key={k}
            type="button"
            className="btn btn-secondary year !min-h-[68px] !text-3xl"
            aria-label={es.join.digit(k)}
            onClick={() => {
              press(k);
            }}
          >
            {k}
          </button>
        ))}
        <span />
        <button
          type="button"
          className="btn btn-secondary year !min-h-[68px] !text-3xl"
          aria-label={es.join.digit('0')}
          onClick={() => {
            press('0');
          }}
        >
          0
        </button>
        <button
          type="button"
          className="btn btn-secondary !min-h-[68px]"
          aria-label={es.join.delete}
          onClick={() => {
            setCode((c) => c.slice(0, -1));
            setError(null);
          }}
        >
          <Delete aria-hidden />
        </button>
      </div>
    </Screen>
  );
}
