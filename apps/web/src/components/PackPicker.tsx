import {
  AudioLines,
  Castle,
  Check,
  Disc3,
  Flame,
  Guitar,
  MicVocal,
  Music,
  Piano,
  Radio,
  Sparkles,
  Zap,
  type LucideIcon,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import { es } from '../i18n/es';
import type { CatalogPack } from '../protocol/types';
import { Button } from './ui';

/** Iconos de los packs por el nombre que publica el servidor (`catalog/packs.json`). Sin coincidencia: `Music`. */
const PACK_ICONS: Record<string, LucideIcon> = {
  'disc-3': Disc3,
  guitar: Guitar,
  'audio-lines': AudioLines,
  'mic-vocal': MicVocal,
  flame: Flame,
  castle: Castle,
  sparkles: Sparkles,
  radio: Radio,
  piano: Piano,
  zap: Zap,
};

function packIcon(name: string): LucideIcon {
  return PACK_ICONS[name] ?? Music;
}

type PacksState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'ready'; packs: CatalogPack[] };

function usePacks(): { state: PacksState; reload: () => void } {
  const [state, setState] = useState<PacksState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let alive = true;
    setState({ status: 'loading' });
    api.packs().then(
      (packs) => {
        if (alive) setState({ status: 'ready', packs });
      },
      () => {
        if (alive) setState({ status: 'error' });
      },
    );
    return () => {
      alive = false;
    };
  }, [attempt]);
  const reload = useCallback(() => {
    setAttempt((n) => n + 1);
  }, []);
  return { state, reload };
}

/** Selector múltiple de packs de géneros. Siempre queda al menos uno elegido. */
export function PackPicker({
  value,
  onChange,
  layout = 'grid',
  onTotal,
}: {
  value: string[];
  onChange: (slugs: string[]) => void;
  /** `list`: una tarjeta por fila con la descripción completa; el total lo pinta quien llama vía `onTotal`. */
  layout?: 'grid' | 'list';
  onTotal?: (total: number | null) => void;
}) {
  const { state, reload } = usePacks();
  const list = layout === 'list';

  // Si el servidor ya no conoce los packs guardados o no tienen canciones, se elige el primero con canciones.
  useEffect(() => {
    if (state.status !== 'ready') return;
    const known = value.filter((s) => state.packs.some((p) => p.slug === s && p.count > 0));
    if (known.length === value.length && known.length > 0) return;
    const fallback = known.length > 0 ? known : state.packs.filter((p) => p.count > 0).slice(0, 1).map((p) => p.slug);
    if (fallback.length > 0) onChange(fallback);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  const toggle = (slug: string) => {
    if (value.includes(slug)) {
      if (value.length > 1) onChange(value.filter((s) => s !== slug));
    } else {
      onChange([...value, slug]);
    }
  };

  const total =
    state.status === 'ready'
      ? state.packs.filter((p) => value.includes(p.slug)).reduce((sum, p) => sum + p.count, 0)
      : null;

  useEffect(() => {
    onTotal?.(total);
  }, [total, onTotal]);

  return (
    <div className="flex flex-col gap-3" data-testid="pack-picker">
      <div className={list ? 'sr-only' : undefined}>
        <span className="font-bold" id="packs-legend">
          {es.packs.title}
        </span>
        <p className="help">{es.packs.hint}</p>
      </div>

      {state.status === 'loading' ? (
        <div className={list ? 'flex flex-col gap-3' : 'grid grid-cols-2 gap-3'} role="status" aria-label={es.packs.loading}>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="pack-skeleton" />
          ))}
        </div>
      ) : null}

      {state.status === 'error' ? (
        <div className="notice flex-col items-stretch" role="alert">
          <p>{es.packs.error}</p>
          <Button variant="secondary" onClick={reload}>
            {es.common.retry}
          </Button>
        </div>
      ) : null}

      {state.status === 'ready' ? (
        <div role="group" aria-labelledby="packs-legend" className={list ? 'flex flex-col gap-3' : 'grid grid-cols-2 gap-3'}>
          {state.packs.map((p) => {
            const Icon = packIcon(p.icon);
            const on = value.includes(p.slug);
            const empty = p.count === 0;
            return (
              <button
                key={p.slug}
                type="button"
                role="checkbox"
                aria-checked={on}
                disabled={empty}
                className={list ? 'pack pack-row' : 'pack'}
                data-slug={p.slug}
                onClick={() => {
                  toggle(p.slug);
                }}
              >
                <Icon className="pack-icon" size={28} aria-hidden />
                <span className="tick" aria-hidden>
                  <Check size={16} strokeWidth={3} />
                </span>
                <span className="pack-name">{p.name}</span>
                <span className="pack-desc">{p.description}</span>
                <span className="pack-count">{empty ? es.packs.empty : es.packs.count(p.count)}</span>
              </button>
            );
          })}
        </div>
      ) : null}

      {total !== null && !list ? (
        <p role="status" className="flex items-center gap-2 font-semibold" data-testid="pack-total">
          <Music size={18} aria-hidden className="text-accent" />
          {es.packs.total(total)}
        </p>
      ) : null}
      {value.length === 1 && state.status === 'ready' ? <p className="help">{es.packs.atLeastOne}</p> : null}
    </div>
  );
}

/** Los packs elegidos, en solo lectura (equipos que no son el anfitrión). */
export function PackSummary({ slugs }: { slugs: string[] }) {
  const { state } = usePacks();
  const chosen =
    state.status === 'ready'
      ? slugs.map((s) => state.packs.find((p) => p.slug === s) ?? { slug: s, name: s, icon: '', description: '', count: 0 })
      : [];
  return (
    <div className="flex flex-col gap-2" data-testid="pack-summary">
      <span className="overline">{es.packs.chosen}</span>
      {state.status === 'loading' ? <div className="pack-skeleton" style={{ minHeight: 40 }} /> : null}
      {state.status === 'error' ? <p className="help">{es.packs.error}</p> : null}
      <ul className="flex flex-wrap gap-2">
        {chosen.map((p) => {
          const Icon = packIcon(p.icon);
          return (
            <li key={p.slug} className="chip">
              <Icon size={16} aria-hidden className="text-primary-light" />
              {p.name}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
