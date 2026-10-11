import { Loader2, WifiOff } from 'lucide-react';
import { es } from '../i18n/es';
import { useRoom } from '../store/room';

export function ConnectionBanner() {
  const status = useRoom((s) => s.status);
  if (status === 'open' || status === 'idle') return null;
  return (
    <div role="status" className="conn-banner" style={{ paddingTop: 'max(8px, env(safe-area-inset-top))' }}>
      {status === 'connecting' ? (
        <Loader2 size={16} className="animate-spin text-accent" aria-hidden />
      ) : (
        <WifiOff size={16} className="pause-icon text-magenta-light" aria-hidden />
      )}
      {status === 'connecting' ? es.connection.connecting : es.connection.reconnecting}
    </div>
  );
}
