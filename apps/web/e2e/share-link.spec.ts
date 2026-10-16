import { expect, test } from '@playwright/test';
import { es } from '../src/i18n/es';
import { createRoom, openMobile } from './helpers';

// El enlace de «Compartir sala» (/unirse/<código>) entra en la sala sin teclear el código.
test('el enlace compartido entra directamente en la sala', async ({ browser }) => {
  const a = await openMobile(browser);
  const b = await openMobile(browser);
  try {
    const code = await createRoom(a.page, { mode: 'voice', teams: 2, hostName: 'Rojos' });
    await b.page.goto(`/unirse/${code}`);
    await expect(b.page).toHaveURL(new RegExp(`/sala/${code}$`), { timeout: 15_000 });
    await b.page.getByLabel(es.identity.name).fill('Azules');
    await b.page.getByRole('button', { name: es.identity.save }).click();
    await expect(b.page.getByTestId('room-code')).toHaveText(code);
  } finally {
    await a.ctx.close();
    await b.ctx.close();
  }
});

test('con un enlace a una sala que no existe avisa y deja reintentar', async ({ page }) => {
  await page.goto('/unirse/0000');
  await expect(page.getByRole('alert')).toHaveText(es.join.notFound);
  await expect(page.getByTestId('join-enter')).toBeVisible();
});
