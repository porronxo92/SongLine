import { expect, test } from '@playwright/test';

test('la pantalla de inicio carga', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle('HitsterCasero');
  await expect(page.getByRole('heading', { name: 'HitsterCasero' })).toBeVisible();
});
