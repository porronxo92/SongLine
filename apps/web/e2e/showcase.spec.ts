import { expect, test } from '@playwright/test';
import { es } from '../src/i18n/es';

test('la demo revela el año, explica el error y permite otra colocación sin crear una partida', async ({ page }) => {
  const createdRooms: string[] = [];
  page.on('request', (request) => {
    if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/rooms') {
      createdRooms.push(request.url());
    }
  });
  await page.goto('/');
  const demo = page.getByTestId('timeline-demo');
  await expect(demo.getByText('1996', { exact: true })).toHaveCount(0);
  const before = demo.getByRole('button', { name: es.showcase.demoBefore });
  const between = demo.getByRole('button', { name: es.showcase.demoBetween });
  await before.focus();
  await page.keyboard.press('Enter');
  await expect(demo.getByText(es.showcase.demoIncorrect, { exact: true })).toBeVisible();
  await expect(demo.getByText(es.showcase.demoAnswer, { exact: true })).toBeVisible();
  await expect(before).toHaveAttribute('aria-pressed', 'true');
  await expect(between).toHaveAttribute('aria-disabled', 'true');
  await demo.getByRole('button', { name: es.showcase.demoRetry }).click();
  await expect(before).toBeFocused();
  await expect(demo.getByText('1996', { exact: true })).toHaveCount(0);
  await between.click();
  await expect(demo.getByText(es.showcase.demoCorrect, { exact: true })).toBeVisible();
  await expect(between).toHaveAttribute('aria-pressed', 'true');
  expect(createdRooms).toEqual([]);
});

test('la landing tiene un único acceso al juego y la aplicación conserva las salas guardadas', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: es.home.create, exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: es.home.join, exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: es.home.play, exact: true })).toHaveCount(1);
  await page.getByRole('button', { name: es.home.play, exact: true }).click();
  await expect(page).toHaveURL('/app');
  await expect(page.getByTestId('timeline-demo')).toHaveCount(0);
  await expect(page.getByRole('button', { name: es.home.create, exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: es.home.join, exact: true })).toBeVisible();
  await page.goto('/jugar');
  await expect(page).toHaveURL('/app');
  await page.evaluate(() => { localStorage.setItem('hc.room_code', '4321'); });
  await page.reload();
  await expect(page).toHaveURL('/app');
  await expect(page.getByRole('button', { name: es.home.resume('4321') })).toBeVisible();
  await page.getByRole('button', { name: es.home.forget, exact: true }).click();
  await expect(page.getByRole('button', { name: es.home.resume('4321') })).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem('hc.room_code'))).toBeNull();
});

test('los enlaces anteriores conservan el token de recuperación y las invitaciones entran en la aplicación', async ({ page }) => {
  await page.goto('/reset-password?token=test-reset-token#enlace');
  // The reset screen captures and removes the secret from the visible URL after redirecting.
  await expect(page.getByRole('heading', { name: es.account.reset, exact: true })).toBeVisible();
  await expect(page).toHaveURL('/app/reset-password');
  await expect(page.getByLabel(es.account.password, { exact: true })).toBeVisible();
  await page.goto('/unirse/0000');
  await expect(page).toHaveURL('/app/unirse/0000');
  await page.getByRole('button', { name: es.common.back, exact: true }).click();
  await expect(page).toHaveURL('/app');
});
