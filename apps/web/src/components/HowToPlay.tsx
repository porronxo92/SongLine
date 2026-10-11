import {
  BatteryCharging,
  CircleHelp,
  Equal,
  Flag,
  Lightbulb,
  SkipBack,
  Mic,
  Music2,
  Smartphone,
  Speaker,
  Target,
  ThumbsUp,
  Users,
  WifiOff,
  Play,
  Zap,
  type LucideIcon,
} from 'lucide-react';
import { useCallback, useState } from 'react';
import { es } from '../i18n/es';
import { Modal } from './Modal';
import { Pick } from './Pick';
import { Button } from './ui';

/** Un icono por paso, en el mismo orden que `es.howto.steps`. */
const STEP_ICONS: (LucideIcon | 'pick')[] = [Target, Play, Mic, Equal, 'pick', Lightbulb, SkipBack, Zap, ThumbsUp, WifiOff, Flag];

/** Un icono por punto de «Antes de empezar», en el mismo orden que `es.howto.before.items`. */
const BEFORE_ICONS: LucideIcon[] = [Users, Music2, Smartphone, Speaker, BatteryCharging];

/** Reglas paso a paso. Foco atrapado, se cierra con Esc y con el botón. */
export function HowToPlay({ onClose }: { onClose: () => void }) {
  return (
    <Modal title={es.howto.title} labelledBy="howto-title" onClose={onClose} wide closeOnBackdrop>
      <section className="mb-6" data-testid="howto-before" aria-labelledby="howto-before-title">
        <h3 id="howto-before-title" className="howto-sec">
          {es.howto.before.title}
        </h3>
        <ul className="flex flex-col gap-4">
          {es.howto.before.items.map((it, i) => {
            const Icon = BEFORE_ICONS[i] ?? Users;
            return (
              <li key={it.title} className="rule">
                <span className="rule-ico" aria-hidden>
                  <Icon size={22} />
                </span>
                <div>
                  <h4 className="rule-title">{it.title}</h4>
                  <p>{it.body}</p>
                </div>
              </li>
            );
          })}
        </ul>
      </section>
      <h3 className="howto-sec">{es.howto.before.rulesTitle}</h3>
      <ol className="mb-5 flex flex-col gap-4" data-testid="howto">
        {es.howto.steps.map((step, i) => {
          const Icon = STEP_ICONS[i] ?? Target;
          const items: readonly string[] | undefined = 'items' in step ? step.items : undefined;
          const example: string | undefined = 'example' in step ? step.example : undefined;
          return (
            <li key={step.title} className="rule">
              <span className="rule-ico" aria-hidden>
                {Icon === 'pick' ? <Pick width={20} /> : <Icon size={22} />}
              </span>
              <div>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
                {items ? (
                  <ol className="mt-1 list-decimal pl-5 text-[15px] leading-snug text-muted-foreground">
                    {items.map((t) => (
                      <li key={t} className="py-0.5">
                        {t}
                      </li>
                    ))}
                  </ol>
                ) : null}
                {example ? <p className="example">{example}</p> : null}
              </div>
            </li>
          );
        })}
      </ol>
      <Button variant="primary" xl onClick={onClose}>
        {es.howto.close}
      </Button>
    </Modal>
  );
}

/** Icono de interrogación para las cabeceras. Abre las reglas. */
export function HowToPlayButton() {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => {
    setOpen(false);
  }, []);
  return (
    <>
      <button
        type="button"
        className="btn btn-ghost btn-icon"
        aria-label={es.howto.iconLabel}
        data-testid="howto-icon"
        onClick={() => {
          setOpen(true);
        }}
      >
        <CircleHelp aria-hidden />
      </button>
      {open ? <HowToPlay onClose={close} /> : null}
    </>
  );
}
