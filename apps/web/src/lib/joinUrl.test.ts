import { describe, expect, it } from 'vitest';
import { joinUrl } from './joinUrl';

describe('joinUrl', () => {
  it('lleva a la pantalla de unirse con el código ya puesto', () => {
    expect(joinUrl('4821', 'https://songline.vercel.app')).toBe('https://songline.vercel.app/unirse/4821');
  });
});
