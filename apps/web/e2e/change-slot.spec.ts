import { expect, test } from '@playwright/test';
import { es } from '../src/i18n/es';
import { createRoom, isShown, joinRoom, openMobile, startGame } from './helpers';

// Modo voz, 2 equipos: tras anclar se puede cambiar el hueco, elegir otro y anclar de nuevo.
test('«Cambiar hueco» devuelve al carrusel en el mismo hueco y deja anclar otro', async ({ browser }) => {
  const a = await openMobile(browser);
  const b = await openMobile(browser);
  try {
    const code = await createRoom(a.page, { mode: 'voice', teams: 2, hostName: 'Rojos' });
    await joinRoom(b.page, code, 'Azules');
    await startGame(a.page, 2);

    let active = a.page;
    let other = b.page;
    await expect
      .poll(async () => {
        if (await isShown(a.page.getByRole('button', { name: es.game.play }))) return 'a';
        if (await isShown(b.page.getByRole('button', { name: es.game.play }))) return 'b';
        return '';
      }, { timeout: 30_000 })
      .not.toBe('');
    if (await isShown(b.page.getByRole('button', { name: es.game.play }))) {
      active = b.page;
      other = a.page;
    }
    await active.getByRole('button', { name: es.game.play }).click();

    const label = active.getByTestId('gap-label');
    const firstGap = ((await label.textContent()) ?? '').trim();
    await active.getByRole('button', { name: es.game.anchor }).click();

    const dialog = active.getByRole('dialog');
    const summary = dialog.getByTestId('placement-summary');
    const firstSentence = ((await summary.textContent()) ?? '').trim();
    await expect(dialog.getByRole('button', { name: es.game.voiceConfirm })).toBeVisible();

    // Cambiar hueco: vuelve al carrusel, en el mismo hueco.
    await dialog.getByTestId('change-slot').click();
    await expect(active.getByRole('button', { name: es.game.anchor })).toBeVisible();
    await expect(active.getByRole('dialog')).toHaveCount(0);
    await expect(label).toHaveText(firstGap);

    // Elige el otro hueco y ancla de nuevo.
    const next = active.getByRole('button', { name: es.timeline.next });
    const prev = active.getByRole('button', { name: es.timeline.prev });
    await ((await next.isEnabled()) ? next : prev).click();
    await expect(label).not.toHaveText(firstGap);
    await active.getByRole('button', { name: es.game.anchor }).click();
    await expect(summary).toBeVisible();
    expect(((await summary.textContent()) ?? '').trim()).not.toBe(firstSentence);
    // El otro equipo ve el hueco nuevo.
    await expect(other.getByTestId('placement-summary')).toContainText('puesto la carta');

    // Sigue pudiendo confirmar.
    await expect(dialog.getByRole('button', { name: es.game.voiceConfirm })).toBeVisible();
  } finally {
    await a.ctx.close();
    await b.ctx.close();
  }
});

test('«Cómo se juega» se cierra tocando fuera, pero no al arrastrar desde dentro', async ({ browser }) => {
  const a = await openMobile(browser);
  try {
    const page = a.page;
    await page.goto('/');
    const opener = page.getByRole('button', { name: es.home.howTo });
    await opener.click();
    const dialog = page.getByRole('dialog', { name: es.howto.title });
    await expect(dialog).toBeVisible();

    // El gesto empieza dentro del panel y acaba fuera: no cierra.
    const box = await dialog.boundingBox();
    if (!box) throw new Error('sin caja');
    await page.mouse.move(box.x + box.width / 2, box.y + 40);
    await page.mouse.down();
    await page.mouse.move(2, 2);
    await page.mouse.up();
    await expect(dialog).toBeVisible();

    // Tocar el fondo cierra y devuelve el foco al botón.
    await page.mouse.click(2, 2);
    await expect(dialog).toHaveCount(0);
    await expect(opener).toBeFocused();
  } finally {
    await a.ctx.close();
  }
});
