import clsx from "clsx";
import { Ban, Check, Crown, Hourglass, Swords, X } from "lucide-react";
import { Fragment } from "react";
import { es } from "../i18n/es";
import type { ResultExplanation } from "../lib/explain";
import { colorFor, teamName } from "../lib/teams";
import type { TeamView } from "../protocol/types";
import { Pick } from "./Pick";
import { TeamShape } from "./ui";

/** Resalta los años (cuatro cifras) con la fuente display. */
export function Years({ text }: { text: string }) {
  const parts = text.split(/(\b\d{4}\b)/);
  return (
    <>
      {parts.map((p, i) =>
        /^\d{4}$/.test(p) ? (
          <b key={`${String(i)}${p}`} className="yr">
            {p}
          </b>
        ) : (
          <Fragment key={`${String(i)}${p}`}>{p}</Fragment>
        ),
      )}
    </>
  );
}

function TeamTag({ team }: { team: TeamView }) {
  const c = colorFor(team);
  return (
    <span className="ex-team" style={{ "--tc": c.hex } as React.CSSProperties}>
      <TeamShape shape={c.shape} color={c.hex} size={18} />
      <span>{teamName(team)}</span>
    </span>
  );
}

interface Props {
  explanation: ResultExplanation;
  active: TeamView;
  objector: TeamView | null;
  /** Oculta la línea «falta la respuesta»: el panel de honor ya la explica. */
  hidePending?: boolean;
}

/** Bloque «Qué ha pasado» de la revelación: titular, hueco, objeción y ficha. */
export function RevealExplain({
  explanation: ex,
  active,
  objector,
  hidePending = false,
}: Props) {
  const HeadIcon = ex.headline.kind === "discard" ? Ban : Crown;
  const obj = ex.objection;
  const TokenIcon = ex.token.tone === "pending" ? Hourglass : null;
  return (
    <section
      className="flex flex-col gap-3"
      data-testid="reveal-result"
      aria-label={es.explain.title}
    >
      <h2
        className={clsx("ex-head", `ex-${ex.headline.kind}`)}
        aria-live="polite"
        data-testid="reveal-headline"
      >
        <HeadIcon size={26} aria-hidden />
        <span>{ex.headline.text}</span>
      </h2>

      <div className="ex-card" data-testid="reveal-placement">
        <div className="ex-card-head">
          <TeamTag team={active} />
          <span className={clsx("ex-verdict", ex.placement.ok ? "ok" : "ko")}>
            {ex.placement.ok ? (
              <Check size={16} aria-hidden />
            ) : (
              <X size={16} aria-hidden />
            )}
            {ex.placement.title}
          </span>
        </div>
        {ex.placement.lines.map((l) => (
          <p key={l}>
            <Years text={l} />
          </p>
        ))}
      </div>

      {obj && objector ? (
        <div className="ex-card" data-testid="reveal-objection">
          <div className="ex-card-head">
            <span className="ex-versus">
              <TeamTag team={objector} />
              <Swords size={16} aria-hidden className="text-muted-foreground" />
              <TeamTag team={active} />
            </span>
            <span className={clsx("ex-verdict", obj.ok ? "ok" : "ko")}>
              {obj.ok ? (
                <Check size={16} aria-hidden />
              ) : (
                <X size={16} aria-hidden />
              )}
              {obj.title}
            </span>
          </div>
          {obj.lines.map((l) => (
            <p key={l}>
              <Years text={l} />
            </p>
          ))}
        </div>
      ) : null}

      {ex.hintRefunds && ex.hintRefunds.length > 0 ? (
        <section
          className="ex-card"
          aria-label={es.explain.hintRefundTitle}
          data-testid="reveal-hint-refunds"
          aria-live="polite"
        >
          <h3 className="mb-3 font-bold">{es.explain.hintRefundTitle}</h3>
          <ul className="flex flex-col gap-3">
            {ex.hintRefunds.map((hint) => (
              <li key={hint.kind} data-testid={`reveal-hint-${hint.kind}`}>
                <p className="mb-1 text-sm font-bold">
                  {es.explain.hintLabel(hint.kind)}
                </p>
                <p className={clsx("ex-token", `ex-token-${hint.tone}`)}>
                  {hint.tone === "pending" ? (
                    <Hourglass size={18} aria-hidden />
                  ) : (
                    <Pick width={16} spent={!hint.refunded} />
                  )}
                  <span>{hint.text}</span>
                </p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {hidePending && ex.token.tone === "pending" ? null : (
        <div>
          <h3 className="mb-2 text-sm font-bold">{es.explain.tokenLabel}</h3>
          <p
            className={clsx("ex-token", `ex-token-${ex.token.tone}`)}
            data-testid="reveal-token"
          >
            {TokenIcon ? (
              <TokenIcon size={18} aria-hidden />
            ) : (
              <Pick width={16} spent={ex.token.tone !== "good"} />
            )}
            <span>{ex.token.text}</span>
          </p>
        </div>
      )}
    </section>
  );
}
