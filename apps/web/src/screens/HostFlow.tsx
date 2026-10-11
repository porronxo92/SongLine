import { AlertTriangle, Music2, Speaker, UserCheck } from 'lucide-react';
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
  // Los borradores guardados antes de los packs no traen `packs`: se rellenan con los valores por defecto.
  const [draft] = useState<CreateDraft>(() => ({
    settings: { ...DEFAULT_SETTINGS, ...loadDraft<CreateDraft>()?.settings },
  }));
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
          <div className="notice" role="note">
            <AlertTriangle aria-hidden />
            <p>{es.hostLogin.premiumBanner}</p>
          </div>
          <section className="info-box" aria-labelledby="spotify-how">
            <h2 id="spotify-how">{es.hostLogin.how.title}</h2>
            <ul>
              {[UserCheck, Music2, Speaker].map((Icon, i) => (
                <li key={i}>
                  <Icon size={18} aria-hidden />
                  <span>{es.hostLogin.how.items[i]}</span>
                </li>
              ))}
            </ul>
          </section>
          <Button
            xl
            variant="accent"
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
