import { useEffect, useRef, type ReactNode } from 'react';

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Modal accesible: rol dialog, foco atrapado, Escape opcional y foco devuelto al cerrar. */
export function Modal({
  title,
  children,
  onClose,
  labelledBy = 'modal-title',
}: {
  title: string;
  children: ReactNode;
  onClose?: () => void;
  labelledBy?: string;
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
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4 backdrop-blur-sm sm:items-center"
      style={{ paddingBottom: 'max(16px, env(safe-area-inset-bottom))' }}
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
        className="clay max-h-[90dvh] w-full max-w-md overflow-y-auto p-6"
      >
        <h2 id={labelledBy} className="mb-3 font-display text-2xl font-semibold">
          {title}
        </h2>
        {children}
      </div>
    </div>
  );
}
