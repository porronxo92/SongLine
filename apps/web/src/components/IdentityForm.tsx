import { useState } from 'react';
import { es } from '../i18n/es';
import { TEAM_COLORS } from '../lib/teams';
import { Button, TeamShape } from './ui';

/** Nombre y color del equipo. Cada color lleva su forma (● ▲ ■ ◆) y su nombre. */
export function IdentityForm({
  takenColors = [],
  initialName = '',
  initialColor,
  submitLabel = es.identity.save,
  busy,
  onSubmit,
}: {
  takenColors?: string[];
  initialName?: string;
  initialColor?: string;
  submitLabel?: string;
  busy?: boolean;
  onSubmit: (name: string, color: string) => void;
}) {
  const taken = takenColors.map((c) => c.toLowerCase());
  const firstFree = TEAM_COLORS.find((c) => !taken.includes(c.hex.toLowerCase()));
  const [name, setName] = useState(initialName);
  const [color, setColor] = useState(initialColor ?? firstFree?.hex ?? TEAM_COLORS[0]?.hex ?? '#FF6B4A');
  const valid = name.trim().length > 0;

  return (
    <form
      className="flex flex-col gap-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) onSubmit(name.trim(), color);
      }}
    >
      <label className="flex flex-col gap-1 font-bold">
        {es.identity.name}
        <input
          className="input"
          value={name}
          maxLength={20}
          autoComplete="off"
          autoCapitalize="words"
          placeholder={es.identity.namePlaceholder}
          name="team-name"
          onChange={(e) => {
            setName(e.target.value);
          }}
        />
      </label>
      <div role="radiogroup" aria-label={es.identity.color} className="flex flex-col gap-2">
        <span className="font-bold">{es.identity.color}</span>
        <div className="grid grid-cols-2 gap-3">
          {TEAM_COLORS.map((c) => {
            const isTaken = taken.includes(c.hex.toLowerCase());
            const on = color.toLowerCase() === c.hex.toLowerCase();
            return (
              <button
                key={c.hex}
                type="button"
                role="radio"
                aria-checked={on}
                disabled={isTaken}
                onClick={() => {
                  setColor(c.hex);
                }}
                className="choice !min-h-[64px] !flex-row !items-center !justify-start !gap-3"
              >
                <TeamShape shape={c.shape} color={c.hex} size={28} />
                <span>{c.name}</span>
                {isTaken ? <small>{es.identity.taken}</small> : null}
              </button>
            );
          })}
        </div>
      </div>
      <Button type="submit" busy={busy} disabled={!valid}>
        {submitLabel}
      </Button>
    </form>
  );
}
