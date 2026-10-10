import { AlertTriangle } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, api } from '../api/client';
import type { AudioKind } from '../audio/AudioProvider';
import { AudioGate, resolveAudioKind } from '../components/AudioGate';
import { IdentityForm } from '../components/IdentityForm';
import { Button, Card, Screen, Spinner } from '../components/ui';
import { es } from '../i18n/es';
import { loadDraft, saveDraft } from '../lib/session';
import { joinRoom } from '../store/controller';
import { DEFAULT_SETTINGS, type CreateDraft } from './Create';

function useDraft(): CreateDraft {
  const [draft] = useState<CreateDraft>(() => loadDraft<CreateDraft>() ?? { settings: DEFAULT_SETTINGS });
  return draft;
}

/** Solo el anfitrión inicia sesión en Spotify. En modo fake o con audio alternativo se salta. */
export function HostLogin() {
  const navigate = useNavigate();
  const draft = useDraft();
  const [needLogin, setNeedLogin] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    void api.authStatus().then((st) => {
      if (!alive) return;
      if (st.auth_mode === 'fake' || draft.settings.audio_source === 'preview' || st.logged_in) {
        navigate('/anfitrion/audio', { replace: true });
      } else {
        setNeedLogin(true);
      }
    });
    return () => {
      alive = false;
    };
  }, [draft.settings.audio_source, navigate]);

  return (
    <Screen title={es.hostLogin.title} back="/crear">
      {needLogin ? (
        <Card className="flex flex-col gap-4">
          <div className="flex items-start gap-3 rounded-sm bg-amber-100 p-3 text-amber-950" role="note">
            <AlertTriangle aria-hidden className="mt-0.5 shrink-0" />
            <p className="font-semibold">{es.hostLogin.premiumBanner}</p>
          </div>
          <p>{es.hostLogin.onlyHost}</p>
          <Button
            xl
            variant="violet"
            busy={busy}
            onClick={() => {
              setBusy(true);
              void api.startSpotifyLogin('/anfitrion/audio').then((url) => {
                window.location.assign(url);
              });
            }}
          >
            {es.hostLogin.login}
          </Button>
        </Card>
      ) : (
        <Spinner label={es.hostLogin.checking} />
      )}
    </Screen>
  );
}

/** AudioGate previo a crear la sala (D1: este móvil reproduce todo). */
export function HostAudio() {
  const navigate = useNavigate();
  const draft = useDraft();
  const [kind, setKind] = useState<AudioKind | null>(null);

  useEffect(() => {
    void resolveAudioKind(draft.settings.audio_source).then(setKind);
  }, [draft.settings.audio_source]);

  return (
    <Screen back="/crear">
      {kind ? (
        <AudioGate
          kind={kind}
          onDone={() => {
            navigate('/anfitrion/equipo', { replace: true });
          }}
          onFallback={() => {
            saveDraft({ settings: { ...draft.settings, audio_source: 'preview' } } satisfies CreateDraft);
            setKind('preview');
          }}
          onRelogin={() => {
            void api.startSpotifyLogin('/anfitrion/audio').then((url) => {
              window.location.assign(url);
            });
          }}
        />
      ) : (
        <Spinner />
      )}
    </Screen>
  );
}

/** Nombre y color del equipo anfitrión; aquí se crea la sala. */
export function HostIdentity() {
  const navigate = useNavigate();
  const draft = useDraft();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview] = useState(() => loadDraft<CreateDraft>()?.settings.audio_source === 'preview');

  const submit = (name: string, color: string) => {
    setBusy(true);
    setError(null);
    api
      .createRoom({
        settings: { ...draft.settings, audio_source: preview ? 'preview' : draft.settings.audio_source },
        name,
        color,
      })
      .then(async ({ code }) => {
        await joinRoom(code);
        navigate(`/sala/${code}`, { replace: true });
      })
      .catch((e: unknown) => {
        setBusy(false);
        setError(e instanceof ApiError && e.status === 429 ? es.join.rate : es.common.unknownError);
      });
  };

  return (
    <Screen title={es.identity.title} back="/crear">
      <Card>
        <IdentityForm busy={busy} onSubmit={submit} />
      </Card>
      {error ? <p role="alert" className="text-center font-bold text-destructive">{error}</p> : null}
    </Screen>
  );
}
