import { Loader2, WifiOff } from 'lucide-react';
import { es } from '../i18n/es';
import { useRoom } from '../store/room';

export function ConnectionBanner() {
  const status = useRoom((s) => s.status);
  if (status === 'open' || status === 'idle') return null;
  return (
    <div
      role="status"
      className="sticky top-0 z-40 flex items-center justify-center gap-2 bg-foreground px-4 py-2 text-sm font-bold text-white"
      style={{ paddingTop: 'max(8px, env(safe-area-inset-top))' }}
    >
      {status === 'connecting' ? (
        <Loader2 size={16} className="animate-spin" aria-hidden />
      ) : (
        <WifiOff size={16} aria-hidden />
      )}
      {status === 'connecting' ? es.connection.connecting : es.connection.reconnecting}
    </div>
  );
}
