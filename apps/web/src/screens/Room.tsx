import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import type { AudioKind } from '../audio/AudioProvider';
import { audioHost, useAudioUi } from '../audio/host';
import { AudioGate, TapToPlay, resolveAudioKind } from '../components/AudioGate';
import { ConnectionBanner } from '../components/ConnectionBanner';
import { Button, Card, Screen, Spinner, Toast } from '../components/ui';
import { useWakeLock } from '../hooks/hooks';
import { es } from '../i18n/es';
import { joinRoom, leaveRoom } from '../store/controller';
import { useRoom } from '../store/room';
import { ChooseSlot, Lobby } from './Lobby';
import { Countdown, Game } from './Game';
import { Results } from './Results';

export default function Room() {
  const { code = '' } = useParams();
  const navigate = useNavigate();
  const view = useRoom((s) => s.view);
  const fatal = useRoom((s) => s.fatal);
  const unlocked = useAudioUi((s) => s.unlocked);

  useEffect(() => {
    void joinRoom(code);
    return () => {
      leaveRoom(false);
    };
  }, [code]);

  const inGame = view !== null && view.phase !== 'lobby' && view.phase !== 'game_over';
  useWakeLock(inGame || (view?.you.isHost ?? false));

  if (fatal) {
    return (
      <Screen>
        <Card className="mt-10 flex flex-col gap-4 text-center">
          <p role="alert" className="text-lg font-bold">
            {fatal === 'kicked'
              ? es.connection.kicked
              : fatal === 'destroyed'
                ? es.connection.destroyed
                : es.connection.notFound}
          </p>
          <Button
            onClick={() => {
              leaveRoom(true);
              navigate('/');
            }}
          >
            {es.connection.home}
          </Button>
        </Card>
      </Screen>
    );
  }

  if (!view) {
    return (
      <>
        <ConnectionBanner />
        <Screen>
          <Spinner label={es.connection.connecting} />
        </Screen>
      </>
    );
  }

  const needsGate = view.you.isHost && !unlocked;

  return (
    <>
      <ConnectionBanner />
      <Toast />
      <TapToPlay />
      {needsGate ? (
        <HostRegate source={view.settings.audioSource} />
      ) : view.phase === 'lobby' ? (
        view.you.slot === null ? (
          <ChooseSlot view={view} />
        ) : (
          <Lobby view={view} />
        )
      ) : view.phase === 'countdown' ? (
        <Countdown view={view} />
      ) : view.phase === 'game_over' ? (
        <Results view={view} />
      ) : (
        <Game view={view} />
      )}
    </>
  );
}

/** El anfitrión recargó la página: hay que volver a dar el gesto del AudioGate. */
function HostRegate({ source }: { source: 'spotify' | 'preview' }) {
  const [kind, setKind] = useState<AudioKind | null>(null);
  useEffect(() => {
    void resolveAudioKind(source).then(setKind);
  }, [source]);
  return (
    <Screen>
      {kind ? (
        <AudioGate
          kind={kind}
          onDone={() => {
            void audioHost.onSocketOpen();
          }}
          onFallback={() => {
            setKind('preview');
          }}
        />
      ) : (
        <Spinner />
      )}
    </Screen>
  );
}
