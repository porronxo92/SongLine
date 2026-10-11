import { es } from '../i18n/es';

/** Texto en español para un código de `error` del servidor. Nunca devuelve el código ni nombres internos. */
export function errorMessage(code: string | null | undefined): string {
  if (code && Object.prototype.hasOwnProperty.call(es.errors, code)) {
    return es.errors[code] ?? es.common.unknownError;
  }
  return es.common.unknownError;
}
