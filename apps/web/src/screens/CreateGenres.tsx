import { Music } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PackPicker } from '../components/PackPicker';
import { Button, Screen, StepIndicator } from '../components/ui';
import { es } from '../i18n/es';
import { useCreateSettings } from './Create';

/** Paso 2 de 2: géneros. El total y «Continuar» quedan fijos al pie. */
export default function CreateGenres() {
  const navigate = useNavigate();
  const [settings, update] = useCreateSettings();
  const [total, setTotal] = useState<number | null>(null);
  return (
    <Screen
      title={es.create.genresTitle}
      back="/crear"
      footer={
        <div className="sticky-footer">
          <p role="status" className="flex items-center gap-2 text-lg font-bold" data-testid="pack-total">
            <Music size={20} aria-hidden className="text-accent" />
            {total === null ? es.packs.loading : es.packs.total(total)}
          </p>
          <Button
            xl
            onClick={() => {
              navigate('/anfitrion/login');
            }}
          >
            {es.common.continue}
          </Button>
        </div>
      }
    >
      <StepIndicator current={2} total={2} />
      <p className="help">{es.create.genresHint}</p>
      <PackPicker
        layout="list"
        value={settings.packs}
        onChange={(packs) => {
          update({ packs });
        }}
        onTotal={setTotal}
      />
    </Screen>
  );
}
