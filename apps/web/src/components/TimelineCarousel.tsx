import clsx from 'clsx';
import useEmblaCarousel from 'embla-carousel-react';
import { useReducedMotion } from 'framer-motion';
import { ChevronLeft, ChevronRight, Info, Lock, Plus } from 'lucide-react';
import { useCallback, useEffect, useMemo, type KeyboardEvent, type ReactNode } from 'react';
import { es } from '../i18n/es';
import { gapLabel } from '../lib/teams';
import type { CardPublic } from '../protocol/types';
import { YearCard } from './MysteryCard';

export type CarouselMode = 'readonly' | 'place' | 'object';

const GAP_W = 112;
const CARD_W = 112;

interface Props {
  cards: CardPublic[];
  mode: CarouselMode;
  /** Carta misteriosa fija en el centro. */
  mystery?: ReactNode;
  selectedIndex: number;
  onIndexChange?: (index: number) => void;
  /** Hueco bloqueado (en `object`: el que eligió el equipo activo). */
  blockedIndex?: number | null;
  highlightId?: string | null;
  /** Pista de años iguales bajo la etiqueta del hueco (una vez por pantalla). */
  equalHint?: boolean;
}

/**
 * La carta misteriosa queda fija en el centro y la línea se desliza.
 * Slides alternos [hueco, carta, hueco, ...] agrupados de 2 en 2: cada parada (snap) es un hueco.
 */
export function TimelineCarousel({
  cards,
  mode,
  mystery,
  selectedIndex,
  onIndexChange,
  blockedIndex = null,
  highlightId = null,
  equalHint = false,
}: Props) {
  const interactive = mode !== 'readonly';
  const reduce = useReducedMotion() === true;
  const options = useMemo(
    () => ({
      align: 'start' as const,
      containScroll: false as const,
      slidesToScroll: 2,
      watchDrag: interactive,
      duration: reduce ? 8 : 22,
    }),
    [interactive, reduce],
  );
  const [viewportRef, embla] = useEmblaCarousel(options);
  const gaps = cards.length + 1;
  const years = useMemo(() => cards.map((c) => c.year), [cards]);
  const clamped = Math.max(0, Math.min(gaps - 1, selectedIndex));

  // Embla -> padre.
  useEffect(() => {
    if (!embla) return;
    const onSelect = () => {
      onIndexChange?.(embla.selectedScrollSnap());
    };
    embla.on('select', onSelect);
    return () => {
      embla.off('select', onSelect);
    };
  }, [embla, onIndexChange]);

  // Padre -> Embla (y tras reinicializar por cambio de cartas).
  useEffect(() => {
    if (!embla) return;
    const sync = (jump: boolean) => {
      if (embla.selectedScrollSnap() !== clamped && clamped < embla.scrollSnapList().length) {
        embla.scrollTo(clamped, jump);
      }
    };
    sync(false);
    const onReInit = () => {
      sync(true);
    };
    embla.on('reInit', onReInit);
    return () => {
      embla.off('reInit', onReInit);
    };
  }, [embla, clamped, gaps]);

  const go = useCallback(
    (dir: 1 | -1) => {
      if (!embla) return;
      if (dir === 1) embla.scrollNext();
      else embla.scrollPrev();
    },
    [embla],
  );

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (!interactive) return;
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      go(-1);
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      go(1);
    }
  };

  const blocked = blockedIndex !== null && clamped === blockedIndex;
  const label = gapLabel(years, clamped);

  return (
    <section
      aria-roledescription="carrusel"
      aria-label={es.timeline.label}
      className="w-full"
      onKeyDown={onKeyDown}
      data-testid="timeline"
      data-mode={mode}
    >
      <div className="tl">
        <div className="absolute inset-y-0 left-1/2 flex items-center" style={{ width: GAP_W, marginLeft: -GAP_W / 2 }}>
          <div ref={viewportRef} className="w-full" style={{ overflow: 'visible' }}>
            <div className="flex items-center">
              {Array.from({ length: gaps }, (_, i) => {
                const card = cards[i];
                return (
                  <GapAndCard
                    key={card?.instanceId ?? `gap-${String(i)}`}
                    index={i}
                    card={card}
                    selected={i === clamped}
                    blocked={blockedIndex === i}
                    highlight={card !== undefined && card.instanceId === highlightId}
                  />
                );
              })}
            </div>
          </div>
        </div>
        {mystery ? (
          <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center">{mystery}</div>
        ) : null}
      </div>

      <div className="mt-1 flex items-center justify-center gap-2">
        {interactive ? (
          <button
            type="button"
            className="btn btn-secondary btn-icon"
            aria-label={es.timeline.prev}
            disabled={clamped <= 0}
            onClick={() => {
              go(-1);
            }}
          >
            <ChevronLeft aria-hidden />
          </button>
        ) : null}
        <p
          role="status"
          aria-live="polite"
          data-testid="gap-label"
          className="tl-label"
        >
          <b>{label}</b>
          <span>{blocked ? es.timeline.blocked : es.timeline.slotOf(clamped, gaps)}</span>
        </p>
        {interactive ? (
          <button
            type="button"
            className="btn btn-secondary btn-icon"
            aria-label={es.timeline.next}
            disabled={clamped >= gaps - 1}
            onClick={() => {
              go(1);
            }}
          >
            <ChevronRight aria-hidden />
          </button>
        ) : null}
      </div>
      {equalHint ? (
        <p className="ex-hint" data-testid="equal-hint">
          <Info size={14} aria-hidden />
          <span>{es.explain.equalHint}</span>
        </p>
      ) : null}
    </section>
  );
}

function GapAndCard({
  index,
  card,
  selected,
  blocked,
  highlight,
}: {
  index: number;
  card: CardPublic | undefined;
  selected: boolean;
  blocked: boolean;
  highlight: boolean;
}) {
  return (
    <>
      <div
        style={{ flex: `0 0 ${String(GAP_W)}px`, minWidth: 0 }}
        className="flex items-center justify-center"
        data-gap={index}
        aria-hidden
      >
        <div className={clsx('slot', selected && !blocked && 'sel', blocked && 'locked')}>
          {blocked ? <Lock size={22} /> : <Plus size={20} />}
        </div>
      </div>
      {card ? (
        <div
          style={{ flex: `0 0 ${String(CARD_W)}px`, minWidth: 0 }}
          className="flex items-center justify-center"
        >
          <YearCard card={card} highlight={highlight} />
        </div>
      ) : null}
    </>
  );
}
