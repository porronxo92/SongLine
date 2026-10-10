import type { EditableSettings } from '../protocol/types';
import { es } from '../i18n/es';
import { Stepper } from './ui';

interface Option<T extends string> {
  value: T;
  label: string;
  hint: string;
}

export function Segmented<T extends string>({
  legend,
  value,
  options,
  onChange,
}: {
  legend: string;
  value: T;
  options: Option<T>[];
  onChange: (v: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={legend} className="flex flex-col gap-2">
      <span className="font-bold">{legend}</span>
      <div className="grid grid-cols-2 gap-2">
        {options.map((o) => {
          const on = o.value === value;
          return (
            <button
              key={o.value}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => {
                onChange(o.value);
              }}
              className="btn !flex-col !items-start !gap-0.5 !px-3 text-left"
              style={{
                background: on ? 'var(--color-secondary)' : '#fff',
                color: on ? '#000' : 'var(--color-foreground)',
                borderColor: on ? '#6d3fd6' : 'var(--color-border)',
                minHeight: 72,
              }}
            >
              <span>{o.label}</span>
              <span className="text-xs font-semibold leading-tight">{o.hint}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Ajustes editables de la sala. Los usa la pantalla Crear y los controles del anfitrión en el lobby. */
export function SettingsFields({
  values,
  onChange,
  minTeams = 2,
}: {
  values: EditableSettings;
  onChange: (patch: Partial<EditableSettings>) => void;
  minTeams?: number;
}) {
  return (
    <div className="flex flex-col gap-5">
      <Stepper
        label={es.create.teams}
        value={values.team_count}
        min={minTeams}
        max={4}
        format={es.create.teamsValue}
        onChange={(n) => {
          onChange({ team_count: n });
        }}
      />
      <Segmented
        legend={es.create.mode}
        value={values.mode}
        options={[
          { value: 'app', label: es.create.modeApp, hint: es.create.modeAppHint },
          { value: 'voice', label: es.create.modeVoice, hint: es.create.modeVoiceHint },
        ]}
        onChange={(mode) => {
          onChange({ mode });
        }}
      />
      <Stepper
        label={es.create.target}
        value={values.target_cards}
        min={3}
        max={30}
        onChange={(n) => {
          onChange({ target_cards: n });
        }}
      />
      <Stepper
        label={es.create.objection}
        value={values.objection_window_s}
        min={5}
        max={60}
        step={5}
        format={es.common.seconds}
        onChange={(n) => {
          onChange({ objection_window_s: n });
        }}
      />
      <Segmented
        legend={es.create.audio}
        value={values.audio_source}
        options={[
          { value: 'spotify', label: es.create.audioSpotify, hint: es.create.audioSpotifyHint },
          { value: 'preview', label: es.create.audioPreview, hint: es.create.audioPreviewHint },
        ]}
        onChange={(audio_source) => {
          onChange({ audio_source });
        }}
      />
    </div>
  );
}
