import clsx from 'clsx';
import { ArrowLeft, Circle, Diamond, Loader2, Minus, Plus, Square, Triangle } from 'lucide-react';
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react';
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { es } from '../i18n/es';
import type { Shape } from '../lib/teams';
import { useRoom } from '../store/room';

type Variant = 'primary' | 'secondary' | 'accent' | 'danger' | 'ghost';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  xl?: boolean;
  busy?: boolean;
}

export function Button({ variant = 'primary', xl, busy, className, children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      type="button"
      {...rest}
      disabled={disabled === true || busy === true}
      className={clsx('btn', `btn-${variant}`, xl && 'btn-xl', className)}
    >
      {busy ? <Loader2 className="animate-spin" size={20} aria-hidden /> : null}
      {children}
    </button>
  );
}

export function Card({
  className,
  children,
  ...rest
}: { className?: string; children: ReactNode } & HTMLAttributes<HTMLDivElement>) {
  return (
    <div {...rest} className={clsx('panel p-5', className)}>
      {children}
    </div>
  );
}

export function Spinner({ label = es.common.loading }: { label?: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-3 p-8 text-muted-foreground">
      <Loader2 className="animate-spin" aria-hidden />
      <span>{label}</span>
    </div>
  );
}

/** Marco de pantalla con título, botón de volver y acciones opcionales. */
export function Screen({
  title,
  back,
  actions,
  children,
  footer,
}: {
  title?: string;
  back?: string | (() => void);
  actions?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const navigate = useNavigate();
  return (
    <main className="screen">
      {title || back || actions ? (
        <header className="flex items-center gap-3">
          {back ? (
            <button
              type="button"
              aria-label={es.common.back}
              className="btn btn-secondary btn-icon"
              onClick={() => {
                if (typeof back === 'function') back();
                else navigate(back);
              }}
            >
              <ArrowLeft aria-hidden />
            </button>
          ) : null}
          {title ? <h1 className="screen-title min-w-0 flex-1">{title}</h1> : <span className="flex-1" />}
          {actions}
        </header>
      ) : null}
      <div className="flex flex-1 flex-col gap-4">{children}</div>
      {footer}
    </main>
  );
}

const SHAPE_ICON = { circle: Circle, triangle: Triangle, square: Square, diamond: Diamond } as const;

/** Forma de equipo (● ▲ ■ ◆) con el color relleno. */
export function TeamShape({ shape, color, size = 22 }: { shape: Shape; color: string; size?: number }) {
  const Icon = SHAPE_ICON[shape];
  return <Icon aria-hidden size={size} fill={color} color={color} strokeWidth={2.5} />;
}

/** Aviso efímero para errores de comandos. */
export function Toast() {
  const toast = useRoom((s) => s.toast);
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => {
      useRoom.setState({ toast: null });
    }, 3500);
    return () => {
      clearTimeout(id);
    };
  }, [toast]);
  if (!toast) return null;
  return (
    <div
      role="alert"
      className="toast fixed inset-x-4 z-[60] mx-auto max-w-md px-4 py-3 text-center font-semibold"
      style={{ bottom: 'max(16px, env(safe-area-inset-bottom))' }}
    >
      {toast.text}
    </div>
  );
}

export function Stepper({
  label,
  value,
  min,
  max,
  step = 1,
  format,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  format?: (n: number) => string;
  onChange: (n: number) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="font-bold">{label}</span>
      <div className="flex items-center gap-2" role="group" aria-label={label}>
        <button
          type="button"
          className="btn btn-secondary btn-icon"
          aria-label={`${es.create.less}: ${label}`}
          disabled={value <= min}
          onClick={() => {
            onChange(Math.max(min, value - step));
          }}
        >
          <Minus aria-hidden size={20} />
        </button>
        <output className="year min-w-[5rem] text-center text-lg" aria-live="polite">
          {format ? format(value) : String(value)}
        </output>
        <button
          type="button"
          className="btn btn-secondary btn-icon"
          aria-label={`${es.create.more}: ${label}`}
          disabled={value >= max}
          onClick={() => {
            onChange(Math.min(max, value + step));
          }}
        >
          <Plus aria-hidden size={20} />
        </button>
      </div>
    </div>
  );
}

/** Indicador de paso: texto visible y barras. El paso actual lleva `aria-current="step"`. */
export function StepIndicator({ current, total }: { current: number; total: number }) {
  return (
    <div className="steps">
      <p className="overline" aria-current="step">
        {es.create.step(current, total)}
      </p>
      <div className="steps-bars" aria-hidden>
        {Array.from({ length: total }, (_, i) => (
          <span key={i} className="steps-bar" data-done={i < current} />
        ))}
      </div>
    </div>
  );
}
