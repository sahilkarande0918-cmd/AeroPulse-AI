// Render docs/overview/aeropulse-overview.html to docs/AeroPulse-AI-Overview.pdf (A4) with the local Edge browser.
//   node scripts/build_overview_pdf.mjs        (run from the repo root; needs frontend/node_modules installed)
import { createRequire } from 'node:module'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { join } from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const { chromium } = createRequire(join(root, 'frontend', 'package.json'))('@playwright/test')
const html = pathToFileURL(join(root, 'docs', 'overview', 'aeropulse-overview.html')).href
const out = join(root, 'docs', 'AeroPulse-AI-Overview.pdf')

const browser = await chromium.launch({ channel: process.env.E2E_CHANNEL ?? 'msedge' })
const page = await browser.newPage()
await page.goto(html, { waitUntil: 'networkidle' })
await page.evaluate(() => document.fonts.ready)
// Fail loudly if any page's content overflows its fixed A4 box.
const overflow = await page.$$eval('.page', (pages) => pages.map((p, i) => ({ page: i + 1, over: p.scrollHeight - p.clientHeight })).filter((x) => x.over > 1))
if (overflow.length) { console.error('Overflowing pages:', overflow); process.exitCode = 1 }
await page.pdf({ path: out, format: 'A4', printBackground: true, preferCSSPageSize: true })
await browser.close()
console.log(`wrote ${out}`)
