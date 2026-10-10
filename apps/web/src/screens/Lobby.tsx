import { Crown, Volume2, VolumeX, Wifi, WifiOff } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { HostControls } from '../components/HostControls';
import { IdentityForm } from '../components/IdentityForm';
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
                  className="btn !justify-between"
                  style={{
                    background: '#fff',
                    color: 'var(--color-foreground)',
                    borderColor: slot === t.slot ? 'var(--color-foreground)' : 'var(--color-border)',
                  }}
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
      footer={
        <Button
          variant="soft"
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
        <p className="text-sm font-bold text-muted-foreground">{es.lobby.codeLabel}</p>
        <p className="year text-6xl tracking-[0.2em]" data-testid="room-code">
          {view.code}
        </p>
        <p className="text-sm text-muted-foreground">{es.lobby.shareHint}</p>
        <p className="mt-2 text-sm font-semibold">
          {es.lobby.modeLine(
            view.settings.mode === 'app' ? es.lobby.modeApp : es.lobby.modeVoice,
            view.settings.targetCards,
          )}
        </p>
      </Card>

      <Card className="flex flex-col gap-3">
        <h2 className="font-display text-xl font-semibold">{es.lobby.slots}</h2>
        <ul className="flex flex-col gap-2">
          {teams.map((t) => {
            const c = colorFor(t);
            return (
              <li
                key={t.slot}
                className="flex min-h-[52px] items-center gap-3 rounded-sm border-2 border-border px-3"
                data-testid={`lobby-slot-${String(t.slot)}`}
              >
                {t.claimed ? (
                  <TeamShape shape={c.shape} color={c.hex} size={26} />
                ) : (
                  <span className="h-[26px] w-[26px] rounded-full border-2 border-dashed border-muted-foreground" aria-hidden />
                )}
                <span className="flex-1 truncate font-bold">
                  {t.claimed ? teamName(t) : es.lobby.empty}
                  {t.slot === view.you.slot ? ` (${es.lobby.youAre.toLowerCase()})` : ''}
                </span>
                {t.isHost ? (
                  <span className="chip">
                    <Crown size={14} aria-hidden />
                    {es.lobby.hostBadge}
                  </span>
                ) : null}
                {t.claimed ? (
                  t.connected ? (
                    <span className="flex items-center gap-1 text-sm font-semibold text-green-800">
                      <Wifi size={16} aria-hidden />
                      {es.lobby.connected}
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-sm font-semibold text-destructive">
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
            <Volume2 size={18} aria-hidden className="text-green-700" />
          ) : (
            <VolumeX size={18} aria-hidden className="text-destructive" />
          )}
          {view.audio.hostReady ? es.lobby.audioOk : es.lobby.audioWait}
        </p>
        {view.settings.audioSource === 'spotify' ? (
          <p className="rounded-sm bg-amber-100 p-3 text-sm font-semibold text-amber-950">{es.lobby.spotifyWarn}</p>
        ) : null}
      </Card>

      {isHost ? <HostControls view={view} /> : null}

      <label className="flex min-h-[48px] items-center gap-3 font-semibold">
        <input
          type="checkbox"
          className="h-6 w-6 accent-secondary"
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
