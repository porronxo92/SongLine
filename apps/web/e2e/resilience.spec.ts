import { expect, test, type Browser, type BrowserContext } from '@playwright/test';
import { es } from '../src/i18n/es';
import {
  activeSlot,
  createRoom,
  driveUntil,
  isShown,
  joinRoom,
  newDrive,
  openMobile,
  startGame,
  type Mobile,
  type StorageState,
} from './helpers';

const NAMES = ['Anfitriones', 'Azules', 'Verdes'] as const;

/** Sala de 3 equipos en modo voz, con todos conectados y la partida empezada. */
async function threeTeamGame(browser: Browser): Promise<{ mobiles: Mobile[]; code: string }> {
  const mobiles = [await openMobile(browser), await openMobile(browser), await openMobile(browser)];
  const [h, p2, p3] = mobiles as [Mobile, Mobile, Mobile];
  const code = await createRoom(h.page, { mode: 'voice', teams: 3, hostName: NAMES[0] });
  await joinRoom(p2.page, code, NAMES[1]);
  await joinRoom(p3.page, code, NAMES[2]);
  await startGame(h.page, 3);
  return { mobiles, code };
}

test('(a) recargar el móvil de un equipo que no tiene el turno lo devuelve a su hueco con el estado correcto', async ({
  browser,
}) => {
  const { mobiles } = await threeTeamGame(browser);
  const pages = mobiles.map((m) => m.page);
  try {
    // Mitad de partida: dos turnos cerrados.
    const drive = newDrive();
    const midGame = await driveUntil(pages, drive, () => Promise.resolve(drive.nexts >= 2), 180_000);
    expect(midGame, 'la partida debe llegar a mitad (dos turnos cerrados)').toBe(true);

    const active = await activeSlot(pages[0]!);
    expect(active).not.toBeNull();
    const idx = [1, 2].find((s) => s !== active);
    if (idx === undefined) throw new Error('unreachable');
    const page = pages[idx]!;

    const bannerBefore = await page.getByTestId('turn-banner').textContent();
    await page.reload();

    // Vuelve a su hueco (vosotros) y ve el mismo turno que antes de recargar.
    await expect(page.getByTestId(`team-${String(idx)}`)).toContainText(`(${es.lobby.youAre.toLowerCase()})`);
    await expect(page.getByTestId('turn-banner')).toHaveText(bannerBefore ?? '');
    await expect.poll(() => activeSlot(page)).toBe(active);
  } finally {
    await Promise.all(mobiles.map((m) => m.ctx.close()));
  }
});

test('(b) cerrar el móvil del activo en mitad de la colocación pausa la partida y reabrirlo la reanuda', async ({
  browser,
}) => {
  const { mobiles, code } = await threeTeamGame(browser);
  const openContexts: BrowserContext[] = mobiles.map((m) => m.ctx);
  try {
    const pages = mobiles.map((m) => m.page);
    const placing = async (): Promise<boolean> => {
      for (const p of pages) {
        if (await isShown(p.getByRole('button', { name: es.game.anchor }))) return true;
      }
      return false;
    };
    const reached = await driveUntil(pages, newDrive(), placing, 120_000);
    expect(reached, 'debe llegar la fase de colocación').toBe(true);

    // Quién está colocando: el móvil que ve «Anclar aquí».
    let activeIdx = -1;
    for (const [i, p] of pages.entries()) {
      if (await isShown(p.getByRole('button', { name: es.game.anchor }))) {
        activeIdx = i;
        break;
      }
    }
    expect(activeIdx).toBeGreaterThanOrEqual(0);
    const active = mobiles[activeIdx]!;
    const otherIdx = [0, 1, 2].find((i) => i !== activeIdx)!;
    const other = pages[otherIdx]!;

    // Copia el localStorage (sesión) y cierra el móvil del activo.
    const state: StorageState = await active.ctx.storageState();
    await active.ctx.close();

    // Los demás ven la pausa.
    await expect(other.getByTestId('paused')).toBeVisible({ timeout: 15_000 });

    // Reabre un contexto nuevo con el mismo localStorage: la partida se reanuda.
    const back = await openMobile(browser, state);
    openContexts[activeIdx] = back.ctx;
    await back.page.goto(`/sala/${code}`);
    const anchor = back.page.getByRole('button', { name: es.game.anchor });
    const activate = back.page.getByRole('button', { name: es.audioGate.activate });
    // Si el activo es el anfitrión, el AudioGate pide el gesto otra vez.
    await expect(anchor.or(activate)).toBeVisible({ timeout: 20_000 });
    if (await isShown(activate)) await activate.click();
    await expect(anchor).toBeVisible({ timeout: 20_000 });
    await expect(back.page.getByTestId(`team-${String(activeIdx)}`)).toContainText(
      `(${es.lobby.youAre.toLowerCase()})`,
    );

    // La pausa desaparece en los demás móviles.
    await expect(other.getByTestId('paused')).toBeHidden({ timeout: 15_000 });
  } finally {
    await Promise.all(openContexts.map((c) => c.close()));
  }
});

test('(c) unirse con un código que no existe muestra «Esa sala no existe»', async ({ browser }) => {
  const m = await openMobile(browser);
  try {
    // Elige un código libre según el servidor (GET 404).
    let code = '';
    for (let i = 0; i < 5 && code === ''; i++) {
      const candidate = String(Math.floor(Math.random() * 10_000)).padStart(4, '0');
      const res = await m.page.request.get(`/api/rooms/${candidate}`);
      if (res.status() === 404) code = candidate;
    }
    expect(code, 'debe encontrarse un código libre').not.toBe('');

    await m.page.goto('/unirse');
    for (const d of code) {
      await m.page.getByRole('button', { name: es.join.digit(d) }).click();
    }
    await expect(m.page.getByRole('alert')).toHaveText(es.join.notFound);
    await expect(m.page).toHaveURL(/\/unirse$/);
  } finally {
    await m.ctx.close();
  }
});
