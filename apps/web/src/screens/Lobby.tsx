import { Check, Crown, VolumeX, Wifi, WifiOff } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { HostControls } from '../components/HostControls';
import { HowToPlayButton } from '../components/HowToPlay';
import { IdentityForm } from '../components/IdentityForm';
import { PackSummary } from '../components/PackPicker';
import { ShareRoom } from '../components/ShareRoom';
import { Button, Card, Screen, TeamShape } from '../components/ui';
import { es } from '../i18n/es';
import { getVibrateEnabled, setVibrateEnabled } from '../lib/session';
import { colorFor, safeColor, teamName } from '../lib/teams';
import type { RoomView } from '../protocol/types';
import { act, leaveRoom } from '../store/controller';

/** Espectador sin hueco: elige hueco, nombre y color. */
export function ChooseSlot({ view }: { view: RoomView }) {
  const free = view.teams.filter((t) => !t.claimed);
  const [slot, setSlot] = useState<number | null>(free[0]?.slot ?? null);
  const [busy, setBusy] = useState(false);
  const takenColors = view.teams.flatMap((t) => (t.claimed ? [safeColor(t.color)] : [])).filter((c): c is string => c !== null);
  const navigate = useNavigate();

  return (
    <Screen
      title={es.identity.spectatorTitle}
      back={() => {
        leaveRoom(true);
        navigate('/');
      }}
    >
      {free.length === 0 ? (
        <Card>{es.join.full}</Card>
      ) : (
        <>
          <Card>
            <div role="radiogroup" aria-label={es.identity.pickSlot} className="flex flex-col gap-2">
              <span className="font-bold">{es.identity.pickSlot}</span>
              {view.teams.map((t) => (
                <button
                  key={t.slot}
                  type="button"
                  role="radio"
                  aria-checked={slot === t.slot}
                  disabled={t.claimed}
                  className="choice !min-h-[56px] !flex-row !items-center !justify-between"
                  onClick={() => {
                    setSlot(t.slot);
                  }}
                >
                  <span>{t.claimed ? teamName(t) : es.common.team(t.slot)}</span>
                  <span className="text-sm">{t.claimed ? es.identity.slotTaken : es.identity.slotFree}</span>
                </button>
              ))}
            </div>
          </Card>
          <Card>
            <IdentityForm
              takenColors={takenColors}
              busy={busy}
              onSubmit={(name, color) => {
                if (slot === null) return;
                setBusy(true);
                void act('claim_slot', { slot, name, color }).then(() => {
                  setBusy(false);
                });
              }}
            />
          </Card>
        </>
      )}
    </Screen>
  );
}

export function Lobby({ view }: { view: RoomView }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [vibrate, setVibrate] = useState(getVibrateEnabled);
  const teams = view.teams;
  const isHost = view.you.isHost;

  return (
    <Screen
      title={es.lobby.title}
      actions={<HowToPlayButton />}
      footer={
        <Button
          variant="secondary"
          onClick={() => {
            leaveRoom(true);
            navigate('/');
          }}
        >
          {es.lobby.leave}
        </Button>
      }
    >
      <Card className="text-center">
        <p className="overline">{es.lobby.codeLabel}</p>
        <p
          className="year py-1 text-[40px] leading-tight text-accent"
          style={{ letterSpacing: '0.12em', textShadow: 'var(--glow-text-accent)' }}
          data-testid="room-code"
        >
          {view.code}
        </p>
        <p className="help">{es.lobby.shareHint}</p>
        <ShareRoom code={view.code} />
        <p className="mt-2 text-sm font-semibold text-muted-foreground">
          {es.lobby.modeLine(
            view.settings.mode === 'app' ? es.lobby.modeApp : es.lobby.modeVoice,
            view.settings.targetCards,
          )}
        </p>
      </Card>

      <Card className="flex flex-col gap-3">
        <h2 className="h2">{es.lobby.slots}</h2>
        <ul className="flex flex-col gap-2">
          {teams.map((t) => {
            const c = colorFor(t);
            return (
              <li
                key={t.slot}
                className={t.claimed ? 'row-item' : 'row-item empty'}
                data-testid={`lobby-slot-${String(t.slot)}`}
              >
                {t.claimed ? (
                  <TeamShape shape={c.shape} color={c.hex} size={26} />
                ) : (
                  <span className="h-[26px] w-[26px] rounded-full border-2 border-dashed border-border-strong" aria-hidden />
                )}
                <span className="flex-1 truncate font-bold">
                  {t.claimed ? teamName(t) : es.lobby.empty}
                  {t.slot === view.you.slot ? ` (${es.lobby.youAre.toLowerCase()})` : ''}
                </span>
                {t.isHost ? (
                  <span className="chip !px-2" title={es.lobby.hostBadge}>
                    <Crown size={14} aria-hidden />
                    <span className="sr-only-live">{es.lobby.hostBadge}</span>
                  </span>
                ) : null}
                {t.claimed ? (
                  t.connected ? (
                    <span className="flex items-center gap-1 text-sm font-semibold text-accent">
                      <Wifi size={16} aria-hidden />
                      {es.lobby.connected}
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-sm font-semibold text-magenta-light">
                      <WifiOff size={16} aria-hidden />
                      {es.lobby.offline}
                    </span>
                  )
                ) : null}
              </li>
            );
          })}
        </ul>
        <p
          className="flex items-center gap-2 font-semibold"
          role="status"
          data-testid="audio-state"
          data-ready={view.audio.hostReady}
        >
          {view.audio.hostReady ? (
            <Check size={18} aria-hidden className="text-accent" />
          ) : (
            <VolumeX size={18} aria-hidden className="text-magenta-light" />
          )}
          {view.audio.hostReady ? es.lobby.audioOk : es.lobby.audioWait}
        </p>
        {view.settings.audioSource === 'spotify' ? (
          <p className="notice text-sm">{es.lobby.spotifyWarn}</p>
        ) : null}
      </Card>

      {isHost ? (
        <HostControls view={view} />
      ) : (
        <Card className="flex flex-col gap-2">
          <PackSummary slugs={view.settings.packs} />
        </Card>
      )}

      <label className="flex min-h-[48px] items-center gap-3 font-semibold">
        <input
          type="checkbox"
          className="h-6 w-6 accent-[#00F5D4]"
          checked={vibrate}
          onChange={(e) => {
            setVibrate(e.target.checked);
            setVibrateEnabled(e.target.checked);
          }}
        />
        {es.lobby.vibrate}
      </label>

      {isHost ? (
        <Button
          xl
          busy={busy}
          onClick={() => {
            setBusy(true);
            void act('start_game', {}).then(() => {
              setBusy(false);
            });
          }}
        >
          {es.lobby.start}
        </Button>
      ) : (
        <p className="text-center font-semibold text-muted-foreground">{es.lobby.waitHost}</p>
      )}
    </Screen>
  );
}
