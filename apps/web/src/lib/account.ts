import { create } from 'zustand';
import { ApiError } from '../api/client';

export interface AccountUser {
  id: string;
  email: string;
  display_name: string;
  plan: 'free' | 'premium';
  max_teams: number;
  max_cards: number | null;
  pack_slugs: string[];
}
const TOKEN_KEY = 'songline.account.token';
export function accountToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export async function accountRequest<T>(path: string, body?: unknown): Promise<T> {
  const token = accountToken();
  const response = await fetch(`/api/account/${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    const data = (await response.json().catch(() => ({}))) as {
      detail?: unknown;
    };
    throw new ApiError(response.status, typeof data.detail === 'string' ? data.detail : 'account_error');
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}
interface AccountState {
  user: AccountUser | null;
  ready: boolean;
  load: () => Promise<void>;
  authenticate: (register: boolean, email: string, password: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
}
export const useAccount = create<AccountState>((set) => ({
  user: null,
  ready: false,
  load: async () => {
    if (!accountToken()) {
      set({ user: null, ready: true });
      return;
    }
    try {
      set({ user: await accountRequest<AccountUser>('me'), ready: true });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) localStorage.removeItem(TOKEN_KEY);
      set({ user: null, ready: true });
      throw error;
    }
  },
  authenticate: async (register, email, password, displayName) => {
    const result = await accountRequest<{ token: string; user: AccountUser }>(
      register ? 'register' : 'login',
      {
        email,
        password,
        ...(register ? { display_name: displayName } : {}),
      },
    );
    localStorage.setItem(TOKEN_KEY, result.token);
    set({ user: result.user, ready: true });
  },
  logout: async () => {
    await accountRequest<undefined>('logout', {});
    localStorage.removeItem(TOKEN_KEY);
    set({ user: null, ready: true });
  },
}));
