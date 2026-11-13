import { appPath } from '../lib/routes';
import { Speaker } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { GameSettingsFields } from '../components/SettingsFields';
import { Button, Card, Screen, StepIndicator } from '../components/ui';
import { useAccount } from '../lib/account';
import { es } from '../i18n/es';
import { loadDraft, saveDraft } from '../lib/session';
import type { EditableSettings } from '../protocol/types';

export interface CreateDraft {
  settings: EditableSettings;
}

export const DEFAULT_SETTINGS: EditableSettings = {
  team_count: 2,
  mode: 'voice',
  target_cards: 5,
  objection_window_s: 15,
  audio_source: 'spotify',
  packs: ['mix'],
  hints_enabled: true,
  initial_tokens: 1,
};

/** Ajustes del borrador de «Nueva sala», compartidos por los dos pasos. Cada cambio se guarda al instante. */
export function useCreateSettings(): [EditableSettings, (patch: Partial<EditableSettings>) => void] {
  const user = useAccount((s) => s.user);
  const [settings, setSettings] = useState<EditableSettings>(() => {
    const draft = {
      ...DEFAULT_SETTINGS,
      ...loadDraft<CreateDraft>()?.settings,
    };
    const allowed = user?.pack_slugs ?? ['mix'];
    const packs = draft.packs.filter((slug) => allowed.includes(slug));
    return {
      ...draft,
      team_count: Math.min(draft.team_count, user?.max_teams ?? 2),
      target_cards: Math.min(
        draft.target_cards,
        user?.max_cards ?? (user?.plan === 'premium' ? Number.MAX_SAFE_INTEGER : 5),
      ),
      packs: packs.length ? packs : ['mix'],
    };
  });
  useEffect(() => {
    saveDraft({ settings } satisfies CreateDraft);
  }, [settings]);
  return [
    settings,
    (patch) => {
      setSettings((s) => ({ ...s, ...patch }));
    },
  ];
}

/** Paso 1 de 2: ajustes de juego. */
export default function Create() {
  const navigate = useNavigate();
  const [settings, update] = useCreateSettings();
  return (
    <Screen title={es.create.title} back={appPath()}>
      <StepIndicator current={1} total={2} />
      <Card className="flex flex-col gap-2">
        <GameSettingsFields values={settings} onChange={update} collapseExtras />
        <p className="flex items-center gap-2 text-sm text-muted-foreground" data-testid="audio-help">
          <Speaker size={16} aria-hidden className="flex-none text-accent" />
          {es.create.audioHelp}
        </p>
      </Card>
      <Button
        xl
        onClick={() => {
          navigate(appPath('crear/generos'));
        }}
      >
        {es.create.next}
      </Button>
    </Screen>
  );
}
