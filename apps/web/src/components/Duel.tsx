import clsx from 'clsx';
import { Crown, Zap } from 'lucide-react';
import { useEffect, useState } from 'react';
import { es } from '../i18n/es';
import { colorFor, gapLabel, teamName } from '../lib/teams';
import type { Outcome, TeamView } from '../protocol/types';
import { Pick } from './Pick';
import { TeamShape } from './ui';

const SPARKS: [number, number][] = [
  [-36, -22],
  [36, -22],
  [-26, 30],
  [26, 30],
];

/** La ficha vuela hacia el hueco disputado y se rompe en chispas. Es solo decoración. */
function TokenSpend() {
  const [alive, setAlive] = useState(true);
  useEffect(() => {
    const id = setTimeout(() => {
      setAlive(false);
    }, 1400);
    return () => {
      clearTimeout(id);
    };
  }, []);
  if (!alive) return null;
  return (
    <div aria-hidden>
      <span className="pick-fly">
        <Pick />
      </span>
      {SPARKS.map(([x, y]) => (
        <span key={`${String(x)}${String(y)}`} className="spark" style={{ '--x': `${String(x)}px`, '--y': `${String(y)}px` } as React.CSSProperties} />
      ))}
    </div>
  );
}

interface Props {
  original: TeamView;
  objector: TeamView;
  years: number[];
  originalIndex: number;
  objectionIndex: number;
  /** Sin resultado: el duelo sigue abierto. */
  result?: { outcome: Outcome; objectionOk: boolean | null } | null;
}

/** Choque entre el equipo que colocó la carta y el que objeta por otro hueco. */
export function Duel({ original, objector, years, originalIndex, objectionIndex, result = null }: Props) {
  const oc = colorFor(original);
  const bc = colorFor(objector);
  const objectorWins = result?.outcome === 'stolen';
  const originalWins = result?.outcome === 'kept';
  const nobody = result?.outcome === 'discarded';

  const badge = !result ? (
    <span className="badge badge-mag">
      <Zap size={14} aria-hidden />
      {es.duel.badge}
    </span>
  ) : objectorWins ? (
    <span className="badge badge-gold">
      <Crown size={14} aria-hidden />
      {es.duel.right}
    </span>
  ) : (
    <span className="badge badge-mag">
      <Zap size={14} aria-hidden />
      {es.duel.failed}
    </span>
  );

  return (
    <div className="duel" data-testid="duel" data-state={result ? result.outcome : 'open'}>
      {!result ? <TokenSpend /> : null}
      <div className="mb-3 flex flex-col items-center gap-1.5 text-center">
        {badge}
        <span className="glitch" data-t={gapLabel(years, objectionIndex)}>
          {gapLabel(years, objectionIndex)}
        </span>
      </div>
      <div className="duel-teams">
        <div
          className={clsx('fighter', originalWins && 'win', (objectorWins || nobody) && 'lose')}
          style={{ '--tc': oc.hex } as React.CSSProperties}
        >
          <TeamShape shape={oc.shape} color={oc.hex} size={26} />
          <b>{teamName(original)}</b>
          <small>
            {es.duel.original}
            <br />
            {gapLabel(years, originalIndex)}
          </small>
        </div>
        <div className="vs" aria-hidden style={result ? { animation: 'none' } : undefined}>
          {es.duel.vs}
        </div>
        <div
          className={clsx('fighter', objectorWins && 'win', (originalWins || nobody) && 'lose')}
          style={{ '--tc': bc.hex } as React.CSSProperties}
        >
          <TeamShape shape={bc.shape} color={bc.hex} size={26} />
          <b>{teamName(objector)}</b>
          <small>
            {es.duel.objecting}
            <br />
            {gapLabel(years, objectionIndex)}
          </small>
        </div>
      </div>
      {!result ? (
        <>
          <div className="tension" aria-hidden style={{ '--tc': oc.hex } as React.CSSProperties}>
            <i />
            <i style={{ '--tc': bc.hex } as React.CSSProperties} />
          </div>
          <p className="help mt-2 text-center">{es.duel.checking}</p>
        </>
      ) : null}
    </div>
  );
}
