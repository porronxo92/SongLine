import { expect, test } from '@playwright/test';
import { es } from '../src/i18n/es';
import { createRoom, joinRoom, openMobile } from './helpers';

test('crear sala con dos packs, el lobby los muestra y «Cómo se juega» se abre y se cierra', async ({ browser }) => {
  const host = await openMobile(browser);
  const guest = await openMobile(browser);
  const visitor = await openMobile(browser);
  try {
    // Paso 1 de 2: ajustes de juego, sin géneros.
    await host.page.goto('/crear');
    await expect(host.page.getByText(es.create.step(1, 2))).toBeVisible();
    await expect(host.page.getByTestId('pack-picker')).toHaveCount(0);
    await host.page.getByRole('button', { name: `${es.create.more}: ${es.create.teams}` }).click();
    await host.page.getByRole('radio', { name: new RegExp(`^${es.create.modeApp}`) }).click();
    await host.page.getByRole('button', { name: es.create.next }).click();

    // Paso 2 de 2: solo géneros. mix viene marcado; se añade rock-poprock.
    await expect(host.page).toHaveURL(/\/crear\/generos$/);
    await expect(host.page.getByText(es.create.step(2, 2))).toBeVisible();
    await expect(host.page.getByRole('radio', { name: new RegExp(`^${es.create.modeApp}`) })).toHaveCount(0);
    const picker = host.page.getByTestId('pack-picker');
    const mix = picker.locator('[data-slug="mix"]');
    const rock = picker.locator('[data-slug="rock-poprock"]');
    await expect(mix).toHaveAttribute('aria-checked', 'true');
    await expect(rock).toHaveAttribute('aria-checked', 'false');
    // La descripción sale completa, sin recortar.
    const desc = rock.locator('.pack-desc');
    expect(await desc.evaluate((el) => el.scrollHeight <= el.clientHeight + 1)).toBe(true);
    const totalBefore = (await host.page.getByTestId('pack-total').textContent()) ?? '';
    await rock.click();
    await expect(rock).toHaveAttribute('aria-checked', 'true');
    await expect(host.page.getByTestId('pack-total')).not.toHaveText(totalBefore);
    // Siempre queda al menos un pack: quitar mix deja rock; quitar rock después no hace nada.
    await mix.click();
    await expect(mix).toHaveAttribute('aria-checked', 'false');
    await rock.click();
    await expect(rock).toHaveAttribute('aria-checked', 'true');
    await mix.click();
    await expect(mix).toHaveAttribute('aria-checked', 'true');

    // Recargar en el paso 2 conserva la selección.
    await host.page.reload();
    await expect(host.page.getByTestId('pack-picker').locator('[data-slug="rock-poprock"]')).toHaveAttribute('aria-checked', 'true');
    await expect(host.page.getByTestId('pack-picker').locator('[data-slug="mix"]')).toHaveAttribute('aria-checked', 'true');

    // Volver al paso 1 conserva los ajustes (3 equipos, modo app).
    await host.page.getByRole('button', { name: es.common.back }).click();
    await expect(host.page).toHaveURL(/\/crear$/);
    await expect(host.page.getByRole('group', { name: es.create.teams }).locator('output')).toHaveText(es.create.teamsValue(3));
    await expect(host.page.getByRole('radio', { name: new RegExp(`^${es.create.modeApp}`) })).toHaveAttribute('aria-checked', 'true');
    // Adelante otra vez: los géneros siguen elegidos.
    await host.page.getByRole('button', { name: es.create.next }).click();
    await expect(host.page.getByTestId('pack-picker').locator('[data-slug="rock-poprock"]')).toHaveAttribute('aria-checked', 'true');

    // El botón atrás del navegador también vuelve al paso 1 con los ajustes.
    await host.page.goBack();
    await expect(host.page).toHaveURL(/\/crear$/);
    await expect(host.page.getByRole('radio', { name: new RegExp(`^${es.create.modeApp}`) })).toHaveAttribute('aria-checked', 'true');

    // Entrar directo al paso 2 sin borrador usa los valores por defecto.
    await host.page.evaluate(() => {
      sessionStorage.clear();
    });
    await host.page.goto('/crear/generos');
    await expect(host.page.getByTestId('pack-picker').locator('[data-slug="mix"]')).toHaveAttribute('aria-checked', 'true');
    await expect(host.page.getByTestId('pack-picker').locator('[data-slug="rock-poprock"]')).toHaveAttribute('aria-checked', 'false');

    // Crear la sala con ambos packs.
    const code = await createRoom(host.page, { mode: 'voice', teams: 2, packs: ['rock-poprock'] });
    await joinRoom(guest.page, code, 'Azules');

    // El anfitrión ve el selector con ambos marcados; el otro equipo los ve en solo lectura.
    const hostPicker = host.page.getByTestId('pack-picker');
    await expect(hostPicker.locator('[data-slug="mix"]')).toHaveAttribute('aria-checked', 'true');
    await expect(hostPicker.locator('[data-slug="rock-poprock"]')).toHaveAttribute('aria-checked', 'true');
    const summary = guest.page.getByTestId('pack-summary');
    await expect(summary).toContainText('Mix variado');
    await expect(summary).toContainText('Rock y pop-rock');

    // El anfitrión cambia los packs en el lobby y el otro equipo lo ve.
    await hostPicker.locator('[data-slug="mix"]').click();
    await expect(summary).not.toContainText('Mix variado');
    await expect(summary).toContainText('Rock y pop-rock');

    // «Cómo se juega» desde el lobby: se abre, enfoca dentro y se cierra con Esc.
    const icon = guest.page.getByRole('button', { name: es.howto.iconLabel });
    await icon.click();
    const dialog = guest.page.getByRole('dialog', { name: es.howto.title });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText(es.howto.before.title);
    await expect(dialog.getByTestId('howto-before')).toContainText(es.howto.before.items[1].title);
    await expect(dialog).toContainText(es.howto.steps[3].example);
    await expect(guest.page.locator(':focus')).toBeVisible();
    expect(await dialog.evaluate((el) => el.contains(document.activeElement))).toBe(true);
    await guest.page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(icon).toBeFocused();

    // Desde el inicio (un móvil sin sala guardada): botón visible, cierre con el botón de cerrar.
    await visitor.page.goto('/');
    await visitor.page.getByRole('button', { name: es.home.howTo, exact: true }).click();
    const home = visitor.page.getByRole('dialog', { name: es.howto.title });
    await expect(home).toBeVisible();
    await home.getByRole('button', { name: es.howto.close }).click();
    await expect(home).toHaveCount(0);
  } finally {
    await Promise.all([host.ctx.close(), guest.ctx.close(), visitor.ctx.close()]);
  }
});
