import useEmblaCarousel from 'embla-carousel-react';
import { ChevronLeft, ChevronRight, Lock } from 'lucide-react';
import { useCallback, useEffect, useMemo, type KeyboardEvent, type ReactNode } from 'react';
import { es } from '../i18n/es';
import { gapLabel } from '../lib/teams';
import type { CardPublic } from '../protocol/types';
import { YearCard } from './MysteryCard';

export type CarouselMode = 'readonly' | 'place' | 'object';

const GAP_W = 112;
const CARD_W = 100;

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
}: Props) {
  const interactive = mode !== 'readonly';
  const options = useMemo(
    () => ({
      align: 'start' as const,
      containScroll: false as const,
      slidesToScroll: 2,
      watchDrag: interactive,
      duration: 22,
    }),
    [interactive],
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
      <div className="relative overflow-hidden py-3" style={{ minHeight: 190 }}>
        <div className="mx-auto" style={{ width: GAP_W }}>
          <div ref={viewportRef} style={{ overflow: 'visible' }}>
            <div className="flex">
              {Array.from({ length: gaps }, (_, i) => {
                const card = cards[i];
                return (
                  <GapAndCard
                    key={card?.instanceId ?? `gap-${String(i)}`}
                    index={i}
                    total={gaps}
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
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">{mystery}</div>
        ) : null}
      </div>

      <div className="mt-1 flex items-center justify-center gap-3">
        {interactive ? (
          <button
            type="button"
            className="btn btn-soft !px-3"
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
          className="min-h-[3rem] min-w-[10rem] flex-1 text-center font-display text-xl font-semibold leading-tight"
        >
          <span className="block">{label}</span>
          <span className="block text-sm font-semibold text-muted-foreground">
            {blocked ? es.timeline.blocked : es.timeline.slotOf(clamped, gaps)}
          </span>
        </p>
        {interactive ? (
          <button
            type="button"
            className="btn btn-soft !px-3"
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
    </section>
  );
}

function GapAndCard({
  index,
  total,
  card,
  selected,
  blocked,
  highlight,
}: {
  index: number;
  total: number;
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
        <div
          className="flex h-[140px] w-[104px] items-center justify-center rounded-clay border-4 border-dashed"
          style={{
            borderColor: selected ? 'var(--color-primary)' : 'var(--color-border)',
            opacity: index < total ? 1 : 0,
          }}
        >
          {blocked ? <Lock size={22} className="text-muted-foreground" /> : null}
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
