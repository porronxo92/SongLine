import { X } from 'lucide-react';
import { es } from '../i18n/es';
import { teamName } from '../lib/teams';
import type { EditableSettings, RoomView } from '../protocol/types';
import { act } from '../store/controller';
import { SettingsFields } from './SettingsFields';
import { Card } from './ui';

export function settingsOf(view: RoomView): EditableSettings {
  const s = view.settings;
  return {
    team_count: s.teamCount,
    mode: s.mode,
    target_cards: s.targetCards,
    objection_window_s: s.objectionWindowS,
    audio_source: s.audioSource,
    packs: s.packs,
    hints_enabled: s.hintsEnabled,
    initial_tokens: s.initialTokens,
  };
}

/** Ajustes y expulsión: solo el anfitrión, solo en el lobby. */
export function HostControls({ view }: { view: RoomView }) {
  const occupied = view.teams.filter((t) => t.claimed).reduce((m, t) => Math.max(m, t.slot + 1), 2);
  const kickable = view.teams.filter((t) => t.claimed && !t.isHost);
  return (
    <Card className="flex flex-col gap-5">
      <h2 className="h2">{es.lobby.settings}</h2>
      <SettingsFields
        values={settingsOf(view)}
        minTeams={Math.max(2, occupied)}
        onChange={(patch) => {
          void act('update_settings', patch);
        }}
      />
      {kickable.length > 0 ? (
        <ul className="flex flex-col gap-2">
          {kickable.map((t) => (
            <li key={t.slot} className="flex items-center justify-between gap-2">
              <span className="truncate font-bold">{teamName(t)}</span>
              <button
                type="button"
                className="btn btn-secondary btn-icon"
                aria-label={es.lobby.kick(teamName(t))}
                onClick={() => {
                  void act('kick', { slot: t.slot });
                }}
              >
                <X aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}
