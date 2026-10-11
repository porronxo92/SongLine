import { expect, test, type Page } from '@playwright/test';
import { es } from '../src/i18n/es';
import { createRoom, isShown, joinRoom, openMobile, startGame, tokensOf, type Mobile } from './helpers';

const NAMES = ['Rojos', 'Azules'] as const;

/** Espera a que uno de los dos móviles tenga el turno, pulsa «Reproducir» y devuelve (activo, otro, slot). */
async function startTurn(host: Page, guest: Page): Promise<{ active: Page; other: Page; slot: number }> {
  const pages: [Page, Page] = [host, guest];
  let idx = -1;
  await expect
    .poll(
      async () => {
        for (const [i, p] of pages.entries()) {
          if (await isShown(p.getByRole('button', { name: es.game.play }))) idx = i;
        }
        return idx;
      },
      { timeout: 30_000 },
    )
    .toBeGreaterThanOrEqual(0);
  const active = pages[idx];
  const other = pages[1 - idx];
  if (!active || !other) throw new Error('sin equipo activo');
  await active.getByRole('button', { name: es.game.play }).click();
  await expect(active.getByRole('button', { name: es.game.anchor })).toBeVisible();
  return { active, other, slot: idx };
}

test('el equipo del turno pide una pista: ve el texto, gasta la ficha y los demás solo ven el aviso', async ({ browser }) => {
  const a = await openMobile(browser);
  const b = await openMobile(browser);
  try {
    const code = await createRoom(a.page, { mode: 'voice', teams: 2, hostName: NAMES[0] });
    await joinRoom(b.page, code, NAMES[1]);
    await startGame(a.page, 2);
    const { active, other, slot } = await startTurn(a.page, b.page);
    const activeName = NAMES[slot] ?? '';

    // Ficha inicial por defecto: 1.
    await expect.poll(() => tokensOf(active, slot)).toBe(1);
    await active.getByTestId('hint-button').click();
    const dialog = active.getByRole('dialog', { name: es.hints.chooseTitle });
    await expect(dialog).toContainText(es.hints.chooseCost(1));
    await dialog.getByTestId('hint-choose-artist').click();

    // Texto enmascarado en grande, con etiqueta accesible y cuenta atrás.
    const masked = active.getByTestId('hint-masked-artist');
    await expect(masked).toBeVisible();
    const text = ((await masked.textContent()) ?? '').trim();
    expect(text).toMatch(/_/);
    await expect(masked).toHaveAttribute('aria-label', /^Pista del artista: .*hueco/);
    const timer = active.getByTestId('hint-timer');
    await expect(timer).toBeVisible();
    const secs = Number(((await timer.textContent()) ?? '').replace(/\D/g, ''));
    expect(secs).toBeGreaterThan(40);
    expect(secs).toBeLessThanOrEqual(61);
    await expect.poll(() => tokensOf(active, slot)).toBe(0);

    // Se puede minimizar y volver a abrir.
    await active.getByTestId('hint-toggle').click();
    await expect(masked).toHaveCount(0);
    await active.getByTestId('hint-toggle').click();
    await expect(masked).toBeVisible();

    // Sin fichas el botón queda deshabilitado con el motivo.
    await expect(active.getByTestId('hint-button')).toBeDisabled();
    await expect(active.getByTestId('hint-button')).toContainText(es.hints.noTokensShort);

    // El otro equipo ve el aviso y los tipos usados, pero ningún texto enmascarado.
    await expect(other.getByRole('alert').filter({ hasText: es.hints.usedBy(activeName, 'artist') })).toBeVisible();
    await expect(other.getByTestId('hint-strip')).toBeVisible();
    await expect(other.getByTestId('hint-panel')).toHaveCount(0);
    await expect(other.locator('[data-testid^="hint-masked"]')).toHaveCount(0);
    const html = await other.content();
    expect(html.includes(text)).toBe(false);
    expect(await other.evaluate(() => document.body.innerText)).not.toContain(text);
  } finally {
    await a.ctx.close();
    await b.ctx.close();
  }
});

test('el mini reproductor del equipo del turno manda órdenes al móvil del anfitrión', async ({ browser }) => {
  const a = await openMobile(browser);
  const b = await openMobile(browser);
  try {
    const code = await createRoom(a.page, { mode: 'voice', teams: 2, hostName: NAMES[0] });
    await joinRoom(b.page, code, NAMES[1]);
    await startGame(a.page, 2);
    const { active, other } = await startTurn(a.page, b.page);

    // El servidor comprueba a los 1,5 s que suene; se espera a que pase.
    await a.page.waitForTimeout(2000);
    const log = () =>
      a.page.evaluate(() => (window.__fakeAudioLog ?? []).map((e) => `${e.action}${e.deltaMs === undefined ? '' : `:${String(e.deltaMs)}`}`));

    const player = active.getByRole('group', { name: es.player.label });
    await expect(player).toBeVisible();
    // Los demás equipos no tienen reproductor.
    await expect(other.getByTestId('mini-player')).toHaveCount(0);

    await player.getByRole('button', { name: es.player.back }).click();
    await expect.poll(log).toContain('seek:-10000');
    await expect(player.getByRole('button', { name: es.player.forward })).toBeEnabled();
    await player.getByRole('button', { name: es.player.forward }).click();
    await expect.poll(log).toContain('seek:10000');

    await expect(player.getByRole('button', { name: es.player.pause })).toBeEnabled();
    await player.getByRole('button', { name: es.player.pause }).click();
    await expect.poll(log).toContain('pause');
    // El estado vuelve en el `state`: el botón pasa a «Reanudar» y los demás ven «En pausa».
    await expect(player.getByRole('button', { name: es.player.resume })).toBeVisible();
    await expect(other.getByTestId('paused-chip')).toBeVisible();

    await player.getByRole('button', { name: es.player.resume }).click();
    await expect.poll(log).toContain('resume');
    await expect(player.getByRole('button', { name: es.player.pause })).toBeVisible();

    await expect(player.getByRole('button', { name: es.player.restart })).toBeEnabled();
    await player.getByRole('button', { name: es.player.restart }).click();
    await expect.poll(log).toContain('restart');
  } finally {
    await a.ctx.close();
    await b.ctx.close();
  }
});

test('un error del servidor se muestra en español y sin nombres internos', async ({ browser }) => {
  const a = await openMobile(browser);
  const b = await openMobile(browser);
  const mobiles: Mobile[] = [a, b];
  // Intercepta `use_hint` y responde con el texto crudo que daba el servidor antes.
  for (const m of mobiles) {
    await m.page.routeWebSocket(/\/ws\/rooms\//, (ws) => {
      const server = ws.connectToServer();
      ws.onMessage((msg) => {
        if (typeof msg === 'string') {
          const parsed = JSON.parse(msg) as { type: string; id: string };
          if (parsed.type === 'use_hint') {
            ws.send(
              JSON.stringify({
                type: 'error',
                id: 'x',
                payload: { ref_id: parsed.id, code: 'wrong_phase', message: 'No se puede hacer esto en la fase turn_ready' },
              }),
            );
            return;
          }
        }
        server.send(msg);
      });
      server.onMessage((msg) => {
        ws.send(msg);
      });
    });
  }
  try {
    const code = await createRoom(a.page, { mode: 'voice', teams: 2, hostName: NAMES[0] });
    await joinRoom(b.page, code, NAMES[1]);
    await startGame(a.page, 2);
    const { active } = await startTurn(a.page, b.page);

    await active.getByTestId('hint-button').click();
    await active.getByTestId('hint-choose-title').click();
    const toast = active.getByRole('alert').filter({ hasText: es.errors.wrong_phase ?? '' });
    await expect(toast).toBeVisible();
    await expect(toast).not.toContainText('turn_ready');
    expect(await active.evaluate(() => document.body.innerText)).not.toMatch(/turn_ready|wrong_phase/);
  } finally {
    await a.ctx.close();
    await b.ctx.close();
  }
});
