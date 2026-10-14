/** Enlace que abre la pantalla de unirse con el código de sala ya puesto. */
export function joinUrl(code: string, origin: string = location.origin): string {
  return `${origin}/unirse/${encodeURIComponent(code)}`;
}
