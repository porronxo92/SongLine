import { defineConfig, devices } from '@playwright/test';

const isWin = process.platform === 'win32';
const python = isWin ? '.venv\\Scripts\\python' : '.venv/bin/python';

const apiPort = process.env.E2E_API_PORT ?? '8000';
const webPort = process.env.E2E_WEB_PORT ?? '5173';
// Solo con los puertos por defecto se reutilizan servidores ya levantados.
const reuse = apiPort === '8000' && webPort === '5173';

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
    baseURL: process.env.E2E_BASE_URL ?? `http://127.0.0.1:${webPort}`,
    trace: 'retain-on-failure',
    ...devices['Pixel 7'],
  },
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --port ${apiPort}`,
      cwd: '../server',
      url: `http://127.0.0.1:${apiPort}/api/healthz`,
      reuseExistingServer: reuse,
      timeout: 60_000,
      env: { AUTH_MODE: 'fake', CATALOG_SOURCE: 'csv', PERSISTENCE: 'none', RATE_ROOM_CREATE_PER_MIN: '100' },
    },
    {
      command: 'npm run dev -- --strictPort',
      url: `http://127.0.0.1:${webPort}`,
      reuseExistingServer: reuse,
      timeout: 60_000,
      env: { VITE_API_PORT: apiPort, VITE_PORT: webPort },
    },
  ],
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
