import clsx from 'clsx';
import useEmblaCarousel from 'embla-carousel-react';
import { useReducedMotion } from 'framer-motion';
import { ChevronLeft, ChevronRight, Info, Lock, Plus } from 'lucide-react';
import { useCallback, useEffect, useMemo, type KeyboardEvent, type ReactNode } from 'react';
import { es } from '../i18n/es';
import { groupByYear, toRealIndex, toStop, type YearGroup } from '../lib/groups';
import { gapLabel } from '../lib/teams';
import type { CardPublic } from '../protocol/types';
import { YearCard } from './MysteryCard';

export type CarouselMode = 'readonly' | 'place' | 'object';

const GAP_W = 112;
const CARD_W = 112;
/** Carta suelta, carta apilada y altura máxima de una pila (≈ 2,2 cartas). */
const CARD_H = 148;
const STACK_H = 116;
const STACK_GAP = 6;
const PILE_MAX = 326;
const TL_MIN_H = 232;

/** Distancia vertical entre cartas de una pila de `n` y altura total. */
function pileMetrics(n: number): { step: number; height: number } {
  if (n <= 1) return { step: 0, height: CARD_H };
  if (n === 2) return { step: STACK_H + STACK_GAP, height: 2 * STACK_H + STACK_GAP };
  const step = Math.min(76, (PILE_MAX - STACK_H) / (n - 1));
  return { step, height: STACK_H + step * (n - 1) };
}

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
 * Slides alternos [hueco, grupo, hueco, ...] agrupados de 2 en 2: cada parada (snap) es un límite de grupo.
 * Las cartas consecutivas del mismo año forman un grupo y se apilan en vertical (no hay hueco entre ellas).
 * Los índices de entrada y de salida son índices reales de la línea; los de salida siempre son límites de grupo.
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
  const years = useMemo(() => cards.map((c) => c.year), [cards]);
  const groups = useMemo(() => groupByYear(years), [years]);
  const gaps = groups.length + 1;
  const clamped = toStop(groups, selectedIndex);
  const blockedStop = blockedIndex === null ? null : toStop(groups, blockedIndex);
  const tlHeight = useMemo(
    () => Math.max(TL_MIN_H, ...groups.map((g) => pileMetrics(g.end - g.start).height + 16)),
    [groups],
  );

  // Embla -> padre.
  useEffect(() => {
    if (!embla) return;
    const onSelect = () => {
      onIndexChange?.(toRealIndex(groups, embla.selectedScrollSnap()));
    };
    embla.on('select', onSelect);
    return () => {
      embla.off('select', onSelect);
    };
  }, [embla, onIndexChange, groups]);

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

  const blocked = blockedStop !== null && clamped === blockedStop;
  const label = gapLabel(years, toRealIndex(groups, clamped));

  return (
    <section
      aria-roledescription="carrusel"
      aria-label={es.timeline.label}
      className="w-full"
      onKeyDown={onKeyDown}
      data-testid="timeline"
      data-mode={mode}
    >
      <div className="tl" style={{ height: tlHeight }}>
        <div className="absolute inset-y-0 left-1/2 flex items-center" style={{ width: GAP_W, marginLeft: -GAP_W / 2 }}>
          <div ref={viewportRef} className="w-full" style={{ overflow: 'visible' }}>
            <div className="flex items-center">
              {Array.from({ length: gaps }, (_, i) => {
                const group = groups[i];
                const pile = group ? cards.slice(group.start, group.end) : [];
                return (
                  <GapAndGroup
                    key={pile[0]?.instanceId ?? `gap-${String(i)}`}
                    index={i}
                    group={group}
                    cards={pile}
                    selected={i === clamped}
                    blocked={blockedStop === i}
                    highlightId={highlightId}
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

function GapAndGroup({
  index,
  group,
  cards,
  selected,
  blocked,
  highlightId,
}: {
  index: number;
  group: YearGroup | undefined;
  cards: CardPublic[];
  selected: boolean;
  blocked: boolean;
  highlightId: string | null;
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
      {group ? (
        <div
          style={{ flex: `0 0 ${String(CARD_W)}px`, minWidth: 0 }}
          className="flex items-center justify-center"
          data-group={cards.length}
        >
          <Pile cards={cards} highlightId={highlightId} />
        </div>
      ) : null}
    </>
  );
}

/** Cartas del mismo año apiladas en vertical. Una sola carta se pinta como siempre. */
function Pile({ cards, highlightId }: { cards: CardPublic[]; highlightId: string | null }) {
  const first = cards[0];
  if (!first) return null;
  if (cards.length === 1) {
    return <YearCard card={first} highlight={first.instanceId === highlightId} />;
  }
  const { step, height } = pileMetrics(cards.length);
  return (
    <div className="pile" style={{ height, width: 104 }} role="group" aria-label={es.timeline.pile(first.year, cards.length)}>
      {cards.map((c, i) => (
        <div key={c.instanceId} className="pile-item" style={{ top: i * step, zIndex: i + 1 }}>
          <YearCard card={c} stack highlight={c.instanceId === highlightId} />
        </div>
      ))}
    </div>
  );
}
