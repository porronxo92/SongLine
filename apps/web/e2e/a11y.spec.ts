import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { es } from '../src/i18n/es';
import { createRoom, driveUntil, isShown, joinRoom, newDrive, openMobile, startGame } from './helpers';

/** Violaciones de axe con impacto critical o serious, en forma legible: regla, impacto, selector. */
async function blockingViolations(page: Page): Promise<string[]> {
  const res = await new AxeBuilder({ page }).analyze();
  return res.violations
    .filter((v) => v.impact === 'critical' || v.impact === 'serious')
    .flatMap((v) => v.nodes.map((n) => `${v.id} [${String(v.impact)}] ${n.target.join(' ')}`));
}

test('Inicio no tiene violaciones critical ni serious', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: es.appName })).toBeVisible();
  expect(await blockingViolations(page), 'violaciones critical/serious en Inicio').toEqual([]);
});

test('Unirse no tiene violaciones critical ni serious', async ({ page }) => {
  await page.goto('/unirse');
  await expect(page.getByRole('heading', { name: es.join.title })).toBeVisible();
  expect(await blockingViolations(page), 'violaciones critical/serious en Unirse').toEqual([]);
});

// Un solo anfitrión y una sala: se comprueba el lobby y la pantalla de colocación de la misma partida.
test('Lobby y colocación no tienen violaciones critical ni serious', async ({ browser }) => {
  const host = await openMobile(browser);
  const guest = await openMobile(browser);
  const pages: Page[] = [host.page, guest.page];
  try {
    const code = await createRoom(host.page, { mode: 'app', teams: 2, hostName: 'Anfitriones' });
    await joinRoom(guest.page, code, 'Azules');
    await expect(host.page.getByTestId('room-code')).toHaveText(code);
    expect(await blockingViolations(host.page), 'violaciones critical/serious en Lobby').toEqual([]);

    await startGame(host.page, 2);
    let placing: Page | null = null;
    const reached = await driveUntil(
      pages,
      newDrive(),
      async () => {
        for (const p of pages) {
          if (await isShown(p.getByRole('button', { name: es.game.anchor }))) {
            placing = p;
            return true;
          }
        }
        return false;
      },
      120_000,
    );
    expect(reached, 'debe llegar la fase de colocación').toBe(true);
    const scanned = placing as Page | null;
    if (!scanned) throw new Error('unreachable');
    expect(await blockingViolations(scanned), 'violaciones critical/serious en Colocación').toEqual([]);
  } finally {
    await Promise.all([host.ctx.close(), guest.ctx.close()]);
  }
});
