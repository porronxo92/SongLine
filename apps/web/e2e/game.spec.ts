import { devices, expect, test, type Page } from '@playwright/test';

// Partida corta en modo voz con 3 móviles: crear, unirse, jugar turnos hasta GAME_OVER.
test('tres móviles juegan una partida en modo voz hasta el final', async ({ browser }) => {
  const mobile = { ...devices['Pixel 7'] };
  const ctxs = await Promise.all([0, 1, 2].map(() => browser.newContext(mobile)));
  const [host, p2, p3] = (await Promise.all(ctxs.map((c) => c.newPage()))) as [Page, Page, Page];

  try {
    // ---- Anfitrión: crear sala (3 equipos, voz, 3 cartas) ----
    await host.goto('/');
    await host.getByRole('button', { name: 'Crear sala' }).click();
    await host.getByRole('button', { name: 'Más: Equipos' }).click();
    for (let i = 0; i < 7; i++) {
      await host.getByRole('button', { name: 'Menos: Cartas para ganar' }).click();
    }
    await expect(host.getByRole('group', { name: 'Cartas para ganar' }).locator('output')).toHaveText('3');
    await host.getByRole('radio', { name: /Voz alta/ }).click();
    await host.getByRole('button', { name: 'Continuar' }).click();

    // Modo fake: se salta el login y llega el AudioGate.
    const activate = host.getByRole('button', { name: 'Toca para activar el audio' });
    await expect(activate).toBeEnabled({ timeout: 15_000 });
    await activate.click();

    await host.getByLabel('Nombre del equipo').fill('Anfitriones');
    await host.getByRole('button', { name: 'Listo' }).click();
    const code = (await host.getByTestId('room-code').textContent())?.trim() ?? '';
    expect(code).toMatch(/^\d{4}$/);

    // ---- Los otros dos equipos entran con el código ----
    for (const [page, name] of [
      [p2, 'Azules'],
      [p3, 'Verdes'],
    ] as const) {
      await page.goto('/');
      await page.getByRole('button', { name: 'Únete a una sala' }).click();
      for (const d of code) {
        await page.getByRole('button', { name: `Número ${d}` }).click();
      }
      await page.getByLabel('Nombre del equipo').fill(name);
      await page.getByRole('button', { name: 'Listo' }).click();
      await expect(page.getByTestId('room-code')).toHaveText(code);
    }

    // ---- Lobby: audio listo y todos conectados, luego empezar ----
    await expect(host.getByText('Audio del anfitrión listo')).toBeVisible({ timeout: 15_000 });
    await expect(host.getByText('Conectado')).toHaveCount(3);
    await host.getByRole('button', { name: 'Empezar partida' }).click();
    await expect(host.getByTestId('countdown-number')).toBeVisible();

    // ---- Partida: cada vuelta, quien tenga un botón de acción lo pulsa ----
    const pages = [host, p2, p3];
    let flip = 0;
    const deadline = Date.now() + 200_000;
    let finished = false;
    while (Date.now() < deadline && !finished) {
      for (const page of pages) {
        const play = page.getByRole('button', { name: 'Reproducir canción' });
        const anchor = page.getByRole('button', { name: 'Anclar aquí' });
        const confirm = page.getByRole('button', { name: 'Confirmamos' });
        const next = page.getByRole('button', { name: 'Siguiente', exact: true });
        if (await play.isVisible()) {
          await play.click();
        } else if (await anchor.isVisible()) {
          // Alterna el hueco para variar aciertos.
          flip += 1;
          const move = page.getByRole('button', { name: flip % 2 ? 'Hueco siguiente' : 'Hueco anterior' });
          if (await move.isEnabled()) {
            const label = page.getByTestId('gap-label');
            const before = await label.textContent();
            await move.click();
            await expect(label).not.toHaveText(before ?? '');
          }
          await anchor.click();
        } else if (await confirm.isVisible()) {
          await confirm.click();
        } else if ((await next.isVisible()) && (await next.isEnabled())) {
          await next.click();
        }
      }
      finished = await host.getByRole('heading', { name: 'Fin de la partida' }).isVisible();
      await host.waitForTimeout(300);
    }

    expect(finished, 'la partida debe llegar a GAME_OVER').toBe(true);
    await expect(host.getByTestId('winner')).toContainText('Gana');
    await expect(host.getByRole('button', { name: 'Revancha' })).toBeVisible();
    await expect(p2.getByRole('heading', { name: 'Fin de la partida' })).toBeVisible();
  } finally {
    await Promise.all(ctxs.map((c) => c.close()));
  }
});
