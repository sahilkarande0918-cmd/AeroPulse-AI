import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, CircleSlash, Loader2, MinusCircle, XCircle } from 'lucide-react'
import { ApiError, type Check, type MaintState, type TrustState } from './api'

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')

// ------------------------------------------------------------------ formatting
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

// ------------------------------------------------------------------ layout primitives
export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-[13px] text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

export function Panel({ title, meta, children, className, bodyClass }: {
  title?: ReactNode; meta?: ReactNode; children: ReactNode; className?: string; bodyClass?: string
}) {
  return (
    <section className={cx('min-w-0 rounded-md border border-line bg-surface', className)}>
      {title && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
          <h2 className="text-[13px] font-semibold text-ink">{title}</h2>
          {meta && <div className="text-xs text-muted">{meta}</div>}
        </div>
      )}
      <div className={cx('p-4', bodyClass)}>{children}</div>
    </section>
  )
}

export function Stat({ label, value, unit, tone, note }: { label: string; value: ReactNode; unit?: string; tone?: 'ok' | 'warn' | 'crit' | 'tech'; note?: ReactNode }) {
  const color = { ok: 'text-ok', warn: 'text-warn', crit: 'text-crit', tech: 'text-tech' }[tone ?? 'tech'] ?? 'text-ink'
  return (
    <div className="min-w-0 border-l-2 border-line-strong pl-3">
      <div className="text-xs text-muted">{label}</div>
      <div className={cx('num whitespace-nowrap text-2xl font-medium leading-tight', tone ? color : 'text-ink')}>
        {value}{unit && <span className="ml-1 text-xs text-muted">{unit}</span>}
      </div>
      {note && <div className="text-[11px] text-muted">{note}</div>}
    </div>
  )
}

// ------------------------------------------------------------------ badges
const TRUST: Record<TrustState, string> = {
  VALID: 'border-ok/40 bg-ok/10 text-ok',
  DEGRADED: 'border-warn/40 bg-warn/10 text-warn',
  UNAVAILABLE: 'border-crit/40 bg-crit/10 text-crit',
}
export function TrustBadge({ state }: { state: TrustState | null | undefined }) {
  if (!state) return <span className="text-xs text-muted">no prediction</span>
  return <span className={cx('num inline-flex items-center rounded border px-1.5 py-px text-[11px] font-medium tracking-wide', TRUST[state])}>{state}</span>
}

const MAINT: Record<MaintState, [string, string]> = {
  routine: ['Routine', 'text-muted border-line-strong'],
  watch: ['Watch', 'text-warn border-warn/40'],
  action_required: ['Action required', 'text-crit border-crit/40'],
  in_maintenance: ['In maintenance', 'text-tech border-tech/40'],
}
export function MaintBadge({ state }: { state: MaintState }) {
  const [label, cls] = MAINT[state] ?? [state, 'text-muted border-line']
  return <span className={cx('inline-flex whitespace-nowrap rounded border px-1.5 py-px text-[11px] font-medium', cls)}>{label}</span>
}

export function Tag({ children, tone }: { children: ReactNode; tone?: 'ok' | 'warn' | 'crit' | 'tech' }) {
  const cls = { ok: 'text-ok border-ok/40', warn: 'text-warn border-warn/40', crit: 'text-crit border-crit/40', tech: 'text-tech border-tech/40' }[tone ?? 'tech']
  return <span className={cx('inline-flex whitespace-nowrap rounded border px-1.5 py-px text-[11px]', tone ? cls : 'border-line-strong text-muted')}>{children}</span>
}

export const PRIORITY: Record<number, [string, 'crit' | 'warn' | 'tech' | undefined]> = {
  1: ['P1 critical', 'crit'], 2: ['P2 high', 'warn'], 3: ['P3 routine', 'tech'], 4: ['P4 low', undefined],
}
export const PriorityTag = ({ p }: { p: number }) => <Tag tone={PRIORITY[p]?.[1]}>{PRIORITY[p]?.[0] ?? `P${p}`}</Tag>

export function CheckIcon({ status }: { status: Check['status'] }) {
  if (status === 'pass') return <CheckCircle2 aria-label="pass" className="size-4 shrink-0 text-ok" />
  if (status === 'warn') return <AlertTriangle aria-label="warning" className="size-4 shrink-0 text-warn" />
  if (status === 'fail') return <XCircle aria-label="fail" className="size-4 shrink-0 text-crit" />
  return <MinusCircle aria-label="skipped" className="size-4 shrink-0 text-muted" />
}

export function CheckList({ checks }: { checks: Check[] }) {
  return (
    <ul className="space-y-1.5">
      {checks.map((c) => (
        <li key={c.id} className="flex gap-2 text-[13px]">
          <CheckIcon status={c.status} />
          <div className="min-w-0"><span className="text-ink">{c.label}</span> <span className="text-muted">— {c.detail}</span></div>
        </li>
      ))}
    </ul>
  )
}

// ------------------------------------------------------------------ RUL interval gauge
export function RulGauge({ rul, lo, hi, max = 160 }: { rul: number | null; lo: number | null; hi: number | null; max?: number }) {
  if (rul == null || lo == null || hi == null) {
    return <div className="flex items-center gap-2 text-[13px] text-crit"><CircleSlash className="size-4" /> No estimate — withheld by TrustTwin</div>
  }
  const pct = (v: number) => `${Math.min(100, (v / max) * 100)}%`
  const tone = lo <= 15 ? 'bg-crit' : lo <= 40 ? 'bg-warn' : 'bg-ok'
  return (
    <div>
      <div className="flex items-baseline gap-2">
        <span className="num text-2xl font-medium text-ink">{fmt(rul)}</span>
        <span className="text-xs text-muted">cycles predicted RUL</span>
      </div>
      <div className="relative mt-2 h-2 rounded-full bg-raised" role="img" aria-label={`90% interval ${fmt(lo)} to ${fmt(hi)} cycles`}>
        <div className={cx('absolute h-2 rounded-full opacity-60', tone)} style={{ left: pct(lo), width: `calc(${pct(hi)} - ${pct(lo)})` }} />
        <div className="absolute -top-1 h-4 w-0.5 bg-ink" style={{ left: pct(rul) }} />
      </div>
      <div className="num mt-1 flex justify-between text-[11px] text-muted">
        <span>90% interval [{fmt(lo)}, {fmt(hi)}]</span><span>scale 0–{max}</span>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ buttons & states
export function Button({ variant = 'secondary', busy, className, children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'; busy?: boolean
}) {
  const v = {
    primary: 'bg-tech text-on-accent hover:bg-tech/85 active:bg-tech/75 border-tech',
    secondary: 'bg-raised text-ink hover:bg-line-strong active:bg-line border-line-strong',
    danger: 'bg-transparent text-crit hover:bg-crit/10 active:bg-crit/20 border-crit/50',
    ghost: 'bg-transparent text-muted hover:text-ink hover:bg-raised border-transparent',
  }[variant]
  return (
    <button
      {...rest}
      disabled={rest.disabled || busy}
      aria-busy={busy || undefined}
      className={cx('inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded border px-3 py-1.5 text-[13px] font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-45', v, className)}
    >
      {busy && <Loader2 className="size-3.5 animate-spin" aria-hidden />}
      {children}
    </button>
  )
}

export const inputCls = 'w-full rounded border border-line-strong bg-canvas px-2.5 py-1.5 text-[13px] text-ink placeholder:text-muted/70 hover:border-muted/60 disabled:opacity-50 aria-[invalid=true]:border-crit'

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block min-w-0">
      <span className="mb-1 block text-xs text-muted">{label}</span>
      {children}
      {hint && <span className="mt-0.5 block text-[11px] text-muted">{hint}</span>}
    </label>
  )
}

export function Loading({ label = 'Loading' }: { label?: string }) {
  return <div role="status" className="flex items-center gap-2 py-6 text-[13px] text-muted"><Loader2 className="size-4 animate-spin" />{label}…</div>
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error instanceof ApiError ? error : null
  return (
    <div role="alert" className="rounded border border-crit/40 bg-crit/5 p-3 text-[13px]">
      <div className="font-medium text-crit">{e?.status === 403 ? 'Not permitted' : 'Could not load data'}</div>
      <div className="mt-0.5 text-muted">{e?.message ?? (error as Error)?.message ?? 'Unknown error'}</div>
      {onRetry && <Button className="mt-2" onClick={onRetry}>Retry</Button>}
    </div>
  )
}

export const Empty = ({ children }: { children: ReactNode }) => <div className="py-4 text-[13px] text-muted">{children}</div>

export function Table({ head, children, dense }: { head: ReactNode[]; children: ReactNode; dense?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className={cx('w-full border-collapse text-left text-[13px]', dense && 'text-xs')}>
        <thead>
          <tr className="border-b border-line text-xs text-muted">
            {head.map((h, i) => <th key={i} scope="col" className="whitespace-nowrap px-2 py-2 font-medium first:pl-0">{h}</th>)}
          </tr>
        </thead>
        <tbody className="[&>tr]:border-b [&>tr]:border-line/60 [&_td]:px-2 [&_td]:py-2 [&_td:first-child]:pl-0 [&_td]:align-top">{children}</tbody>
      </table>
    </div>
  )
}

export const SimLabel = () => (
  <span className="rounded border border-warn/40 px-1.5 py-px text-[11px] text-warn">Simulated — not demonstrated real-world improvement</span>
)
