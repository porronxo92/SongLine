const TOKEN_KEY = 'hc.session_token';
const ROOM_KEY = 'hc.room_code';
const VIBRATE_KEY = 'hc.vibrate';
const DRAFT_KEY = 'hc.create_draft';

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function write(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* almacenamiento bloqueado: se sigue sin persistir */
  }
}

export const getStoredToken = (): string | null => read(TOKEN_KEY);
export const setStoredToken = (t: string | null): void => {
  write(TOKEN_KEY, t);
};
export const getStoredRoom = (): string | null => read(ROOM_KEY);
export const setStoredRoom = (c: string | null): void => {
  write(ROOM_KEY, c);
};
export const getVibrateEnabled = (): boolean => read(VIBRATE_KEY) !== 'off';
export const setVibrateEnabled = (on: boolean): void => {
  write(VIBRATE_KEY, on ? 'on' : 'off');
};

export function saveDraft(value: unknown): void {
  try {
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(value));
  } catch {
    /* ignorar */
  }
}
// eslint-disable-next-line @typescript-eslint/no-unnecessary-type-parameters
export function loadDraft<T>(): T | null {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}
