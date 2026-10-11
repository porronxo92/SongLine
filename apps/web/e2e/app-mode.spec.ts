import { expect, test, type Page } from '@playwright/test';
import { es } from '../src/i18n/es';
import { createRoom, driveUntil, isShown, joinRoom, newDrive, openMobile, startGame } from './helpers';

// Respuesta deliberadamente falsa: así la validación no da por buena la canción
// y «Dar por bueno» tiene que aparecer en los dos móviles.
const GUESS_TITLE = 'Cancion inventada zz';
const GUESS_ARTIST = 'Artista inventado zz';

// Modo app, 2 equipos.
test('en modo app el activo envía título y artista, y ambos móviles ven la validación y «Dar por bueno»', async ({
  browser,
}) => {
  const a = await openMobile(browser);
  const b = await openMobile(browser);
  const pages: Page[] = [a.page, b.page];
  const [host, guest] = pages as [Page, Page];

  try {
    const code = await createRoom(host, { mode: 'app', teams: 2, hostName: 'Anfitriones' });
    await joinRoom(guest, code, 'Azules');
    await startGame(host, 2);

    // El activo llega a GUESSING y escribe en el modal.
    let submitted = false;
    const sent = await driveUntil(
      pages,
      newDrive(),
      async () => {
        for (const page of pages) {
          const dialog = page.getByRole('dialog', { name: es.game.guessTitle });
          if (await isShown(dialog)) {
            await expect(dialog.getByLabel(es.game.fieldTitle)).toBeVisible();
            await dialog.getByLabel(es.game.fieldTitle).fill(GUESS_TITLE);
            await dialog.getByLabel(es.game.fieldArtist).fill(GUESS_ARTIST);
            await dialog.getByRole('button', { name: es.common.send, exact: true }).click();
            submitted = true;
            return true;
          }
        }
        return false;
      },
      200_000,
    );
    expect(sent, 'el activo debe llegar al modal de respuesta').toBe(true);
    expect(submitted).toBe(true);

    // Revelación en ambos móviles: la respuesta, el resultado de la validación y «Dar por bueno».
    for (const page of pages) {
      const result = page.getByTestId('reveal-guess');
      await expect(result).toBeVisible({ timeout: 20_000 });
      await expect(result).toContainText(GUESS_TITLE);
      await expect(result).toContainText(GUESS_ARTIST);
      // Validación: título y artista no coinciden, así que salen con la cruz.
      await expect(result.locator('span', { hasText: es.game.guessTitleOk }).locator('svg.lucide-x')).toHaveCount(1);
      await expect(result.locator('span', { hasText: es.game.guessArtistOk }).locator('svg.lucide-x')).toHaveCount(1);
      await expect(page.getByRole('button', { name: es.game.acceptGuess })).toBeVisible();
    }

    // Cualquier equipo puede pulsar «Dar por bueno»: lo pulsa el que no tiene el turno.
    await guest.getByRole('button', { name: es.game.acceptGuess }).click();

    // El estado se actualiza en los dos: el botón desaparece y la validación pasa a acierto.
    for (const page of pages) {
      await expect(page.getByRole('button', { name: es.game.acceptGuess })).toBeHidden();
      const result = page.getByTestId('reveal-guess');
      await expect(result.locator('span', { hasText: es.game.guessTitleOk }).locator('svg.lucide-check')).toHaveCount(1);
      await expect(result.locator('span', { hasText: es.game.guessArtistOk }).locator('svg.lucide-check')).toHaveCount(1);
    }
  } finally {
    await Promise.all([a.ctx.close(), b.ctx.close()]);
  }
});
