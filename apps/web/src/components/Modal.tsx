import { useEffect, useRef, type ReactNode } from 'react';

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Modal accesible: rol dialog, foco atrapado, Escape opcional y foco devuelto al cerrar. */
export function Modal({
  title,
  children,
  onClose,
  labelledBy = 'modal-title',
  icon,
  wide,
}: {
  title: string;
  children: ReactNode;
  onClose?: () => void;
  labelledBy?: string;
  /** Icono lucide opcional sobre el título. */
  icon?: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const node = ref.current;
    const items = () => Array.from(node?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
    (items()[0] ?? node)?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && onClose) {
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      const list = items();
      const first = list[0];
      const last = list[list.length - 1];
      if (!first || !last) {
        e.preventDefault();
        return;
      }
      const active = document.activeElement;
      if (e.shiftKey && (active === first || !node?.contains(active))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (active === last || !node?.contains(active))) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      previous?.focus();
    };
  }, [onClose]);

  return (
    <div className="scrim" style={{ paddingBottom: 'max(16px, env(safe-area-inset-bottom))' }}>
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
        className={wide ? 'modal wide' : 'modal'}
      >
        {icon ? <div className="mb-3">{icon}</div> : null}
        <h2 id={labelledBy} className="mb-3 text-[22px] font-bold leading-tight">
          {title}
        </h2>
        {children}
      </div>
    </div>
  );
}
