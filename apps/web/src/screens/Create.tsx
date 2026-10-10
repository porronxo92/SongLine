import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SettingsFields } from '../components/SettingsFields';
import { Button, Card, Screen } from '../components/ui';
import { es } from '../i18n/es';
import { loadDraft, saveDraft } from '../lib/session';
import type { EditableSettings } from '../protocol/types';

export interface CreateDraft {
  settings: EditableSettings;
}

export const DEFAULT_SETTINGS: EditableSettings = {
  team_count: 2,
  mode: 'voice',
  target_cards: 10,
  objection_window_s: 15,
  audio_source: 'spotify',
};

export default function Create() {
  const navigate = useNavigate();
  const [settings, setSettings] = useState<EditableSettings>(
    () => loadDraft<CreateDraft>()?.settings ?? DEFAULT_SETTINGS,
  );
  return (
    <Screen title={es.create.title} back="/">
      <Card>
        <SettingsFields
          values={settings}
          onChange={(patch) => {
            setSettings((s) => ({ ...s, ...patch }));
          }}
        />
      </Card>
      <Button
        xl
        onClick={() => {
          saveDraft({ settings } satisfies CreateDraft);
          navigate('/anfitrion/login');
        }}
      >
        {es.common.continue}
      </Button>
    </Screen>
  );
}
