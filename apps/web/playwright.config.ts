import { defineConfig, devices } from '@playwright/test';

const isWin = process.platform === 'win32';
const python = isWin ? '.venv\\Scripts\\python' : '.venv/bin/python';

// E2E contra el stack local: levanta el backend (AUTH_MODE=fake, catálogo CSV, sin persistencia) y Vite.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  // Cada spec abre 2-3 navegadores móviles; en paralelo agotan la memoria en Windows.
  workers: 1,
  retries: 0,
  timeout: 240_000,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    ...devices['Pixel 7'],
  },
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --port 8000`,
      cwd: '../server',
      url: 'http://127.0.0.1:8000/api/healthz',
      reuseExistingServer: true,
      timeout: 60_000,
      env: { AUTH_MODE: 'fake', CATALOG_SOURCE: 'csv', PERSISTENCE: 'none', RATE_ROOM_CREATE_PER_MIN: '100' },
    },
    {
      command: 'npm run dev -- --strictPort',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
