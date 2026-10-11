import clsx from 'clsx';
import { Wifi, WifiOff } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { es } from '../i18n/es';
import { colorFor, teamName } from '../lib/teams';
import type { TeamView } from '../protocol/types';
import { Pick } from './Pick';
import { TeamShape } from './ui';

export function TeamPanel({
  team,
  target,
  active,
  you,
}: {
  team: TeamView;
  target: number;
  active?: boolean;
  you?: boolean;
}) {
  const c = colorFor(team);
  const pct = Math.min(100, Math.round((team.cardCount / Math.max(1, target)) * 100));
  const hasTokens = team.tokens > 0;

  // El número baja con un pequeño rebote cuando se gasta una ficha.
  const prev = useRef(team.tokens);
  const [bump, setBump] = useState(false);
  useEffect(() => {
    if (team.tokens < prev.current) {
      setBump(true);
      const id = setTimeout(() => {
        setBump(false);
      }, 300);
      prev.current = team.tokens;
      return () => {
        clearTimeout(id);
      };
    }
    prev.current = team.tokens;
    return undefined;
  }, [team.tokens]);

  return (
    <div
      className={clsx('tp', active && 'active')}
      style={{ '--tc': c.hex } as React.CSSProperties}
      aria-current={active ? 'true' : undefined}
      data-testid={`team-${String(team.slot)}`}
    >
      {active ? <span className="turn-tag">{es.team.turn}</span> : null}
      <div className="flex items-center gap-1.5">
        <TeamShape shape={c.shape} color={c.hex} size={18} />
        <span className="min-w-0 flex-1 truncate text-sm font-bold">
          {teamName(team)}
          {you ? ` (${es.lobby.youAre.toLowerCase()})` : ''}
        </span>
        <span title={team.connected ? es.team.online : es.team.offline}>
          {team.connected ? (
            <Wifi size={16} aria-hidden className="text-accent" />
          ) : (
            <WifiOff size={16} aria-hidden className="text-magenta-light" />
          )}
          <span className="sr-only-live">{team.connected ? es.team.online : es.team.offline}</span>
        </span>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="year min-w-[3.2rem] text-[18px] leading-none" aria-label={es.team.progress(team.cardCount, target)}>
          {team.cardCount}/{target}
        </span>
        <span
          className="flex items-center gap-1 text-sm font-bold text-gold"
          aria-label={es.team.tokens(team.tokens)}
        >
          <Pick width={16} spent={!hasTokens} />
          <span className={clsx('inline-block', bump && 'tok-bump')}>
            {team.tokens}
          </span>
        </span>
      </div>
      <div className="bar" aria-hidden>
        <i style={{ width: `${String(pct)}%` }} />
      </div>
    </div>
  );
}
