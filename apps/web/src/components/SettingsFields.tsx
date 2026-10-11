import { ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';
import type { EditableSettings } from '../protocol/types';
import { es } from '../i18n/es';
import { PackPicker } from './PackPicker';
import { Stepper, Switch } from './ui';

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
              className="choice"
            >
              <span>{o.label}</span>
              <small>{o.hint}</small>
            </button>
          );
        })}
      </div>
    </div>
  );
}

interface FieldsProps {
  values: EditableSettings;
  onChange: (patch: Partial<EditableSettings>) => void;
  minTeams?: number;
  /** Esconde los ajustes menos usados tras «Más ajustes» (paso 1 de Nueva sala). */
  collapseExtras?: boolean;
}

/** Ajustes de juego sin géneros: paso 1 de Crear y base de los ajustes del lobby. */
export function GameSettingsFields({ values, onChange, minTeams = 2, collapseExtras }: FieldsProps) {
  const [moreOpen, setMoreOpen] = useState(false);
  const extras = (
    <>
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
      <Switch
        label={es.create.hints}
        help={es.create.hintsHelp}
        checked={values.hints_enabled}
        onChange={(v) => {
          onChange({ hints_enabled: v });
        }}
      />
      <Stepper
        label={es.create.initialTokens}
        value={values.initial_tokens}
        min={0}
        max={3}
        format={es.create.tokensValue}
        onChange={(n) => {
          onChange({ initial_tokens: n });
        }}
      />
    </>
  );
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
      {collapseExtras ? (
        <div className="flex flex-col gap-5">
          <button
            type="button"
            className="btn btn-ghost !justify-between"
            aria-expanded={moreOpen}
            aria-controls="more-settings"
            data-testid="more-settings"
            onClick={() => {
              setMoreOpen((o) => !o);
            }}
          >
            {es.create.moreSettings}
            {moreOpen ? <ChevronUp aria-hidden /> : <ChevronDown aria-hidden />}
          </button>
          {moreOpen ? (
            <div id="more-settings" className="flex flex-col gap-5">
              {extras}
            </div>
          ) : null}
        </div>
      ) : (
        extras
      )}
    </div>
  );
}

/** Todos los ajustes editables juntos. Los usa el lobby del anfitrión. */
export function SettingsFields(props: FieldsProps) {
  return (
    <div className="flex flex-col gap-5">
      <GameSettingsFields {...props} />
      <PackPicker
        value={props.values.packs}
        onChange={(packs) => {
          props.onChange({ packs });
        }}
      />
    </div>
  );
}
