import { test, expect } from '@playwright/test';
import assert from 'node:assert/strict';

// Opt in against a disposable PostgreSQL database migrated to head.
// Existing Playwright servers can be reused; never point this test at production.
test('account registration, Free limits and login', async ({ page }) => {
  test.skip(process.env.ACCOUNT_E2E !== '1', 'Requires a disposable accounts database');
  await page.route('**/api/auth/status', (route) =>
    route.fulfill({ json: { auth_mode: 'spotify', logged_in: false, premium_verified: false } }),
  );
  const email = `smoke.${String(Date.now())}@example.com`;
  await page.goto('/');
  await page.getByRole('heading', { name: 'SongLine' }).waitFor();
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));

  await page.getByRole('button', { name: 'Crear sala', exact: true }).click();
  await page.getByRole('heading', { name: 'Iniciar sesión' }).waitFor();
  await page.getByRole('link', { name: '¿Primera partida? Crea una cuenta' }).click();
  await page.getByLabel('Tu nombre').fill('Anfitrión de prueba');
  await page.getByLabel('Correo electrónico').fill(email);
  await page.getByLabel('Contraseña', { exact: true }).fill('SongLine-test-password-123');
  await page.getByRole('button', { name: 'Crear cuenta', exact: true }).click();
  await page.getByRole('heading', { name: 'Nueva sala' }).waitFor();
  assert((await page.getByRole('group', { name: 'Cartas para ganar' }).innerText()).includes('5'));
  await page.goto('/cuenta');
  await page.getByRole('heading', { name: 'Plan Free' }).waitFor();
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));

  await page.getByRole('button', { name: 'Cerrar sesión' }).click();
  await page.getByRole('link', { name: 'Mi cuenta' }).click();
  await page.getByRole('heading', { name: 'Iniciar sesión' }).waitFor();
  await page.getByLabel('Correo electrónico').fill(email);
  await page.getByLabel('Contraseña', { exact: true }).fill('incorrect-password');
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click();
  await page.getByRole('alert').filter({ hasText: 'Correo o contraseña incorrectos.' }).waitFor();
  await page.getByLabel('Contraseña', { exact: true }).fill('SongLine-test-password-123');
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click();
  await page.getByRole('heading', { name: 'Mi cuenta' }).waitFor();
  await expect(page.getByRole('heading', { name: 'Mi cuenta' })).toBeVisible();
});
