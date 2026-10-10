import { Trophy } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Screen, TeamShape } from '../components/ui';
import { es } from '../i18n/es';
import { colorFor, teamName } from '../lib/teams';
import type { RoomView } from '../protocol/types';
import { act, leaveRoom } from '../store/controller';
import { useRoom } from '../store/room';

export function Results({ view }: { view: RoomView }) {
  const navigate = useNavigate();
  const over = useRoom((s) => s.gameOver);
  const winners = view.winners ?? over?.winners ?? [];
  const standings = view.standings ?? over?.standings ?? [];
  const reason = view.gameOverReason ?? over?.reason ?? 'target';
  const names = winners.map((w) => teamName(view.teams[w], w)).join(' y ');

  return (
    <Screen
      title={es.results.title}
      footer={
        <Button
          variant="soft"
          onClick={() => {
            leaveRoom(true);
            navigate('/');
          }}
        >
          {es.results.leave}
        </Button>
      }
    >
      <Card className="flex flex-col items-center gap-2 text-center">
        <Trophy size={56} className="text-accent" aria-hidden />
        <p className="font-display text-3xl font-semibold" data-testid="winner">
          {winners.length > 1 ? es.results.winners(names) : es.results.winner(names)}
        </p>
        <p className="text-muted-foreground">{reason === 'target' ? es.results.reasonTarget : es.results.reasonDeck}</p>
      </Card>

      <Card>
        <h2 className="mb-2 font-display text-xl font-semibold">{es.results.standings}</h2>
        <ol className="flex flex-col gap-2">
          {standings.map((s) => {
            const team = view.teams[s.slot];
            const c = team ? colorFor(team) : null;
            return (
              <li
                key={s.slot}
                className="flex min-h-[48px] items-center gap-3 rounded-sm border-2 px-3"
                style={{ borderColor: winners.includes(s.slot) ? 'var(--color-accent)' : 'var(--color-border)' }}
              >
                {c ? <TeamShape shape={c.shape} color={c.hex} /> : null}
                <span className="flex-1 truncate font-bold">{s.name ?? es.common.team(s.slot)}</span>
                <span className="year text-lg">{es.common.cards(s.cards)}</span>
              </li>
            );
          })}
        </ol>
      </Card>

      {view.you.isHost ? (
        <Button
          xl
          onClick={() => {
            void act('rematch', {});
          }}
        >
          {es.results.rematch}
        </Button>
      ) : (
        <p className="text-center font-semibold text-muted-foreground">{es.results.waitRematch}</p>
      )}
    </Screen>
  );
}
