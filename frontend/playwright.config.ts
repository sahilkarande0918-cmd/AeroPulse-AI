import { defineConfig } from '@playwright/test'

// End-to-end tests against a running stack (Docker local mode by default; the deployed URL works too):
//   E2E_BASE_URL=https://<app>.vercel.app npx playwright test
// Uses the locally installed Microsoft Edge (channel "msedge"), so no browser download is needed.
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8080',
    channel: process.env.E2E_CHANNEL ?? 'msedge',
    viewport: { width: 1440, height: 900 },
    trace: 'retain-on-failure',
  },
})
