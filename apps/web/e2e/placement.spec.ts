import { expect, test } from '@playwright/test';
import { es } from '../src/i18n/es';
import { createRoom, joinRoom, openMobile, startGame } from './helpers';

// Modo voz, 2 equipos: tras anclar, todos los móviles ven dónde se puso la carta; en la revelación
// el activo ve la pregunta de la ficha con las filas Canción y Artista.
test('el resumen de colocación aparece tras anclar y la pregunta de la ficha se entiende', async ({ browser }) => {
  const a = await openMobile(browser);
  const b = await openMobile(browser);
  try {
    const code = await createRoom(a.page, { mode: 'voice', teams: 2, hostName: 'Rojos' });
    await joinRoom(b.page, code, 'Azules');
    await startGame(a.page, 2);

    // El servidor sortea qué equipo empieza: se usa el móvil que tenga «Reproducir canción».
    const playA = a.page.getByRole('button', { name: es.game.play });
    const playB = b.page.getByRole('button', { name: es.game.play });
    await expect.poll(async () => (await playA.isVisible()) || (await playB.isVisible()), { timeout: 30_000 }).toBe(true);
    const [act, other, actName] = (await playA.isVisible()) ? [a, b, 'Rojos'] : [b, a, 'Azules'];
    await act.page.getByRole('button', { name: es.game.play }).click();
    await act.page.getByRole('button', { name: es.game.anchor }).click();

    const sentence = /puesto la carta (entre|antes de|después de|como primera)/;
    // El activo lo ve dentro del diálogo de confirmación; el otro, bajo la línea.
    const mine = act.page.getByRole('dialog').getByTestId('placement-summary');
    await expect(mine).toContainText('Habéis puesto la carta');
    await expect(mine).toContainText(sentence);
    const theirs = other.page.getByTestId('placement-summary');
    await expect(theirs).toContainText(actName);
    await expect(theirs).toContainText(sentence);

    await act.page.getByRole('button', { name: es.game.voiceConfirm }).click();

    const claim = act.page.getByTestId('honor-claim');
    await expect(claim).toBeVisible({ timeout: 30_000 });
    await expect(claim.getByRole('heading', { name: es.game.honorTitle })).toBeVisible();
    await expect(claim).toContainText(es.game.honorHelp);
    for (const group of [es.game.honorTitleOk, es.game.honorArtistOk]) {
      await expect(claim.getByRole('radiogroup', { name: group }).getByRole('radio')).toHaveCount(2);
    }
    await expect(act.page.getByTestId('placement-summary')).toBeVisible();
    // La frase suelta «Falta que digáis…» ya no se repite fuera del panel.
    await expect(act.page.getByText(es.explain.tokenPendingActive)).toHaveCount(0);
  } finally {
    await a.ctx.close();
    await b.ctx.close();
  }
});
