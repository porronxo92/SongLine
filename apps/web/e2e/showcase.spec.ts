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

test('el escaparate mantiene un único acceso a cada acción y conserva la sala guardada', async ({ page }) => {
  await page.goto('/jugar');
  await expect(page).toHaveURL('/');
  await expect(page.getByRole('button', { name: es.home.create, exact: true })).toHaveCount(1);
  await expect(page.getByRole('button', { name: es.home.join, exact: true })).toHaveCount(1);
  await expect(page.getByRole('button', { name: es.home.howTo, exact: true })).toHaveCount(1);
  await page.evaluate(() => { localStorage.setItem('hc.room_code', '4321'); });
  await page.reload();
  await expect(page).toHaveURL('/');
  await expect(page.getByRole('button', { name: es.home.resume('4321') })).toBeVisible();
  await page.getByRole('button', { name: es.home.forget, exact: true }).click();
  await expect(page.getByRole('button', { name: es.home.resume('4321') })).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem('hc.room_code'))).toBeNull();
});
