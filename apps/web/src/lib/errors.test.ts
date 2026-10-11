import { describe, expect, it } from 'vitest';
import { es } from '../i18n/es';
import { errorMessage } from './errors';

// Códigos de `error` de docs/PROTOCOL.md 3.3.
const SERVER_CODES = [
  'bad_message', 'unknown_type', 'bad_payload', 'bad_token', 'internal', 'paused', 'wrong_phase',
  'not_your_turn', 'not_host', 'not_allowed', 'invalid_slot', 'invalid_name', 'slot_taken',
  'host_cannot_move', 'game_started', 'invalid_settings', 'teams_incomplete', 'teams_offline',
  'audio_not_ready', 'catalog_too_small', 'invalid_index', 'wrong_mode', 'objection_closed',
  'no_token', 'no_tokens', 'hint_already_used', 'hints_disabled', 'rate_limited', 'same_slot', 'too_early',
  'already_guessed', 'too_many_changes',
];

describe('errorMessage', () => {
  it('tiene un mensaje para cada código del protocolo', () => {
    for (const code of SERVER_CODES) {
      expect(Object.keys(es.errors), code).toContain(code);
    }
  });

  it('ningún mensaje enseña códigos ni nombres de fase', () => {
    for (const code of [...SERVER_CODES, 'closed', 'timeout', 'otro_codigo']) {
      const text = errorMessage(code);
      expect(text, code).not.toMatch(/[a-z]+_[a-z]+/);
      expect(text, code).not.toMatch(/turn_ready|placing|guessing/);
      expect(text.length).toBeGreaterThan(5);
    }
  });

  it('mensajes clave', () => {
    expect(errorMessage('wrong_phase')).toBe('Ahora no se puede hacer eso.');
    expect(errorMessage('no_tokens')).toBe('No tenéis fichas.');
    expect(errorMessage('rate_limited')).toBe('Más despacio.');
  });

  it('usa un mensaje genérico para códigos desconocidos', () => {
    expect(errorMessage('algo_raro')).toBe(es.common.unknownError);
    expect(errorMessage(undefined)).toBe(es.common.unknownError);
    expect(errorMessage('constructor')).toBe(es.common.unknownError);
  });
});
