/** Public site and game share an origin today; game navigation stays in one namespace. */
export const APP_BASE_PATH = '/app';

export function appPath(suffix = ''): string {
  const path = suffix.replace(/^\/+/, '');
  return path ? `${APP_BASE_PATH}/${path}` : APP_BASE_PATH;
}

const ACCOUNT_RETURN_PATHS = new Set(
  ['', 'crear', 'crear/generos', 'anfitrion/login', 'anfitrion/audio', 'anfitrion/equipo', 'cuenta'].map(
    appPath,
  ),
);

/** Accept only known account destinations, including old links, on this application. */
export function accountReturnPath(value: unknown): string {
  if (
    typeof value !== 'string' ||
    !value.startsWith('/') ||
    value.startsWith('//') ||
    value.includes('\\') ||
    Array.from(value).some((character) => character.charCodeAt(0) < 32)
  )
    return appPath();
  const url = new URL(value, 'https://songline.invalid');
  const canonical =
    url.pathname === '/' || url.pathname === '/jugar'
      ? appPath()
      : url.pathname === APP_BASE_PATH || url.pathname.startsWith(`${APP_BASE_PATH}/`)
        ? url.pathname
        : appPath(url.pathname);
  return ACCOUNT_RETURN_PATHS.has(canonical) ? canonical + url.search + url.hash : appPath();
}
