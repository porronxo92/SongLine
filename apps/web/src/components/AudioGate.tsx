import { Volume2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import type { AudioKind } from '../audio/AudioProvider';
import { audioHost, describeAudioInitError, useAudioUi } from '../audio/host';
import { es } from '../i18n/es';
import type { AudioSource } from '../protocol/types';
import { Button, Card, Spinner } from './ui';

/** Qué proveedor usa este móvil: falso en AUTH_MODE=fake, reserva si se eligió, SDK en el resto. */
export async function resolveAudioKind(source: AudioSource): Promise<AudioKind> {
  const status = await api.authStatus();
  if (status.auth_mode === 'fake') return 'fake';
  return source === 'preview' ? 'preview' : 'sdk';
}

type Stage =
  | { name: 'preparing' }
  | { name: 'ready' }
  | { name: 'checking' }
  | { name: 'error'; text: string; allowFallback: boolean; allowRelogin: boolean };

/** Pantalla de «Toca para activar el audio»: el gesto desbloquea el reproductor del anfitrión. */
export function AudioGate({
  kind,
  onDone,
  onFallback,
  onRelogin,
}: {
  kind: AudioKind;
  onDone: () => void;
  onFallback?: () => void;
  onRelogin?: () => void;
}) {
  const [stage, setStage] = useState<Stage>({ name: 'preparing' });
  const [attempt, setAttempt] = useState(0);
  const ready = useAudioUi((s) => s.ready);

  useEffect(() => {
    let alive = true;
    setStage({ name: 'preparing' });
    audioHost.prepare(kind).then(
      () => {
        if (alive) setStage({ name: 'ready' });
      },
      (e: unknown) => {
        if (!alive) return;
        const k = describeAudioInitError(e);
        setStage({
          name: 'error',
          text: es.audioGate.initErrors[k],
          allowFallback: k === 'init' || k === 'timeout',
          allowRelogin: k === 'auth',
        });
      },
    );
    return () => {
      alive = false;
    };
  }, [kind, attempt]);

  const activate = useCallback(() => {
    // `unlock` se llama dentro del gesto, antes de cualquier await.
    const unlocking = audioHost.unlock();
    setStage({ name: 'checking' });
    void (async () => {
      try {
        await unlocking;
        const res = await audioHost.verifyPremium();
        if (res.ok) {
          onDone();
        } else {
          const text =
            (es.audioGate.reasons as Record<string, string>)[res.reason] ?? es.audioGate.reasons.unknown;
          setStage({
            name: 'error',
            text,
            allowFallback: true,
            allowRelogin: res.reason === 'no_session',
          });
        }
      } catch {
        setStage({ name: 'error', text: es.audioGate.reasons.unknown, allowFallback: true, allowRelogin: false });
      }
    })();
  }, [onDone]);

  if (stage.name === 'error') {
    return (
      <Card className="flex flex-col gap-4 text-center">
        <h2 className="font-display text-2xl font-semibold">{es.audioGate.blockedTitle}</h2>
        <p role="alert">{stage.text}</p>
        <Button
          onClick={() => {
            setAttempt((n) => n + 1);
          }}
        >
          {es.common.retry}
        </Button>
        {stage.allowRelogin && onRelogin ? (
          <Button variant="violet" onClick={onRelogin}>
            {es.audioGate.relogin}
          </Button>
        ) : null}
        {stage.allowFallback && onFallback ? (
          <Button variant="soft" onClick={onFallback}>
            {es.audioGate.useFallback}
          </Button>
        ) : null}
      </Card>
    );
  }

  return (
    <Card className="flex flex-col items-center gap-5 text-center">
      <Volume2 size={56} className="text-secondary" aria-hidden />
      <h2 className="font-display text-3xl font-semibold">{es.audioGate.title}</h2>
      <p>{es.audioGate.body}</p>
      {stage.name === 'preparing' ? <Spinner label={es.audioGate.preparing} /> : null}
      {stage.name === 'checking' ? <Spinner label={es.audioGate.checking} /> : null}
      {stage.name === 'ready' ? (
        <Button xl disabled={!ready} onClick={activate}>
          {es.audioGate.activate}
        </Button>
      ) : null}
    </Card>
  );
}

/** «Toca para que suene»: pantalla completa, sin metadatos. El `resume()` va dentro del gesto. */
export function TapToPlay() {
  const tap = useAudioUi((s) => s.tapRequired);
  if (!tap) return null;
  return (
    <button
      type="button"
      className="fixed inset-0 z-[70] flex flex-col items-center justify-center gap-4 bg-secondary text-black"
      onClick={() => {
        void audioHost.tapToPlay();
      }}
    >
      <Volume2 size={96} aria-hidden />
      <span className="font-display text-4xl font-semibold">{es.game.tapToPlay}</span>
    </button>
  );
}
