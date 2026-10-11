import { useCallback, useEffect, useRef, useState } from 'react';
import { serverNow } from '../store/room';
import { shouldAutoSend } from '../lib/hints';
import { getVibrateEnabled } from '../lib/session';

/** Segundos que faltan hasta `deadlineTs` (hora del servidor). `null` si no hay plazo. */
export function useCountdown(deadlineTs: number | null | undefined): number | null {
  const [, force] = useState(0);
  useEffect(() => {
    if (deadlineTs === null || deadlineTs === undefined) return;
    const id = setInterval(() => {
      force((n) => n + 1);
    }, 250);
    return () => {
      clearInterval(id);
    };
  }, [deadlineTs]);
  if (deadlineTs === null || deadlineTs === undefined) return null;
  return Math.max(0, Math.ceil(deadlineTs - serverNow()));
}

/** Fracción restante (0..1) de una ventana de `totalS` segundos. */
export function useRemainingFraction(deadlineTs: number | null | undefined, totalS: number): number {
  const s = useCountdown(deadlineTs);
  if (s === null || totalS <= 0) return 0;
  return Math.min(1, s / totalS);
}

/** Mantiene la pantalla encendida mientras `active`. */
export function useWakeLock(active: boolean): void {
  useEffect(() => {
    if (!active || !('wakeLock' in navigator)) return;
    let sentinel: WakeLockSentinel | null = null;
    let cancelled = false;
    const request = () => {
      navigator.wakeLock
        .request('screen')
        .then((s) => {
          if (cancelled) void s.release();
          else sentinel = s;
        })
        .catch(() => undefined);
    };
    const onVisible = () => {
      if (document.visibilityState === 'visible') request();
    };
    request();
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', onVisible);
      void sentinel?.release();
    };
  }, [active]);
}

/** Llama a `fn` como mucho `perSecond` veces por segundo, enviando siempre el último valor. */
export function useThrottled<A extends unknown[]>(fn: (...args: A) => void, perSecond: number) {
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const last = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pending = useRef<A | null>(null);
  const gap = 1000 / perSecond;

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  return useCallback(
    (...args: A) => {
      const now = Date.now();
      const wait = last.current + gap - now;
      if (wait <= 0) {
        last.current = now;
        fnRef.current(...args);
        return;
      }
      pending.current = args;
      timer.current ??= setTimeout(() => {
        timer.current = null;
        last.current = Date.now();
        const a = pending.current;
        pending.current = null;
        if (a) fnRef.current(...a);
      }, wait);
    },
    [gap],
  );
}

export function vibrate(pattern: number | number[]): void {
  if (!getVibrateEnabled()) return;
  try {
    navigator.vibrate(pattern);
  } catch {
    /* no soportado */
  }
}

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const on = () => {
      setReduced(mq.matches);
    };
    mq.addEventListener('change', on);
    return () => {
      mq.removeEventListener('change', on);
    };
  }, []);
  return reduced;
}

/**
 * Cuenta atrás del límite de 60 s tras pedir una pista. Cuando llega a 0 llama a `onExpire` una vez
 * por cada `deadlineTs` (el servidor cambia el plazo al pasar de colocar a responder).
 */
export function useHintDeadline(
  deadlineTs: number | null | undefined,
  paused: boolean,
  enabled: boolean,
  onExpire: () => void,
): number | null {
  const secs = useCountdown(deadlineTs);
  const handled = useRef<number | null>(null);
  const cb = useRef(onExpire);
  cb.current = onExpire;
  useEffect(() => {
    const ts = deadlineTs ?? null;
    if (enabled && shouldAutoSend(ts, secs, handled.current, paused)) {
      handled.current = ts;
      cb.current();
    }
  });
  return secs;
}
