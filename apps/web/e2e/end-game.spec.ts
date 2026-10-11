import { expect, test } from '@playwright/test';
import { es } from '../src/i18n/es';
import { createRoom, driveUntil, joinRoom, newDrive, openMobile, startGame, type Mobile } from './helpers';

const NAMES = ['Anfitriones', 'Azules', 'Verdes'] as const;

test('el anfitrión termina la partida a mitad y todos ven los resultados', async ({ browser }) => {
  const mobiles = [await openMobile(browser), await openMobile(browser), await openMobile(browser)];
  const [host, p2, p3] = mobiles as [Mobile, Mobile, Mobile];
  const pages = mobiles.map((m) => m.page);
  try {
    const code = await createRoom(host.page, { mode: 'voice', teams: 3, hostName: NAMES[0] });
    await joinRoom(p2.page, code, NAMES[1]);
    await joinRoom(p3.page, code, NAMES[2]);
    await startGame(host.page, 3);

    // Solo el anfitrión ve el botón.
    const endButton = (m: Mobile) => m.page.getByRole('button', { name: es.endGame.button });
    await expect(host.page.getByTestId('turn-banner')).toBeVisible({ timeout: 15_000 });
    await expect(endButton(host)).toBeVisible();
    await expect(endButton(p2)).toHaveCount(0);
    await expect(endButton(p3)).toHaveCount(0);

    // Mitad de partida: un turno cerrado.
    const drive = newDrive();
    const mid = await driveUntil(pages, drive, () => Promise.resolve(drive.nexts >= 1), 120_000);
    expect(mid, 'la partida debe llegar a mitad (un turno cerrado)').toBe(true);

    // «Seguir jugando» cierra el modal y la partida continúa.
    await endButton(host).click();
    const dialog = host.page.getByRole('dialog', { name: es.endGame.title });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText(es.endGame.body);
    await dialog.getByRole('button', { name: es.endGame.cancel }).click();
    await expect(dialog).toHaveCount(0);
    await expect(host.page.getByRole('heading', { name: es.results.title })).toHaveCount(0);

    // «Terminar» lleva a todos a la pantalla de resultados con el aviso.
    await endButton(host).click();
    await host.page.getByRole('dialog').getByRole('button', { name: es.endGame.confirm }).click();
    for (const page of pages) {
      await expect(page.getByRole('heading', { name: es.results.title })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText(es.results.reasonHost)).toBeVisible();
      await expect(page.getByTestId('winner')).toBeVisible();
      // Ranking final: una fila por equipo, con su posición, y al menos una en el 1.º.
      const rows = page.getByTestId('rank-row');
      await expect(rows).toHaveCount(pages.length);
      await expect(rows.first()).toContainText(es.results.position(1));
      await expect(page.getByText(es.results.tokensNote)).toBeVisible();
    }

    // La revancha funciona como siempre.
    await expect(p2.page.getByText(es.results.waitRematch)).toBeVisible();
    await host.page.getByRole('button', { name: es.results.rematch }).click();
    await expect(host.page.getByRole('button', { name: es.lobby.start })).toBeVisible({ timeout: 15_000 });
  } finally {
    await Promise.all(mobiles.map((m) => m.ctx.close()));
  }
});
