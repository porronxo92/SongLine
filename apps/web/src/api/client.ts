import type {
  AuthStatus,
  CatalogPack,
  CreateRoomRequest,
  CreateRoomResponse,
  RoomInfo,
  SpotifyStartRequest,
  SpotifyStartResponse,
  SpotifyToken,
  VerifyPremiumResponse,
} from '../protocol/types';
import { getStoredToken, setStoredToken } from '../lib/session';

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function raw<T>(path: string, init: RequestInit & { auth?: boolean } = {}, retried = false): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined && init.body !== null) headers.set('Content-Type', 'application/json');
  const token = getStoredToken();
  if (init.auth !== false && token) headers.set('Authorization', `Bearer ${token}`);
  const res = await fetch(path, { ...init, headers });
  if (!res.ok) {
    if (res.status === 401 && init.auth !== false && token && !retried) {
      // Token no firmado por este servidor (p. ej. reinicio con clave efímera): se pide uno nuevo y se reintenta.
      const body = (await res.clone().json().catch(() => ({}))) as { detail?: unknown };
      if (body.detail === 'invalid_session') {
        setStoredToken(null);
        await ensureSession();
        return raw<T>(path, init, true);
      }
    }
    let detail = String(res.status);
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === 'string') detail = body.detail;
    } catch {
      /* cuerpo no JSON */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function ensureSession(): Promise<string> {
  const existing = getStoredToken();
  if (existing) return existing;
  const { session_token } = await raw<{ session_token: string }>('/api/session', {
    method: 'POST',
    auth: false,
  });
  setStoredToken(session_token);
  return session_token;
}

async function authed<T>(path: string, init: RequestInit = {}): Promise<T> {
  await ensureSession();
  return raw<T>(path, init);
}

export const api = {
  authStatus: () => authed<AuthStatus>('/api/auth/status'),
  spotifyToken: () => authed<SpotifyToken>('/api/auth/spotify/token'),
  verifyPremium: (deviceId: string) =>
    authed<VerifyPremiumResponse>('/api/auth/spotify/verify-premium', {
      method: 'POST',
      body: JSON.stringify({ device_id: deviceId }),
    }),
  logout: () => authed<undefined>('/api/auth/logout', { method: 'POST' }),
  createRoom: (body: CreateRoomRequest) =>
    authed<CreateRoomResponse>('/api/rooms', { method: 'POST', body: JSON.stringify(body) }),
  /** Público: no necesita sesión. */
  packs: () => raw<CatalogPack[]>('/api/catalog/packs', { auth: false }),
  roomInfo: (code: string) => authed<RoomInfo>(`/api/rooms/${encodeURIComponent(code)}`),
  /**
   * Único punto de inicio del login de Spotify. El servidor guarda un nonce en una cookie HttpOnly
   * (por eso `credentials: 'include'`) y devuelve la URL a la que navegar con `window.location.assign`.
   */
  startSpotifyLogin: async (returnTo: string): Promise<string> => {
    const body: SpotifyStartRequest = { return_to: returnTo };
    const { url } = await authed<SpotifyStartResponse>('/api/auth/spotify/start', {
      method: 'POST',
      credentials: 'include',
      body: JSON.stringify(body),
    });
    return url;
  },
  turnAudio: async (code: string): Promise<Blob> => {
    await ensureSession();
    const res = await fetch(`/api/turn/audio?code=${encodeURIComponent(code)}`, {
      headers: { Authorization: `Bearer ${getStoredToken() ?? ''}` },
    });
    if (!res.ok) throw new ApiError(res.status, 'audio_unavailable');
    return res.blob();
  },
};
