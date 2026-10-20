import type { Prediction } from './api'
import { cx } from './format'

// Station layout of a two-spool turbofan, left (inlet) to right (exhaust). Sensors are the 12 the model uses,
// placed at the module they measure (Saxena et al. 2008 station numbering).
const MODULES: { id: string; label: string; x: number; w: number; sensors: string[] }[] = [
  { id: 'fan', label: 'Fan', x: 8, w: 62, sensors: ['s15'] },
  { id: 'lpc', label: 'LPC', x: 76, w: 70, sensors: ['s2'] },
  { id: 'hpc', label: 'HPC', x: 152, w: 96, sensors: ['s3', 's7', 's9', 's11', 's14', 's17'] },
  { id: 'burner', label: 'Burner', x: 254, w: 62, sensors: ['s12'] },
  { id: 'hpt', label: 'HPT', x: 322, w: 62, sensors: ['s20'] },
  { id: 'lpt', label: 'LPT', x: 390, w: 76, sensors: ['s4', 's21'] },
]

/** Modest engine-health schematic: modules shaded by how much they drive the RUL estimate, outlined when their sensors are suspect. */
export function EngineSchematic({ p, onSelect }: { p: Prediction; onSelect?: (sensor: string) => void }) {
  const contrib: Record<string, number> = {}
  for (const e of p.evidence ?? []) {
    const s = e.feature.split('_')[0]
    contrib[s] = (contrib[s] ?? 0) + e.contribution
  }
  const suspect = new Set(Object.keys(p.imputed ?? {}))
  for (const c of p.checks ?? []) {
    if (c.status === 'pass' || c.status === 'skipped') continue
    for (const m of c.detail.matchAll(/\bs(\d{1,2})\b/g)) suspect.add(`s${m[1]}`)
  }
  const maxAbs = Math.max(1, ...Object.values(contrib).map(Math.abs))
  return (
    <figure>
      <svg viewBox="0 0 474 150" className="w-full max-w-xl" role="img" aria-label="Engine module health schematic">
        <path d="M8 34 Q240 6 466 30 L466 120 Q240 144 8 116 Z" fill="none" stroke="var(--color-line-strong)" strokeWidth="1.5" />
        <line x1="8" y1="75" x2="466" y2="75" stroke="var(--color-line)" strokeDasharray="3 4" />
        {MODULES.map((m) => {
          const c = m.sensors.reduce((a, s) => a + (contrib[s] ?? 0), 0)
          const bad = m.sensors.filter((s) => suspect.has(s))
          const fill = c < 0 ? 'var(--color-crit)' : 'var(--color-ok)'
          const opacity = 0.12 + 0.6 * Math.min(1, Math.abs(c) / maxAbs)
          return (
            <g key={m.id} className={cx(onSelect && 'cursor-pointer')} onClick={() => onSelect?.(m.sensors[0])}>
              <title>{`${m.label}: sensors ${m.sensors.join(', ')} · contribution ${c.toFixed(1)} cycles${bad.length ? ` · suspect ${bad.join(', ')}` : ''}`}</title>
              <rect x={m.x} y={42} width={m.w} height={66} rx={4} fill={fill} fillOpacity={opacity}
                stroke={bad.length ? 'var(--color-warn)' : 'var(--color-line-strong)'} strokeWidth={bad.length ? 2.5 : 1} strokeDasharray={bad.length ? '5 3' : undefined} />
              <text x={m.x + m.w / 2} y={70} textAnchor="middle" className="fill-ink text-[11px] font-medium">{m.label}</text>
              <text x={m.x + m.w / 2} y={88} textAnchor="middle" className="num fill-muted text-[10px]">{c ? `${c > 0 ? '+' : ''}${c.toFixed(1)}` : '·'}</text>
            </g>
          )
        })}
      </svg>
      <figcaption className="mt-1 text-[11px] text-muted">
        Shade = net TreeSHAP contribution of the module's sensors (red lowers RUL, green raises it). Dashed amber outline = sensor flagged by
        TrustTwin or imputed. Simplified two-spool layout for orientation only.
      </figcaption>
    </figure>
  )
}
