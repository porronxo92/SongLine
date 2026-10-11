import { Flag, Trophy } from 'lucide-react';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Pick } from '../components/Pick';
import { Button, Card, Screen, TeamShape } from '../components/ui';
import { es } from '../i18n/es';
import { colorFor, teamName } from '../lib/teams';
import { groupByRank, isTotalTie, rankedStandings } from '../lib/ranking';
import type { RoomView, Standing } from '../protocol/types';
import { act, leaveRoom } from '../store/controller';
import { useRoom } from '../store/room';

const CONFETTI = ['#00F5D4', '#FF007F', '#FFB703', '#B77CFF', '#FF6B4A', '#4D8DFF', '#4ADE80'];

/** 30 piezas con posición, retraso y duración fijas (no hay azar en cada render). */
function Confetti() {
  const pieces = useMemo(
    () =>
      Array.from({ length: 30 }, (_, i) => ({
        left: `${String(((i * 37) % 97) + 1)}%`,
        delay: `${String((i * 130) % 1400)}ms`,
        duration: `${String(2600 + ((i * 211) % 1400))}ms`,
        color: CONFETTI[i % CONFETTI.length] ?? '#00F5D4',
        dot: i % 3 === 0,
      })),
    [],
  );
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      {pieces.map((p, i) => (
        <span
          key={i}
          className={p.dot ? 'conf dot' : 'conf'}
          style={{ left: p.left, background: p.color, animationDelay: p.delay, animationDuration: p.duration }}
        />
      ))}
    </div>
  );
}
/** «A, B y C». */
function joinNames(names: string[]): string {
  if (names.length < 2) return names.join('');
  return `${names.slice(0, -1).join(', ')} y ${names[names.length - 1] ?? ''}`;
}

interface Step {
  g: Standing[];
  cls: string;
}

/**
 * Podio por posición. Los empatados comparten escalón y no hay escalones vacíos.
 * Orden visual: segundo grupo, primero, tercero (los que existan).
 */
function Podium({ view, groups }: { view: RoomView; groups: Standing[][] }) {
  const steps: Step[] = groups.slice(0, 3).map((g, i) => ({ g, cls: `p${String(i + 1)}` }));
  const [first, second, third] = steps;
  const ordered = [second, first, third].filter((x): x is Step => x !== undefined);
  const cols = ordered.length === 1 ? '1fr' : ordered.length === 2 ? '1fr 1.15fr' : '1fr 1.15fr 1fr';
  return (
    <div
      className="podium"
      data-testid="podium"
      style={{ gridTemplateColumns: cols, ...(ordered.length === 1 ? { maxWidth: '16rem', marginInline: 'auto' } : null) }}
    >
      {ordered.map(({ g, cls }) => (
        <div key={cls} className={`pod ${cls}`}>
          <span className="rk" style={{ color: cls === 'p1' ? 'var(--color-gold)' : 'var(--color-fg-2)' }}>
            {es.results.position(g[0]?.rank ?? 1)}
          </span>
          {g.length > 1 ? <span className="tie-tag">{es.results.tie}</span> : null}
          {g.map((s) => {
            const team = view.teams[s.slot];
            const c = team ? colorFor(team) : null;
            return (
              <div key={s.slot} className="pod-team">
                <span className="pod-name">
                  {c ? <TeamShape shape={c.shape} color={c.hex} size={16} /> : null}
                  <b>{s.name ?? es.common.team(s.slot)}</b>
                </span>
                <small>{es.common.cards(s.cards)}</small>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

export function Results({ view }: { view: RoomView }) {
  const navigate = useNavigate();
  const over = useRoom((s) => s.gameOver);
  const raw = view.standings ?? over?.standings;
  const ranked = useMemo(() => rankedStandings(raw ?? []), [raw]);
  const groups = useMemo(() => groupByRank(ranked), [ranked]);
  const serverWinners = view.winners ?? over?.winners ?? [];
  const winners = serverWinners.length ? serverWinners : ranked.filter((s) => s.rank === 1).map((s) => s.slot);
  const reason = view.gameOverReason ?? over?.reason ?? 'target';
  const names = joinNames(winners.map((w) => teamName(view.teams[w], w)));
  const hostEnded = reason === 'host_ended';
  const totalTie = isTotalTie(ranked);
  const leadCards = ranked.find((s) => s.rank === 1)?.cards ?? 0;
  const maxBar = Math.max(view.settings.targetCards, ...ranked.map((s) => s.cards), 1);
  const headline = totalTie
    ? es.results.totalTie
    : winners.length > 1
      ? es.results.winners(names)
      : es.results.winner(names);

  return (
    <Screen
      title={es.results.title}
      footer={
        <Button
          variant="secondary"
          onClick={() => {
            leaveRoom(true);
            navigate('/');
          }}
        >
          {es.results.leave}
        </Button>
      }
    >
      {hostEnded ? (
        <Card className="ended-card">
          <Flag size={64} className="mx-auto text-primary-light" aria-hidden />
          <h2>{es.results.endedTitle}</h2>
          <p className="text-muted-foreground">{es.results.reasonHost}</p>
          <p className="mt-2 font-semibold" data-testid="winner">
            {totalTie ? es.results.leadingTie(leadCards) : es.results.leading(names, leadCards, winners.length > 1)}
          </p>
        </Card>
      ) : (
        <div className="win-card">
          <Confetti />
          <Trophy size={64} className="trophy mx-auto" aria-hidden />
          <h2 data-testid="winner">{headline}</h2>
          <p className="text-muted-foreground">
            {reason === 'target' ? es.results.reasonTarget : es.results.reasonDeck}
            {totalTie ? ` ${es.results.totalTieBody(leadCards)}` : ''}
          </p>
          <Podium view={view} groups={groups} />
        </div>
      )}

      <Card>
        <h2 className="h2 mb-3">{es.results.standings}</h2>
        <ol className="flex flex-col gap-2" data-testid="ranking">
          {ranked.map((s) => {
            const team = view.teams[s.slot];
            const c = team ? colorFor(team) : null;
            const tied = ranked.filter((o) => o.rank === s.rank).length > 1;
            return (
              <li
                key={s.slot}
                className="rank-row"
                data-testid="rank-row"
                data-rank={s.rank}
                style={{ borderColor: s.rank === 1 ? 'var(--color-gold)' : undefined }}
              >
                <span className="rank-pos">
                  <b className={s.rank === 1 ? 'year text-gold' : 'year'} aria-hidden>
                    {es.results.position(s.rank)}
                  </b>
                  <span className="sr-only">{es.results.positionLabel(s.rank)}</span>
                  {tied ? <span className="tie-tag">{es.results.tie}</span> : null}
                </span>
                {c ? <TeamShape shape={c.shape} color={c.hex} /> : null}
                <span className="min-w-0 flex-1">
                  <b className="block truncate">{s.name ?? es.common.team(s.slot)}</b>
                  <span className="rank-bar" aria-hidden>
                    <i style={{ width: `${String(Math.round((s.cards / maxBar) * 100))}%`, background: c?.hex }} />
                  </span>
                </span>
                <span className="rank-score">
                  <b className="year">{es.common.cards(s.cards)}</b>
                  <small>
                    <Pick width={11} spent={s.tokens === 0} />
                    <span aria-hidden>{s.tokens}</span>
                    <span className="sr-only">{es.results.tokens(s.tokens)}</span>
                  </small>
                </span>
              </li>
            );
          })}
        </ol>
        <p className="mt-3 text-sm text-muted-foreground">{es.results.tokensNote}</p>
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
