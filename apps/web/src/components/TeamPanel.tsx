import clsx from 'clsx';
import { Coins, Wifi, WifiOff } from 'lucide-react';
import { es } from '../i18n/es';
import { colorFor, teamName } from '../lib/teams';
import type { TeamView } from '../protocol/types';
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
  return (
    <div
      className={clsx('clay min-w-0 flex-1 p-2.5', active && 'ring-4 ring-accent')}
      aria-current={active ? 'true' : undefined}
      data-testid={`team-${String(team.slot)}`}
    >
      <div className="flex items-center gap-1.5">
        <TeamShape shape={c.shape} color={c.hex} size={18} />
        <span className="truncate text-sm font-bold">
          {teamName(team)}
          {you ? ` (${es.lobby.youAre.toLowerCase()})` : ''}
        </span>
        <span className="ml-auto" title={team.connected ? es.team.online : es.team.offline}>
          {team.connected ? (
            <Wifi size={14} aria-hidden className="text-green-700" />
          ) : (
            <WifiOff size={14} aria-hidden className="text-destructive" />
          )}
          <span className="sr-only-live">{team.connected ? es.team.online : es.team.offline}</span>
        </span>
      </div>
      <div className="mt-1.5 flex items-center justify-between gap-2">
        <span className="year text-base" aria-label={es.team.progress(team.cardCount, target)}>
          {team.cardCount}/{target}
        </span>
        <span className="flex items-center gap-1 text-sm font-bold" aria-label={es.team.tokens(team.tokens)}>
          <Coins size={16} aria-hidden className="text-amber-600" />
          {team.tokens}
        </span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-border" aria-hidden>
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-300"
          style={{ width: `${String(pct)}%` }}
        />
      </div>
    </div>
  );
}
