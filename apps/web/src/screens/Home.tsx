import { CircleHelp, Plus, Users } from 'lucide-react';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { HowToPlay, HowToPlayButton } from '../components/HowToPlay';
import { Button, Screen } from '../components/ui';
import { es } from '../i18n/es';
import { getStoredRoom, setStoredRoom } from '../lib/session';

export default function Home() {
  const navigate = useNavigate();
  const [stored, setStored] = useState(getStoredRoom);
  const [rules, setRules] = useState(false);
  const closeRules = useCallback(() => {
    setRules(false);
  }, []);
  return (
    <>
      <div className="home-grid" aria-hidden />
      <Screen actions={<HowToPlayButton />}>
        <div className="home-stage">
          <img className="home-mark" src="/logo/songline-mark.svg" alt="" width={112} height={112} />
          <h1>
            <img src="/logo/songline-wordmark.svg" alt={es.appName} width={220} height={41} className="mx-auto h-auto w-[220px]" />
          </h1>
          <p className="mb-4 mt-1 max-w-[290px] text-fg-2">{es.home.tagline}</p>
          <div className="relative z-[1] flex w-full flex-col gap-3">
            {stored ? (
              <>
                <Button
                  variant="accent"
                  xl
                  onClick={() => {
                    navigate(`/sala/${stored}`);
                  }}
                >
                  {es.home.resume(stored)}
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setStoredRoom(null);
                    setStored(null);
                  }}
                >
                  {es.home.forget}
                </Button>
              </>
            ) : null}
            <Button
              xl
              onClick={() => {
                navigate('/crear');
              }}
            >
              <Plus aria-hidden />
              {es.home.create}
            </Button>
            <Button
              xl
              variant="secondary"
              onClick={() => {
                navigate('/unirse');
              }}
            >
              <Users aria-hidden />
              {es.home.join}
            </Button>
            <Button
              variant="ghost"
              data-testid="howto-open"
              onClick={() => {
                setRules(true);
              }}
            >
              <CircleHelp aria-hidden />
              {es.home.howTo}
            </Button>
          </div>
        </div>
      </Screen>
      {rules ? <HowToPlay onClose={closeRules} /> : null}
    </>
  );
}
