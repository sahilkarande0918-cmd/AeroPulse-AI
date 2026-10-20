import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test, type Page } from '@playwright/test'

const envFile = fileURLToPath(new URL('../../.env', import.meta.url))
const PASSWORD = process.env.E2E_PASSWORD
  ?? readFileSync(envFile, 'utf8').match(/^DEMO_PASSWORD=(.+)$/m)?.[1]?.trim() ?? ''
const SHOTS = process.env.E2E_SCREENSHOTS   // directory to write README screenshots into (optional)

async function login(page: Page, user: string) {
  await page.goto('/')
  await page.getByLabel('Username').fill(user)
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Command overview' })).toBeVisible()
}

async function shot(page: Page, name: string) {
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: false })
}

test('officer runs the TrustTwin demo and approves the revised plan', async ({ page }) => {
  await login(page, 'officer')
  await expect(page.getByText('Action required').first()).toBeVisible()
  await shot(page, '01-command-overview')

  await page.getByRole('link', { name: 'Aircraft fleet' }).click()
  await page.getByRole('link', { name: 'AP-101' }).click()
  await expect(page.getByRole('heading', { name: 'AP-101 · health detail' })).toBeVisible()
  await expect(page.getByRole('img', { name: 'Engine module health schematic' }).first()).toBeVisible()
  await shot(page, '02-aircraft-health')

  await page.getByRole('link', { name: 'TrustTwin' }).click()
  await page.getByRole('button', { name: /Spare part unavailable/ }).click()
  await page.getByRole('button', { name: /Sensor readings disappear/ }).click()
  await page.getByRole('button', { name: 'Run scenario' }).click()
  await expect(page.getByRole('heading', { name: 'Why the plan changed' })).toBeVisible()
  await expect(page.getByText(/TrustTwin state VALID -> DEGRADED/)).toBeVisible()
  await shot(page, '03-trusttwin-scenario')

  const review = page.locator('section', { has: page.getByRole('heading', { name: 'Officer review' }) })
  await review.getByLabel('Decision reason').last().fill('Verify sensors before committing the replacement slot')
  await review.getByRole('button', { name: 'Approve' }).last().click()
  await expect(review.getByText('Decision record')).toBeVisible()
  await expect(review.getByText(/by officer/)).toBeVisible()
})

test('analyst can run analysis but is never offered approval', async ({ page }) => {
  await login(page, 'analyst')
  await page.getByRole('link', { name: 'TrustTwin' }).click()
  await page.getByRole('button', { name: 'Run scenario' }).click()
  await expect(page.getByRole('heading', { name: 'Why the plan changed' })).toBeVisible()
  await expect(page.getByText(/Your role can view but not decide/).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Approve' })).toHaveCount(0)
})

test('planner, intelligence and reports render real data', async ({ page }) => {
  await login(page, 'officer')
  await page.getByRole('link', { name: 'Maintenance planner' }).click()
  await page.getByRole('button', { name: 'Generate plan' }).click()
  await expect(page.getByText(/cp-sat · OPTIMAL/)).toBeVisible()
  await shot(page, '04-maintenance-planner')

  await page.getByRole('link', { name: 'Predictive intelligence' }).click()
  await expect(page.getByText('15.74').first()).toBeVisible()   // official test RMSE from evaluation_report.json
  await shot(page, '05-predictive-intelligence')

  await page.getByRole('link', { name: 'Reports & audit' }).click()
  await page.getByRole('button', { name: 'Verify chain' }).click()
  await expect(page.getByText(/Chain intact/)).toBeVisible()
})

test('no horizontal overflow at phone width on any page', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await login(page, 'officer')
  await shot(page, '06-mobile-overview')
  for (const path of ['/', '/fleet', '/fleet/1', '/trusttwin', '/planner', '/parts', '/intelligence', '/reports', '/settings']) {
    await page.goto(path)
    await expect(page.locator('main h1').first()).toBeVisible()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow, `horizontal overflow on ${path}`).toBeLessThanOrEqual(0)
  }
})
