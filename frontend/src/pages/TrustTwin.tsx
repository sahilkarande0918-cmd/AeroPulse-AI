import { useMemo, useState, type ReactNode } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowRight, ChevronDown, Play, RotateCcw } from 'lucide-react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, type AircraftRow, type Check, type Decision, type Evidence, type Page, type Part, type PlanResult, type Technician, type TrustState } from '../api'
import { useAuth } from '../auth'
import { DecisionForm } from '../decide'
import { Gantt } from '../gantt'
import {
  Button, CheckList, Empty, ErrorState, Field, Loading, PageHeader, Panel, PriorityTag, RulGauge, SimLabel, Table, Tag, TrustBadge, cx, fmt, inputCls,
} from '../ui'

// ---------------------------------------------------------------- types
interface Assessment {
  state: TrustState; summary: string; reasons: string[]; checks: Check[]; rul: number | null; rul_lower: number | null
  rul_upper: number | null; evidence: Evidence[]; imputed: Record<string, number>; cycle: number; n_cycles: number; model_version: string
}
interface Rec { action: string; task_type: string; skill: string; duration: number; priority: number; rationale: string; due_days: number }
interface Risk { task: string; engine_id: number; rul_lower: number; starts_in_h: number | null; cycles_flown_before_start: number | null; margin_cycles: number | null; flag: string }
interface Side { assessment: Assessment; recommendation: Rec | null; plan: PlanResult; outcomes: { engine_risk: Risk[]; aircraft_maintenance_hours: Record<string, number>; note: string } }
interface Run {
  id: number; created_at: string; seed: number; params: Params; result_hash: string
  result: { engine: { id: number; serial: string; aircraft: string; source: string }; baseline: Side
    revised: Side & { rule_based_plan_kpis: PlanResult['kpis']; rule_based_objective: number }
    diff: { task: string; change: string; from?: number; to?: number; tech_from?: string; tech_to?: string; reason?: string }[]
    explanation: string[]; horizon_start: string; sandbox_note: string }
  review: { recommendation: { id: number; status: string; action: string } | null; schedules: { id: number; solver: string; status: string }[]; decisions: Decision[] }
}
interface Params {
  engine_id: number; seed: number; advance_cycles: number; dropout_sensors: string[]; dropout_last_n: number; bias_sensor: string | null
  bias_sigma: number; noise_sigma: number; stale_hours: number; unavailable_parts: string[]; part_delay_days: number
  unavailable_technicians: string[]; extra_inspection_aircraft: number[]
}

const blank = (engine_id: number): Params => ({
  engine_id, seed: 7, advance_cycles: 0, dropout_sensors: [], dropout_last_n: 1, bias_sensor: null, bias_sigma: 0, noise_sigma: 0,
  stale_hours: 0, unavailable_parts: [], part_delay_days: 0, unavailable_technicians: [], extra_inspection_aircraft: [],
})

type Preset = { key: string; label: string; hint: string; apply: (p: Params, fleet: AircraftRow[]) => Params; active: (p: Params) => boolean }
const PRESETS: Preset[] = [
  { key: 'fault', label: 'Developing engine fault', hint: 'replay 30 further recorded cycles',
    apply: (p) => ({ ...p, advance_cycles: p.advance_cycles ? 0 : 30 }), active: (p) => p.advance_cycles > 0 },
  { key: 'part', label: 'Spare part unavailable', hint: 'hot-section kit stock 0, resupply slips 10 days',
    apply: (p) => p.unavailable_parts.includes('APX-HPT-MOD-KIT') ? { ...p, unavailable_parts: [], part_delay_days: 0 } : { ...p, unavailable_parts: ['APX-HPT-MOD-KIT'], part_delay_days: 10 },
    active: (p) => p.unavailable_parts.length > 0 },
  { key: 'tech', label: 'Technician unavailable', hint: 'TECH-01 (powerplant + NDT) off',
    apply: (p) => ({ ...p, unavailable_technicians: p.unavailable_technicians.length ? [] : ['TECH-01'] }), active: (p) => p.unavailable_technicians.length > 0 },
  { key: 'dropout', label: 'Sensor readings disappear', hint: 's4 (T50) and s11 (Ps30) missing in last 2 readings',
    apply: (p) => p.dropout_sensors.length ? { ...p, dropout_sensors: [], dropout_last_n: 1 } : { ...p, dropout_sensors: ['s4', 's11'], dropout_last_n: 2 },
    active: (p) => p.dropout_sensors.length > 0 },
  { key: 'multi', label: 'Simultaneous inspections', hint: '3 more aircraft need inspection now',
    apply: (p, fleet) => ({ ...p, extra_inspection_aircraft: p.extra_inspection_aircraft.length ? [] : fleet.filter((a) => !a.engines.some((e) => e.id === p.engine_id)).slice(0, 3).map((a) => a.id) }),
    active: (p) => p.extra_inspection_aircraft.length > 0 },
]

const toggle = <T,>(arr: T[], v: T) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v])

export default function TrustTwin() {
  const { can } = useAuth()
  const fleet = useQuery({ queryKey: ['aircraft', '', '', ''], queryFn: () => api.get<Page<AircraftRow>>('/aircraft?search=') })
  const parts = useQuery({ queryKey: ['parts'], queryFn: () => api.get<{ items: Part[] }>('/parts') })
  const techs = useQuery({ queryKey: ['technicians'], queryFn: () => api.get<{ items: Technician[] }>('/technicians') })
  const model = useQuery({ queryKey: ['model'], queryFn: () => api.get<{ feature_schema: { sensors: Record<string, unknown> } }>('/model') })
  const sensors = Object.keys(model.data?.feature_schema.sensors ?? {})
  const history = useQuery({ queryKey: ['scenarios'], queryFn: () => api.get<Page<{ id: number; created_at: string; engine: { serial: string }; baseline_state: TrustState; revised_state: TrustState; result_hash: string }>>('/trusttwin/scenarios?limit=8') })
  const [params, setParams] = useState<Params | null>(null)
  const [runId, setRunId] = useState<number | null>(null)
  const engines = fleet.data?.items.flatMap((a) => a.engines.map((e) => ({ ...e, tail: a.tail }))) ?? []
  const p = params ?? (engines.length ? blank(engines.find((e) => e.serial === 'AP-ENG-01')?.id ?? engines[0].id) : null)

  const run = useMutation({
    mutationFn: (body: Params) => api.post<Run>('/trusttwin/scenarios', body),
    onSuccess: (r) => { setRunId(r.id); history.refetch() },
  })
  const loaded = useQuery({ queryKey: ['scenario', runId], enabled: runId != null, queryFn: () => api.get<Run>(`/trusttwin/scenarios/${runId}`) })
  const result = loaded.data

  if (fleet.isPending) return <Loading />
  if (fleet.isError) return <ErrorState error={fleet.error} onRetry={() => fleet.refetch()} />
  if (!p) return <Empty>No engines in the fleet.</Empty>
  const set = (patch: Partial<Params>) => setParams({ ...p, ...patch })

  return (
    <>
      <PageHeader title="AeroPulse TrustTwin"
        subtitle="Can we trust this prediction, and what is the safest feasible maintenance response given the available resources? Every run re-assesses real data with the trained model, re-plans with CP-SAT, and is sandboxed: live work orders, stock and rosters are never changed." />

      <div className="grid gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">
        {/* ------------------------------------------------ scenario builder */}
        <div className="space-y-4">
          <Panel title="Scenario">
            <div className="space-y-4">
              <Field label="Aircraft · engine">
                <select className={inputCls} value={p.engine_id} onChange={(e) => set({ engine_id: +e.target.value, extra_inspection_aircraft: [] })}>
                  {engines.map((e) => <option key={e.id} value={e.id}>{e.tail} · {e.serial} · {e.prediction?.state ?? '—'}{e.prediction?.rul != null ? ` · RUL ${fmt(e.prediction.rul)}` : ''}</option>)}
                </select>
              </Field>
              <fieldset>
                <legend className="mb-1.5 text-xs text-muted">Disruptions (combine freely)</legend>
                <div className="space-y-1.5">
                  {PRESETS.map((pr) => (
                    <button key={pr.key} type="button" aria-pressed={pr.active(p)} onClick={() => setParams(pr.apply(p, fleet.data.items))}
                      className={cx('block w-full rounded border px-3 py-2 text-left transition-colors duration-150',
                        pr.active(p) ? 'border-tech bg-tech/10' : 'border-line-strong hover:bg-raised')}>
                      <span className="block text-[13px] text-ink">{pr.label}</span>
                      <span className="block text-[11px] text-muted">{pr.hint}</span>
                    </button>
                  ))}
                </div>
              </fieldset>
              <details className="group">
                <summary className="flex cursor-pointer items-center gap-1 text-xs text-muted hover:text-ink"><ChevronDown className="size-3.5 transition-transform group-open:rotate-180" /> Fine-tune parameters</summary>
                <div className="mt-3 space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Advance cycles"><input type="number" min={0} max={200} className={inputCls} value={p.advance_cycles} onChange={(e) => set({ advance_cycles: Math.max(0, +e.target.value) })} /></Field>
                    <Field label="Seed"><input type="number" min={0} className={inputCls} value={p.seed} onChange={(e) => set({ seed: Math.max(0, +e.target.value) })} /></Field>
                    <Field label="Noise (× step σ)"><input type="number" min={0} max={20} step={0.5} className={inputCls} value={p.noise_sigma} onChange={(e) => set({ noise_sigma: +e.target.value })} /></Field>
                    <Field label="Stale link (hours)"><input type="number" min={0} className={inputCls} value={p.stale_hours} onChange={(e) => set({ stale_hours: Math.max(0, +e.target.value) })} /></Field>
                    <Field label="Bias sensor">
                      <select className={inputCls} value={p.bias_sensor ?? ''} onChange={(e) => set({ bias_sensor: e.target.value || null })}>
                        <option value="">none</option>{sensors.map((s) => <option key={s}>{s}</option>)}
                      </select>
                    </Field>
                    <Field label="Bias (× step σ)"><input type="number" min={0} max={100} className={inputCls} value={p.bias_sigma} onChange={(e) => set({ bias_sigma: +e.target.value })} /></Field>
                    <Field label="Dropout: last N readings"><input type="number" min={1} max={50} className={inputCls} value={p.dropout_last_n} onChange={(e) => set({ dropout_last_n: Math.max(1, +e.target.value) })} /></Field>
                    <Field label="Part delay (days)"><input type="number" min={0} max={60} className={inputCls} value={p.part_delay_days} onChange={(e) => set({ part_delay_days: Math.max(0, +e.target.value) })} /></Field>
                  </div>
                  <ChipGroup label="Missing sensors" items={sensors} selected={p.dropout_sensors} onToggle={(s) => set({ dropout_sensors: toggle(p.dropout_sensors, s) })} />
                  <ChipGroup label="Parts unavailable" items={parts.data?.items.map((x) => x.part_number) ?? []} selected={p.unavailable_parts} onToggle={(s) => set({ unavailable_parts: toggle(p.unavailable_parts, s) })} />
                  <ChipGroup label="Technicians unavailable" items={techs.data?.items.map((x) => x.code) ?? []} selected={p.unavailable_technicians} onToggle={(s) => set({ unavailable_technicians: toggle(p.unavailable_technicians, s) })} />
                </div>
              </details>
              {can('scenario:run') ? (
                <div className="flex gap-2">
                  <Button variant="primary" className="flex-1" busy={run.isPending} onClick={() => run.mutate(p)}><Play className="size-3.5" /> Run scenario</Button>
                  <Button variant="ghost" onClick={() => setParams(blank(p.engine_id))} aria-label="Reset disruptions"><RotateCcw className="size-3.5" /></Button>
                </div>
              ) : <p className="text-xs text-muted">Your role cannot run scenarios.</p>}
              {run.isError && <ErrorState error={run.error} />}
            </div>
          </Panel>
          <Panel title="Recent runs">
            {history.data?.items.length ? (
              <ul className="space-y-1 text-[13px]">
                {history.data.items.map((h) => (
                  <li key={h.id}>
                    <button onClick={() => setRunId(h.id)} className={cx('flex w-full items-center justify-between gap-2 rounded px-2 py-1 text-left hover:bg-raised', runId === h.id && 'bg-raised')}>
                      <span className="num">#{h.id} {h.engine.serial}</span>
                      <span className="flex items-center gap-1"><TrustBadge state={h.baseline_state} /><ArrowRight className="size-3 text-muted" /><TrustBadge state={h.revised_state} /></span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : <Empty>No runs yet.</Empty>}
          </Panel>
        </div>

        {/* ------------------------------------------------ results */}
        <div className="min-w-0 space-y-5">
          {!runId ? (
            <Panel>
              <div className="py-6 text-[13px] text-muted">
                <p className="text-ink">Suggested demonstration</p>
                <ol className="mt-2 list-decimal space-y-1 pl-5">
                  <li>Pick <span className="num text-ink">AP-101 · AP-ENG-01</span> and run with no disruption: the model predicts end-of-life is near and recommends a planned replacement.</li>
                  <li>Toggle <span className="text-ink">Spare part unavailable</span> and run: the optimiser re-plans and the replacement can no longer be scheduled — the risk table shows why.</li>
                  <li>Add <span className="text-ink">Sensor readings disappear</span>: TrustTwin downgrades the prediction and asks for verification instead.</li>
                  <li>Review the revised plan below as an officer: approve or reject with a reason. The decision is recorded against the scenario and in the audit log.</li>
                </ol>
              </div>
            </Panel>
          ) : loaded.isPending || run.isPending ? <Loading label="Re-assessing and re-planning" /> : loaded.isError ? <ErrorState error={loaded.error} /> : result && <Result r={result} />}
        </div>
      </div>

      <PolicyComparison />
    </>
  )
}

function ChipGroup({ label, items, selected, onToggle }: { label: string; items: string[]; selected: string[]; onToggle: (s: string) => void }) {
  return (
    <fieldset>
      <legend className="mb-1 text-xs text-muted">{label}</legend>
      <div className="flex flex-wrap gap-1">
        {items.map((s) => (
          <button key={s} type="button" aria-pressed={selected.includes(s)} onClick={() => onToggle(s)}
            className={cx('num rounded border px-1.5 py-0.5 text-[11px] transition-colors', selected.includes(s) ? 'border-tech bg-tech/15 text-ink' : 'border-line-strong text-muted hover:text-ink')}>{s}</button>
        ))}
      </div>
    </fieldset>
  )
}

// ---------------------------------------------------------------- result view
function Stage({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <li className="relative min-w-0 rounded-md border border-line bg-surface p-3">
      <div className="mb-2 flex items-center gap-2 text-xs text-muted"><span className="num grid size-5 place-items-center rounded-full border border-line-strong text-[11px] text-ink">{n}</span>{title}</div>
      {children}
    </li>
  )
}
const Pair = ({ a, b }: { a: ReactNode; b: ReactNode }) => (
  <div className="space-y-1 text-[13px]">
    <div className="flex items-start gap-2"><span className="w-14 shrink-0 text-[11px] text-muted">baseline</span><div className="min-w-0">{a}</div></div>
    <div className="flex items-start gap-2"><span className="w-14 shrink-0 text-[11px] text-tech">revised</span><div className="min-w-0">{b}</div></div>
  </div>
)

function Result({ r }: { r: Run }) {
  const { baseline: b, revised: v } = r.result
  const [tab, setTab] = useState<'revised' | 'baseline'>('revised')
  const revSched = r.review.schedules.find((s) => s.solver.includes('revised'))
  const techs = useMemo(() => (v.plan.problem?.techs ?? []).map((t) => t.id), [v.plan])
  const blocked = useMemo(() => Object.fromEntries((v.plan.problem?.techs ?? []).map((t) => [t.id, t.blocked])), [v.plan])
  const plan = tab === 'revised' ? v.plan : b.plan
  const constraints = r.result.explanation.filter((e) => /unavailable|Spare|Technicians|inspections|slips/i.test(e))

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <span><span className="num text-ink">Run #{r.id}</span> · {r.result.engine.aircraft} · {r.result.engine.serial} · {r.result.engine.source}</span>
        <span className="num">seed {r.seed} · result {r.result_hash.slice(0, 16)}</span>
      </div>

      <ol aria-label="Decision pipeline" className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
        <Stage n={1} title="Current health & data quality">
          <Pair a={<TrustBadge state={b.assessment.state} />} b={<span className="flex flex-wrap items-center gap-1"><TrustBadge state={v.assessment.state} />
            <span className="text-[11px] text-muted">{v.assessment.checks.filter((c) => c.status === 'warn' || c.status === 'fail').length} checks flagged</span></span>} />
        </Stage>
        <Stage n={2} title="Prediction evidence (RUL, cycles)">
          <Pair a={<span className="num">{fmt(b.assessment.rul)} [{fmt(b.assessment.rul_lower)}–{fmt(b.assessment.rul_upper)}]</span>}
                b={v.assessment.rul == null ? <span className="text-crit">withheld</span> : <span className="num">{fmt(v.assessment.rul)} [{fmt(v.assessment.rul_lower)}–{fmt(v.assessment.rul_upper)}]</span>} />
        </Stage>
        <Stage n={3} title="Recommended action">
          <Pair a={b.recommendation ? <span>{b.recommendation.action}</span> : <span className="text-muted">none — routine</span>}
                b={v.recommendation ? <span className="flex flex-wrap items-center gap-1"><PriorityTag p={v.recommendation.priority} />{v.recommendation.action}</span> : <span className="text-muted">none — routine</span>} />
        </Stage>
        <Stage n={4} title="Resource constraints">
          {constraints.length ? <ul className="space-y-1 text-[12px] text-warn">{constraints.map((c, i) => <li key={i}>{c}</li>)}</ul> : <p className="text-[13px] text-muted">No resource disruption.</p>}
        </Stage>
        <Stage n={5} title="Revised plan (CP-SAT)">
          <Pair a={<span className="num">{b.plan.kpis.scheduled} sched · {b.plan.kpis.unscheduled} unsched · {b.plan.kpis.late_tasks} late · obj {fmt(b.plan.objective)}</span>}
                b={<span className="num">{v.plan.kpis.scheduled} sched · <span className={v.plan.kpis.unscheduled ? 'text-crit' : ''}>{v.plan.kpis.unscheduled} unsched</span> · {v.plan.kpis.late_tasks} late · obj {fmt(v.plan.objective)}</span>} />
          <p className="num mt-1 text-[11px] text-muted">rule-based baseline on revised inputs: obj {fmt(v.rule_based_objective)} · {v.rule_based_plan_kpis.unscheduled} unsched</p>
        </Stage>
        <Stage n={6} title="Human approval">
          <div className="space-y-1 text-[13px]">
            <div>Recommendation: <Tag tone={r.review.recommendation?.status === 'approved' ? 'ok' : r.review.recommendation?.status === 'rejected' ? 'crit' : 'warn'}>{r.review.recommendation?.status ?? 'none'}</Tag></div>
            <div>Revised plan: <Tag tone={revSched?.status === 'approved' ? 'ok' : revSched?.status === 'rejected' ? 'crit' : 'warn'}>{revSched?.status ?? '—'}</Tag></div>
            <p className="text-[11px] text-muted">The model never approves. An officer decides below.</p>
          </div>
        </Stage>
      </ol>

      <Panel title="Why the plan changed" meta="generated from computed results, not an LLM">
        <ul className="list-disc space-y-1 pl-4 text-[13px] text-ink marker:text-muted">{r.result.explanation.map((e, i) => <li key={i}>{e}</li>)}</ul>
      </Panel>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Revised data-quality assessment" meta={<TrustBadge state={v.assessment.state} />}>
          <p className="mb-3 text-[13px] text-muted">{v.assessment.summary}</p>
          <CheckList checks={v.assessment.checks} />
          {Object.keys(v.assessment.imputed ?? {}).length > 0 && <p className="mt-2 text-xs text-warn">Imputed: {Object.keys(v.assessment.imputed).join(', ')}</p>}
        </Panel>
        <Panel title="Prediction uncertainty" meta={<span className="num">{v.assessment.model_version}</span>}>
          <div className="space-y-5">
            <div><div className="mb-1 text-xs text-muted">Baseline (cycle {b.assessment.cycle})</div><RulGauge rul={b.assessment.rul} lo={b.assessment.rul_lower} hi={b.assessment.rul_upper} /></div>
            <div><div className="mb-1 text-xs text-tech">Revised (cycle {v.assessment.cycle})</div><RulGauge rul={v.assessment.rul} lo={v.assessment.rul_lower} hi={v.assessment.rul_upper} /></div>
            {v.assessment.evidence.length > 0 && (
              <div>
                <div className="mb-1 text-xs text-muted">Top contributions (TreeSHAP, cycles)</div>
                <ul className="num grid grid-cols-1 gap-x-4 text-[12px] sm:grid-cols-2">
                  {v.assessment.evidence.slice(0, 6).map((e) => <li key={e.feature} className="flex justify-between gap-2"><span className="text-muted">{e.feature} ({e.sensor})</span><span className={e.contribution < 0 ? 'text-crit' : 'text-ok'}>{e.contribution > 0 ? '+' : ''}{e.contribution.toFixed(1)}</span></li>)}
                </ul>
              </div>
            )}
          </div>
        </Panel>
      </div>

      <Panel title="Baseline vs revised plan" meta={
        <div role="radiogroup" aria-label="Plan" className="inline-flex rounded border border-line-strong p-0.5">
          {(['revised', 'baseline'] as const).map((t) => (
            <button key={t} role="radio" aria-checked={tab === t} onClick={() => setTab(t)}
              className={cx('rounded px-2 py-0.5 text-xs', tab === t ? 'bg-raised text-ink' : 'text-muted hover:text-ink')}>{t}</button>
          ))}
        </div>}>
        <Gantt assignments={plan.assignments} techs={techs} blocked={blocked} horizonStart={r.result.horizon_start} />
        {plan.unscheduled.length > 0 && (
          <ul className="mt-3 space-y-1 text-[13px]">{plan.unscheduled.map((u) => <li key={u.task}><span className="num text-crit">{u.task}</span> <span className="text-muted">unscheduled — {u.reason}</span></li>)}</ul>
        )}
        {r.result.diff.length > 0 && (
          <div className="mt-4">
            <div className="mb-1 text-xs text-muted">Changes from baseline</div>
            <Table head={['Task', 'Change', 'Start (h from horizon)', 'Technician / reason']} dense>
              {r.result.diff.map((d) => (
                <tr key={d.task}><td className="num">{d.task}</td><td><Tag tone={d.change === 'now unscheduled' ? 'crit' : d.change === 'added' || d.change === 'action changed' ? 'tech' : undefined}>{d.change}</Tag></td>
                  <td className="num">{d.from ?? '—'} → {d.to ?? '—'}</td><td className="text-muted">{d.tech_from || d.tech_to ? `${d.tech_from ?? '—'} → ${d.tech_to ?? '—'}` : ''}{d.reason && <div>{d.reason}</div>}</td></tr>
              ))}
            </Table>
          </div>
        )}
      </Panel>

      <Panel title="Projected consequences — engine risk margin" meta={v.outcomes.note}>
        {v.outcomes.engine_risk.length === 0 ? <Empty>No predicted engine is linked to a planned task.</Empty> : (
          <Table head={['Task', 'Engine', 'RUL lower bound', 'Starts in', 'Cycles flown before start', 'Margin', 'Status']}>
            {v.outcomes.engine_risk.map((x) => (
              <tr key={x.task}><td className="num">{x.task}</td><td className="num">#{x.engine_id}</td><td className="num">{x.rul_lower}</td>
                <td className="num">{x.starts_in_h == null ? '—' : `${x.starts_in_h} h`}</td><td className="num">{x.cycles_flown_before_start ?? '—'}</td>
                <td className="num">{x.margin_cycles ?? '—'}</td>
                <td><Tag tone={x.flag === 'ok' ? 'ok' : 'crit'}>{x.flag}</Tag></td></tr>
            ))}
          </Table>
        )}
        <p className="mt-2 text-[11px] text-muted">Margin = lower-bound RUL minus cycles flown at the assumed utilisation before maintenance starts. Negative or unscheduled means the plan relies on the engine outliving its conservative estimate.</p>
      </Panel>

      <Panel title="Officer review" meta={r.result.sandbox_note}>
        <div className="grid gap-5 lg:grid-cols-2">
          <div>
            <div className="mb-1 text-[13px]">Recommendation {r.review.recommendation && <span className="num text-muted">REC-{r.review.recommendation.id}</span>}</div>
            {r.review.recommendation?.status === 'proposed'
              ? <DecisionForm target="recommendation" id={r.review.recommendation.id} options={['approve', 'reject', 'request_inspection', 'request_data']} />
              : <p className="text-xs text-muted">{r.review.recommendation ? `Decided: ${r.review.recommendation.status}` : 'No action recommended.'}</p>}
          </div>
          <div>
            <div className="mb-1 text-[13px]">Revised plan {revSched && <span className="num text-muted">#{revSched.id}</span>}</div>
            {revSched?.status === 'proposed' ? <DecisionForm target="schedule" id={revSched.id} /> : <p className="text-xs text-muted">Decided: {revSched?.status}</p>}
          </div>
        </div>
        {r.review.decisions.length > 0 && (
          <div className="mt-4 border-t border-line pt-3">
            <div className="mb-1 text-xs text-muted">Decision record</div>
            <ul className="space-y-1 text-[13px]">
              {r.review.decisions.map((d) => <li key={d.id}><span className="num">{d.target_type} #{d.target_id}</span> <Tag tone={d.decision === 'approve' ? 'ok' : 'crit'}>{d.decision}</Tag> by <span className="text-ink">{d.user}</span> ({d.role}) <span className="text-muted">— “{d.reason}” · {new Date(d.created_at).toLocaleString()}</span></li>)}
            </ul>
          </div>
        )}
      </Panel>
    </>
  )
}

// ---------------------------------------------------------------- policy comparison (digital twin)
type Metrics = Record<string, number>
interface SimRun { id: number; seed: number; result: { label: string; identical_conditions: string; data_note: string; params: Record<string, number>
  reactive: { metrics: Metrics; daily_availability_pct: number[] }; predictive: { metrics: Metrics; daily_availability_pct: number[] }; delta: Metrics; result_hash: string } }

const METRIC_LABELS: [string, string, 'lower' | 'higher' | 'info'][] = [
  ['availability_pct', 'Simulated fleet availability (%)', 'higher'], ['downtime_hours', 'Maintenance downtime (aircraft-hours)', 'lower'],
  ['failures', 'Unscheduled failures', 'lower'], ['planned_replacements', 'Planned replacements', 'info'], ['inspections', 'Verification inspections', 'info'],
  ['degraded_predictions', 'Degraded (rejected) predictions', 'info'], ['delayed_jobs', 'Delayed tasks (> 2 days waiting)', 'lower'],
  ['part_shortage_job_days', 'Job-days waiting for parts', 'lower'], ['crew_shortage_job_days', 'Job-days waiting for crew', 'lower'],
  ['wasted_life_cycles', 'Remaining life removed early (cycles)', 'lower'], ['unresolved_at_end', 'Unresolved maintenance events at end', 'lower'],
]

function PolicyComparison() {
  const { can } = useAuth()
  const latest = useQuery({ queryKey: ['sim-latest'], queryFn: () => api.get<SimRun>('/simulation/latest') })
  const [form, setForm] = useState({ seed: 2026, days: 120, crews: 2, spare_engines: 4, resupply_every_days: 14, resupply_qty: 3, dropout_prob: 0.02, trigger_lower_bound: 25 })
  const run = useMutation({ mutationFn: () => api.post<SimRun>('/simulation/compare', form), onSuccess: () => latest.refetch() })
  const s = latest.data
  const chart = s ? s.result.reactive.daily_availability_pct.map((x, i) => ({ day: i + 1, reactive: x, predictive: s.result.predictive.daily_availability_pct[i] })) : []
  return (
    <section className="mt-8">
      <PageHeader title="Fleet digital twin — policy comparison"
        subtitle="Policy A (reactive) vs Policy B (predictive, TrustTwin-gated, human-reviewed) under identical synthetic conditions. Engine degradation replays C-MAPSS hold-out trajectories; predictions come from the trained model." actions={<SimLabel />} />
      <div className="grid gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">
        <Panel title="Simulation inputs">
          <div className="grid grid-cols-2 gap-3">
            {(Object.keys(form) as (keyof typeof form)[]).map((k) => (
              <Field key={k} label={k.replaceAll('_', ' ')}>
                <input type="number" step={k === 'dropout_prob' ? 0.01 : 1} min={0} className={inputCls} value={form[k]} onChange={(e) => setForm({ ...form, [k]: +e.target.value })} />
              </Field>
            ))}
          </div>
          {can('scenario:run') && <Button variant="primary" className="mt-3 w-full" busy={run.isPending} onClick={() => run.mutate()}>Run both policies</Button>}
          {run.isError && <div className="mt-2"><ErrorState error={run.error} /></div>}
        </Panel>
        <div className="min-w-0 space-y-5">
          {latest.isPending ? <Loading /> : latest.isError ? <ErrorState error={latest.error} /> : s && (
            <>
              <Panel title="Outcome metrics" meta={<span className="num">run #{s.id} · seed {s.seed} · {s.result.result_hash.slice(0, 12)}</span>}>
                <Table head={['Metric', 'A · reactive', 'B · predictive', 'B − A']}>
                  {METRIC_LABELS.map(([k, label, better]) => {
                    const d = s.result.delta[k]
                    const good = better === 'info' || d === 0 ? undefined : (better === 'higher' ? d > 0 : d < 0)
                    return (
                      <tr key={k}><td>{label}</td><td className="num">{s.result.reactive.metrics[k]}</td><td className="num">{s.result.predictive.metrics[k]}</td>
                        <td className={cx('num', good === true && 'text-ok', good === false && 'text-crit')}>{d > 0 ? '+' : ''}{d}</td></tr>
                    )
                  })}
                </Table>
                <p className="mt-2 text-[11px] text-muted">{s.result.identical_conditions} {s.result.data_note} {s.result.label}</p>
              </Panel>
              <Panel title="Daily simulated availability">
                <div className="h-56">
                  <ResponsiveContainer>
                    <LineChart data={chart} margin={{ top: 5, right: 10, bottom: 15, left: 0 }}>
                      <CartesianGrid strokeDasharray="2 4" />
                      <XAxis dataKey="day" label={{ value: 'simulated day', position: 'insideBottom', offset: -8 }} />
                      <YAxis domain={[40, 100]} unit="%" width={44} />
                      <Tooltip formatter={(x: number) => `${x}%`} labelFormatter={(l) => `Day ${l}`} />
                      <Legend verticalAlign="top" height={24} />
                      <Line dataKey="reactive" name="A · reactive" stroke="var(--color-muted)" dot={false} isAnimationActive={false} />
                      <Line dataKey="predictive" name="B · predictive" stroke="var(--color-tech)" dot={false} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </Panel>
            </>
          )}
        </div>
      </div>
    </section>
  )
}
