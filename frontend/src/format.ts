// Pure formatting helpers and shared constants (kept out of component files for fast refresh).

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')

export const fmt = (v: number | null | undefined, d = 0) => (v == null || Number.isNaN(v) ? '—' : v.toFixed(d))

export function fmtTime(iso: string | null | undefined) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString(undefined, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export function ago(iso: string | null | undefined) {
  if (!iso) return '—'
  const h = (Date.now() - new Date(iso).getTime()) / 36e5
  if (h < 1) return `${Math.max(0, Math.round(h * 60))} min ago`
  if (h < 48) return `${Math.round(h)} h ago`
  return `${Math.round(h / 24)} d ago`
}

export const PRIORITY: Record<number, [string, 'crit' | 'warn' | 'tech' | undefined]> = {
  1: ['P1 critical', 'crit'], 2: ['P2 high', 'warn'], 3: ['P3 routine', 'tech'], 4: ['P4 low', undefined],
}

export const inputCls = 'w-full rounded border border-line-strong bg-canvas px-2.5 py-1.5 text-[13px] text-ink placeholder:text-muted/70 hover:border-muted/60 disabled:opacity-50 aria-[invalid=true]:border-crit'
