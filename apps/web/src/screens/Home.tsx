import { Music2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button, Screen } from '../components/ui';
import { es } from '../i18n/es';
import { getStoredRoom, setStoredRoom } from '../lib/session';
import { useState } from 'react';

export default function Home() {
  const navigate = useNavigate();
  const [stored, setStored] = useState(getStoredRoom);
  return (
    <Screen>
      <div className="flex flex-1 flex-col items-center justify-center gap-8 text-center">
        <div
          className="flex h-28 w-28 items-center justify-center rounded-[28px] text-white shadow-clay"
          style={{ background: 'linear-gradient(145deg, #8b5cf6, #ec4899)' }}
        >
          <Music2 size={56} aria-hidden />
        </div>
        <div>
          <h1 className="font-display text-5xl font-semibold text-primary">{es.appName}</h1>
          <p className="mt-2 text-lg text-muted-foreground">{es.home.tagline}</p>
        </div>
        <div className="flex w-full flex-col gap-3">
          {stored ? (
            <>
              <Button
                xl
                variant="violet"
                onClick={() => {
                  navigate(`/sala/${stored}`);
                }}
              >
                {es.home.resume(stored)}
              </Button>
              <Button
                variant="soft"
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
            {es.home.create}
          </Button>
          <Button
            xl
            variant="pink"
            onClick={() => {
              navigate('/unirse');
            }}
          >
            {es.home.join}
          </Button>
        </div>
      </div>
    </Screen>
  );
}
