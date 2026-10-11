import { afterEach, describe, expect, it, vi } from 'vitest';
import { wsBase } from './client';

describe('wsBase', () => {
  it('usa VITE_WS_URL sin la barra final cuando está definida', () => {
    expect(wsBase('wss://songline-api.onrender.com/')).toBe('wss://songline-api.onrender.com');
    expect(wsBase('  wss://api.example.com  ')).toBe('wss://api.example.com');
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });
  it('sin variable, usa el mismo host que sirve la web (ws en http, wss en https)', () => {
    vi.stubGlobal('location', { protocol: 'http:', host: '127.0.0.1:5173' });
    expect(wsBase(undefined)).toBe('ws://127.0.0.1:5173');
    expect(wsBase('')).toBe('ws://127.0.0.1:5173');
    vi.stubGlobal('location', { protocol: 'https:', host: 'songline.vercel.app' });
    expect(wsBase(undefined)).toBe('wss://songline.vercel.app');
  });
});
