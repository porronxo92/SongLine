import { motion, useReducedMotion } from 'framer-motion';
import { Music2 } from 'lucide-react';
import { es } from '../i18n/es';
import type { CardPublic } from '../protocol/types';

/** Carta de la línea del tiempo (ya revelada). */
export function YearCard({ card, highlight }: { card: CardPublic; highlight?: boolean }) {
  return (
    <div
      className="flex h-[132px] w-[96px] flex-col items-center justify-between rounded-clay p-2 text-center shadow-clay"
      style={{
        background: highlight ? 'var(--color-accent)' : '#fff',
        border: highlight ? '3px solid #b45309' : '3px solid var(--color-border)',
      }}
      aria-label={`${String(card.year)}, ${card.title}, ${card.artist}`}
    >
      <span className="year text-[1.7rem] leading-none">{card.year}</span>
      <span className="line-clamp-2 text-[0.72rem] font-bold leading-tight">{card.title}</span>
      <span className="line-clamp-1 text-[0.68rem] font-semibold leading-tight text-muted-foreground">
        {card.artist}
      </span>
    </div>
  );
}

/** Carta misteriosa. Se voltea cuando llega `card` (REVEAL). */
export function MysteryCard({ card, large }: { card?: CardPublic | null; large?: boolean }) {
  const reduce = useReducedMotion() === true;
  const w = large ? 200 : 104;
  const h = large ? 270 : 140;
  const flipped = Boolean(card);
  const face: React.CSSProperties = {
    position: 'absolute',
    inset: 0,
    backfaceVisibility: 'hidden',
    WebkitBackfaceVisibility: 'hidden',
    borderRadius: 'var(--radius-lg)',
    boxShadow: 'var(--shadow-clay)',
  };
  return (
    <div style={{ width: w, height: h, perspective: 900 }} aria-label={flipped ? undefined : es.game.mystery}>
      <motion.div
        style={{ width: '100%', height: '100%', position: 'relative', transformStyle: 'preserve-3d' }}
        initial={false}
        animate={{ rotateY: flipped ? 180 : 0 }}
        transition={reduce ? { duration: 0 } : { duration: 0.7, ease: 'easeInOut' }}
      >
        <div
          style={{
            ...face,
            background: 'linear-gradient(145deg, #8b5cf6, #ec4899)',
            border: '4px solid rgba(255,255,255,0.85)',
          }}
          className="flex flex-col items-center justify-center gap-2 text-white"
          aria-hidden={flipped}
        >
          <Music2 size={large ? 56 : 32} aria-hidden />
          <span className="year" style={{ fontSize: large ? '4rem' : '2.4rem', lineHeight: 1 }}>
            ?
          </span>
        </div>
        <div
          style={{ ...face, transform: 'rotateY(180deg)', background: '#fff', border: '4px solid #f59e0b' }}
          className="flex flex-col items-center justify-between p-3 text-center"
          aria-hidden={!flipped}
        >
          {card ? (
            <>
              <span className="year" style={{ fontSize: large ? '3.4rem' : '2rem', lineHeight: 1 }}>
                {card.year}
              </span>
              <div>
                <p className={large ? 'text-lg font-bold leading-tight' : 'text-sm font-bold leading-tight'}>
                  {card.title}
                </p>
                <p className="mt-1 text-sm font-semibold leading-tight text-muted-foreground">{card.artist}</p>
                {card.note ? <p className="mt-1 text-xs text-muted-foreground">{card.note}</p> : null}
              </div>
            </>
          ) : null}
        </div>
      </motion.div>
    </div>
  );
}
