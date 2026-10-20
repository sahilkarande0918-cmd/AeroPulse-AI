// Mandatory scenario 18: fail if any server secret (or its variable name) appears in the built frontend bundle.
// Usage: node scripts/check_bundle_secrets.mjs   (after `npm --prefix frontend run build`)
import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('..', import.meta.url))
const dist = join(root, 'frontend', 'dist')
if (!existsSync(dist)) { console.error('frontend/dist missing; build first'); process.exit(2) }

const SECRET_KEYS = ['JWT_SECRET_KEY', 'DEMO_PASSWORD', 'POSTGRES_PASSWORD', 'GEMINI_API_KEY', 'DATABASE_URL',
  'RENDER_API_KEY', 'VERCEL_TOKEN', 'UPTIMEROBOT_API_KEY', 'PROD_DEMO_PASSWORD']
const needles = [...SECRET_KEYS]
const envFile = join(root, '.env')
if (existsSync(envFile)) {
  for (const line of readFileSync(envFile, 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z_]+)\s*=\s*(.+?)\s*$/)
    if (m && SECRET_KEYS.includes(m[1]) && m[2].length >= 6) needles.push(m[2])
  }
}

const files = []
const walk = (d) => readdirSync(d).forEach((f) => { const p = join(d, f); statSync(p).isDirectory() ? walk(p) : files.push(p) })
walk(dist)
const hits = []
for (const f of files.filter((f) => /\.(js|css|html|map|json)$/.test(f))) {
  const text = readFileSync(f, 'utf8')
  for (const n of needles) if (text.includes(n)) hits.push(`${f}: contains ${SECRET_KEYS.includes(n) ? n : '<value of a secret>'}`)
}
if (hits.length) { console.error('SECRET LEAK IN BUNDLE:\n' + hits.join('\n')); process.exit(1) }
console.log(`ok: ${files.length} bundle files scanned, ${needles.length} secret names/values absent`)
