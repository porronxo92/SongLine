import clsx from 'clsx';
import { motion, useReducedMotion } from 'framer-motion';
import { useId } from 'react';
import { es } from '../i18n/es';
import { decadeLabel, decadeVar } from '../lib/decade';
import type { CardPublic } from '../protocol/types';
import { useRoom } from '../store/room';

/** Carta de la línea del tiempo (ya revelada). Sin portada: un vinilo del color de la década. */
export function YearCard({ card, highlight, stack }: { card: CardPublic; highlight?: boolean; stack?: boolean }) {
  return (
    <div className="relative">
      <div
        className={clsx('ycard', stack && 'stack', highlight && 'hit')}
        style={{ '--dc': decadeVar(card.year) } as React.CSSProperties}
        aria-label={`${String(card.year)}, ${card.title}, ${card.artist}`}
      >
        <span className="y">{card.year}</span>
        <span className="t">{card.title}</span>
        <span className="a">{card.artist}</span>
      </div>
      {highlight ? <span className="ring-hit" aria-hidden /> : null}
    </div>
  );
}

function Disc({ size }: { size: number }) {
  const id = useId();
  return (
    <svg className="vinyl" width={size} height={size} viewBox="0 0 100 100" aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#7B2CBF" />
          <stop offset="1" stopColor="#FF007F" />
        </linearGradient>
      </defs>
      <circle cx="50" cy="50" r="48" fill="#0D0E15" stroke="#B77CFF" strokeOpacity=".5" strokeWidth="1.5" />
      <g fill="none" stroke="#fff" strokeOpacity=".12" strokeWidth="1">
        <circle cx="50" cy="50" r="40" />
        <circle cx="50" cy="50" r="34" />
        <circle cx="50" cy="50" r="28" />
      </g>
      <circle cx="50" cy="50" r="19" fill={`url(#${id})`} />
      <path d="M26 30A30 30 0 0 1 46 20" stroke="#fff" strokeOpacity=".35" strokeWidth="3" fill="none" strokeLinecap="round" />
    </svg>
  );
}

/** Carta misteriosa. Se voltea cuando llega `card` (REVEAL). No lleva ningún dato de la canción. */
export function MysteryCard({ card, large }: { card?: CardPublic | null; large?: boolean }) {
  const reduce = useReducedMotion() === true;
  const playing = useRoom((s) => s.audioStatus?.playing ?? s.view?.audio.playing ?? false);
  const w = large ? 200 : 104;
  const h = large ? 270 : 140;
  const flipped = Boolean(card);
  const face: React.CSSProperties = {
    position: 'absolute',
    inset: 0,
    backfaceVisibility: 'hidden',
    WebkitBackfaceVisibility: 'hidden',
  };
  return (
    <motion.div
      style={{ width: w, height: h, perspective: 900 }}
      aria-label={flipped ? undefined : es.game.mystery}
      initial={false}
      animate={reduce ? { scale: 1 } : { scale: flipped ? [1, 1, 1.04, 1] : 1 }}
      transition={reduce ? { duration: 0 } : { duration: 1, times: [0, 0.7, 0.85, 1] }}
    >
      <motion.div
        style={{ width: '100%', height: '100%', position: 'relative', transformStyle: 'preserve-3d' }}
        initial={false}
        animate={{ rotateY: flipped ? 180 : 0 }}
        transition={reduce ? { duration: 0 } : { duration: 0.7, ease: [0.65, 0, 0.35, 1] }}
      >
        <div style={face} aria-hidden={flipped}>
          <div
            className={clsx('mystery', large && 'lg', playing && 'playing')}
            style={{ width: '100%', height: '100%' }}
            role="img"
            aria-label={es.game.mystery}
          >
            <Disc size={large ? 150 : 78} />
            <span className="q">?</span>
            {playing ? (
              <span className="wave" aria-hidden>
                <i />
                <i />
                <i />
              </span>
            ) : null}
          </div>
        </div>
        <div style={{ ...face, transform: 'rotateY(180deg)' }} aria-hidden={!flipped}>
          {card ? (
            <div
              className={clsx('ycard', large && 'big')}
              style={{ '--dc': decadeVar(card.year), width: '100%', height: '100%' } as React.CSSProperties}
            >
              {large ? <span className="dec">{decadeLabel(card.year)}</span> : null}
              <span className="y">{card.year}</span>
              <div>
                <p className="t">{card.title}</p>
                <p className="a mt-1">{card.artist}</p>
                {card.note ? <p className="note mt-1">{card.note}</p> : null}
              </div>
            </div>
          ) : null}
        </div>
      </motion.div>
    </motion.div>
  );
}
