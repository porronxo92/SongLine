import { Check, Share2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { es } from '../i18n/es';
import { joinUrl } from '../lib/joinUrl';
import { Button } from './ui';

/**
 * Comparte el enlace de la sala con el menú nativo del móvil (WhatsApp, Telegram…).
 * Sin `navigator.share` (algunos navegadores de escritorio) copia el texto y el enlace.
 */
export function ShareRoom({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const id = setTimeout(() => {
      setCopied(false);
    }, 2500);
    return () => {
      clearTimeout(id);
    };
  }, [copied]);

  async function share() {
    const url = joinUrl(code);
    const text = es.lobby.shareText(code);
    if (typeof navigator.share === 'function') {
      try {
        await navigator.share({ title: 'SongLine', text, url });
        return;
      } catch (err) {
        // El usuario cerró el menú: no hay nada más que hacer.
        if (err instanceof DOMException && err.name === 'AbortError') return;
      }
    }
    try {
      await navigator.clipboard.writeText(`${text} ${url}`);
      setCopied(true);
    } catch {
      // Sin portapapeles: queda el código en pantalla.
    }
  }

  return (
    <div className="mt-3 flex flex-col items-center gap-1">
      <Button variant="secondary" data-testid="share-room" onClick={() => void share()}>
        {copied ? <Check aria-hidden /> : <Share2 aria-hidden />}
        {copied ? es.lobby.shareCopied : es.lobby.share}
      </Button>
      <span className="sr-only-live" role="status">
        {copied ? es.lobby.shareCopied : ''}
      </span>
    </div>
  );
}
