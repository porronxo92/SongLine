import { devices, expect, type Browser, type BrowserContext, type Locator, type Page } from '@playwright/test';
import { es } from '../src/i18n/es';

/** Móvil de referencia (igual que playwright.config.ts). */
export const PIXEL = { ...devices['Pixel 7'] };

export type StorageState = Awaited<ReturnType<BrowserContext['storageState']>>;

export interface Mobile {
  ctx: BrowserContext;
  page: Page;
}

/** Abre un móvil nuevo. Con `storageState` reabre el mismo localStorage (misma sesión). */
export async function openMobile(browser: Browser, storageState?: StorageState): Promise<Mobile> {
  const ctx = await browser.newContext(storageState ? { ...PIXEL, storageState } : { ...PIXEL });
  const page = await ctx.newPage();
  return { ctx, page };
}

export function isShown(loc: Locator): Promise<boolean> {
  return loc.isVisible().catch(() => false);
}

export interface RoomOptions {
  mode: 'app' | 'voice';
  teams: number;
  /** Cartas para ganar. Por defecto, el valor de Crear (10). */
  target?: number;
  hostName?: string;
  /** Packs de géneros que se marcan además de `mix` (slugs). */
  packs?: string[];
}

/**
 * El anfitrión crea la sala desde cero (fake: se salta el login de Spotify).
 * El servidor limita las creaciones a 5 por minuto y por IP: si llega el aviso de límite, espera y reintenta.
 */
export async function createRoom(host: Page, o: RoomOptions): Promise<string> {
  await host.goto('/');
  await host.getByRole('button', { name: es.home.create }).click();
  for (let i = 2; i < o.teams; i++) {
    await host.getByRole('button', { name: `${es.create.more}: ${es.create.teams}` }).click();
  }
  if (o.target !== undefined) {
    for (let t = 10; t > o.target; t--) {
      await host.getByRole('button', { name: `${es.create.less}: ${es.create.target}` }).click();
    }
    await expect(host.getByRole('group', { name: es.create.target }).locator('output')).toHaveText(String(o.target));
  }
  // Paso 1 de 2 listo: los géneros se eligen en el paso 2.
  await host.getByRole('radio', { name: new RegExp(`^${o.mode === 'voice' ? es.create.modeVoice : es.create.modeApp}`) }).click();
  await host.getByRole('button', { name: es.create.next }).click();
  await expect(host).toHaveURL(/\/crear\/generos$/);
  for (const slug of o.packs ?? []) {
    const tile = host.locator(`[data-slug="${slug}"]`);
    await tile.click();
    await expect(tile).toHaveAttribute('aria-checked', 'true');
  }
  await host.getByRole('button', { name: es.common.continue }).click();

  // Modo fake: se salta el login y llega el AudioGate.
  const activate = host.getByRole('button', { name: es.audioGate.activate });
  await expect(activate).toBeEnabled({ timeout: 15_000 });
  await activate.click();

  await host.getByLabel(es.identity.name).fill(o.hostName ?? 'Anfitriones');
  const save = host.getByRole('button', { name: es.identity.save });
  await save.click();
  for (let attempt = 1; attempt <= 3; attempt++) {
    const created = await host
      .getByTestId('room-code')
      .waitFor({ state: 'visible', timeout: 15_000 })
      .then(() => true)
      .catch(() => false);
    if (created) break;
    if (!(await isShown(host.getByText(es.join.rate)))) {
      throw new Error('createRoom: la sala no se creó y no apareció el aviso de límite');
    }
    await host.waitForTimeout(61_000);
    await save.click();
  }
  const code = (await host.getByTestId('room-code').textContent())?.trim() ?? '';
  expect(code).toMatch(/^\d{4}$/);
  return code;
}

/** Un equipo entra con el código: Únete, teclea los cuatro dígitos, nombre y «Listo». */
export async function joinRoom(page: Page, code: string, name: string): Promise<void> {
  await page.goto('/');
  await page.getByRole('button', { name: es.home.join }).click();
  for (const d of code) {
    await page.getByRole('button', { name: es.join.digit(d) }).click();
  }
  await page.getByLabel(es.identity.name).fill(name);
  await page.getByRole('button', { name: es.identity.save }).click();
  await expect(page.getByTestId('room-code')).toHaveText(code);
}

/** Espera a que todos estén conectados y arranca la partida desde el lobby del anfitrión. */
export async function startGame(host: Page, teams: number): Promise<void> {
  await expect(host.getByText(es.lobby.audioOk)).toBeVisible({ timeout: 15_000 });
  await expect(host.getByText(es.lobby.connected, { exact: true })).toHaveCount(teams);
  await host.getByRole('button', { name: es.lobby.start }).click();
  await expect(host.getByTestId('countdown-number')).toBeVisible();
}

export interface DriveState {
  /** Contador para alternar el sentido del desplazamiento al colocar. */
  flip: number;
  /** Turnos cerrados con «Siguiente». */
  nexts: number;
}

export const newDrive = (): DriveState => ({ flip: 0, nexts: 0 });

/**
 * Una acción de juego para el móvil dado, si tiene alguna disponible:
 * reproducir, colocar (alternando hueco), confirmar (voz), reclamar por honor (voz) o siguiente.
 */
export async function playStep(page: Page, st: DriveState): Promise<void> {
  const play = page.getByRole('button', { name: es.game.play });
  if (await isShown(play)) {
    await play.click();
    return;
  }

  const anchor = page.getByRole('button', { name: es.game.anchor });
  if (await isShown(anchor)) {
    st.flip += 1;
    const move = page.getByRole('button', { name: st.flip % 2 ? es.timeline.next : es.timeline.prev });
    if (await move.isEnabled()) {
      const label = page.getByTestId('gap-label');
      const before = await label.textContent();
      await move.click();
      await expect(label).not.toHaveText(before ?? '');
    }
    await anchor.click();
    return;
  }

  const confirm = page.getByRole('button', { name: es.game.voiceConfirm });
  if (await isShown(confirm)) {
    await confirm.click();
    return;
  }

  // Modo voz tras revelar: el activo confirma canción y artista (reclamación por honor).
  for (const group of [es.game.honorTitleOk, es.game.honorArtistOk]) {
    const yes = page.getByRole('radiogroup', { name: group }).getByRole('radio', { name: es.common.yes });
    if ((await isShown(yes)) && (await yes.getAttribute('aria-checked')) !== 'true') {
      await yes.click();
    }
  }

  const next = page.getByRole('button', { name: es.game.next, exact: true });
  if ((await isShown(next)) && (await next.isEnabled())) {
    await next.click();
    st.nexts += 1;
  }
}

/**
 * Juega por turnos con todos los móviles hasta que `done` sea cierto.
 * `step` puede consumir la acción de un móvil (p. ej. objeciones) devolviendo true.
 * Devuelve false si se agota el tiempo o la partida termina antes.
 */
export async function driveUntil(
  pages: Page[],
  drive: DriveState,
  done: () => Promise<boolean>,
  timeoutMs: number,
  step?: (page: Page, index: number) => Promise<boolean>,
): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  const first = pages[0];
  if (!first) return false;
  while (Date.now() < deadline) {
    for (const [i, page] of pages.entries()) {
      if (await done()) return true;
      if (await isShown(first.getByRole('heading', { name: es.results.title }))) return false;
      if (step && (await step(page, i))) continue;
      await playStep(page, drive);
    }
    if (await done()) return true;
  }
  return false;
}

/** Ranura (0..3) del equipo con el turno, leída del TeamPanel (aria-current). */
export async function activeSlot(page: Page): Promise<number | null> {
  const cur = page.locator('[data-testid^="team-"][aria-current="true"]');
  if (!(await isShown(cur))) return null;
  const id = await cur.getAttribute('data-testid');
  return id ? Number(id.replace('team-', '')) : null;
}

/** Fichas del equipo `slot` tal como las pinta el TeamPanel (-1 si la vista no está en partida). */
export async function tokensOf(page: Page, slot: number): Promise<number> {
  const loc = page.getByTestId(`team-${String(slot)}`).locator('[aria-label$=" fichas"]');
  if (!(await isShown(loc))) return -1;
  return Number(((await loc.textContent()) ?? '').trim());
}
