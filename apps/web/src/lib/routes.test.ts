import { describe, expect, it } from 'vitest';
import { accountReturnPath, appPath } from './routes';

describe('application paths', () => {
  it('keeps the app entry and nested screens in the same namespace', () => {
    expect(appPath()).toBe('/app');
    expect(appPath('/crear')).toBe('/app/crear');
    expect(appPath('unirse/4821')).toBe('/app/unirse/4821');
  });

  it('preserves safe login destinations and callback parameters from previous URLs', () => {
    expect(accountReturnPath('/crear?modo=voz#ajustes')).toBe('/app/crear?modo=voz#ajustes');
    expect(accountReturnPath('/app/cuenta')).toBe('/app/cuenta');
    expect(accountReturnPath('/anfitrion/audio?auth=ok')).toBe('/app/anfitrion/audio?auth=ok');
    expect(accountReturnPath('/jugar')).toBe('/app');
    expect(accountReturnPath('/')).toBe('/app');
  });

  it.each([
    undefined, null, 123, 'https://example.com', '//example.com', '/\\example.com',
    '/app/unknown', '/unknown', '/app/login', '/crear\n',
  ])('rejects an untrusted account return path: %s', (value) => {
    expect(accountReturnPath(value)).toBe('/app');
  });
});
