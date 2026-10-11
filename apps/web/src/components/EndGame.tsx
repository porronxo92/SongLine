import { Flag } from 'lucide-react';
import { useState } from 'react';
import { es } from '../i18n/es';
import type { RoomView } from '../protocol/types';
import { act } from '../store/controller';
import { Modal } from './Modal';
import { Button } from './ui';

/** Botón discreto «Terminar partida» con confirmación. Solo se pinta en el móvil del anfitrión. */
export function EndGameButton({ view }: { view: RoomView }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!view.you.isHost) return null;
  return (
    <>
      <button
        type="button"
        className="btn btn-ghost self-center !px-4 text-sm"
        data-testid="end-game"
        onClick={() => {
          setOpen(true);
        }}
      >
        <Flag size={18} aria-hidden />
        {es.endGame.button}
      </button>
      {open ? (
        <Modal
          icon={<Flag size={40} className="text-magenta" aria-hidden />}
          title={es.endGame.title}
          labelledBy="end-game-title"
          onClose={() => {
            setOpen(false);
          }}
        >
          <p className="mb-5 text-fg-2">{es.endGame.body}</p>
          <div className="flex flex-col gap-3">
            <Button
              variant="danger"
              busy={busy}
              onClick={() => {
                setBusy(true);
                void act('end_game', {}).then((ok) => {
                  setBusy(false);
                  if (ok) setOpen(false);
                });
              }}
            >
              {es.endGame.confirm}
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setOpen(false);
              }}
            >
              {es.endGame.cancel}
            </Button>
          </div>
        </Modal>
      ) : null}
    </>
  );
}
