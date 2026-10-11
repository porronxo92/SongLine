import { MapPin } from 'lucide-react';
import { colorFor, teamName } from '../lib/teams';
import { placementSentence } from '../lib/placement';
import type { TeamView } from '../protocol/types';
import { Years } from './RevealExplain';

/**
 * Una línea que dice dónde puso la carta el equipo activo.
 * `years`: años de su línea antes de insertar la carta. `index`: `turn.placedIndex`.
 */
export function PlacementSummary({
  team,
  years,
  index,
  mine,
}: {
  team: TeamView;
  years: readonly number[];
  index: number | null;
  mine: boolean;
}) {
  if (index === null) return null;
  const c = colorFor(team);
  return (
    <p className="placed" style={{ '--tc': c.hex } as React.CSSProperties} data-testid="placement-summary">
      <MapPin size={20} aria-hidden className="shrink-0" style={{ color: c.hex }} />
      <span>
        <Years text={placementSentence(years, index, teamName(team), mine)} />
      </span>
    </p>
  );
}
