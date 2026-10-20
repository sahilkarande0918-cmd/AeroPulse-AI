import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, type MaintState, type Part, type Prediction, type TrustState } from '../api'
import { ErrorState, Loading, MaintBadge, PageHeader, Panel, RulGauge, SimLabel, Stat, Table, TrustBadge, ago, fmt, fmtTime } from '../ui'

interface Overview {
  aircraft_total: number; engines_total: number
  maintenance_states: Partial<Record<MaintState, number>>; trust_states: Partial<Record<TrustState, number>>
  warnings: { aircraft_id: number; tail: string; state: MaintState; engines: { serial: string; state: TrustState; rul_lower: number | null }[] }[]
  outstanding_inspections: number; pending_recommendations: number
  workload: { open_work_orders: number; planned_hours: number; pending_approval: number; by_skill: Record<string, number> }
  parts_shortages: Part[]; latest_prediction: Prediction | null
  recent_events: { id: number; at: string; actor: string; action: string; entity: string }[]
  simulated_availability: { label: string; run_id: number; seed: number; reactive: number[]; predictive: number[] } | null
  data_note: string
}

const STATE_ORDER: MaintState[] = ['action_required', 'watch', 'in_maintenance', 'routine']
const STATE_COLOR: Record<MaintState, string> = { action_required: 'bg-crit', watch: 'bg-warn', in_maintenance: 'bg-tech', routine: 'bg-ok' }

export default function Overview() {
  const q = useQuery({ queryKey: ['overview'], queryFn: () => api.get<Overview>('/fleet/overview') })
  if (q.isPending) return <Loading />
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />
  const d = q.data
  const sim = d.simulated_availability
  const simData = sim?.reactive.map((r, i) => ({ day: i + 1, reactive: r, predictive: sim.predictive[i] })) ?? []

  return (
    <>
      <PageHeader title="Command overview" subtitle={d.data_note} />
      <div className="mb-5 grid grid-cols-2 gap-x-4 gap-y-4 rounded-md border border-line bg-surface p-4 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Aircraft / engines" value={`${d.aircraft_total} / ${d.engines_total}`} />
        <Stat label="Action required" value={d.maintenance_states.action_required ?? 0} tone="crit" note="lower RUL bound ≤ critical or P1 open" />
        <Stat label="On watch" value={d.maintenance_states.watch ?? 0} tone="warn" note="degraded data or warning bound" />
        <Stat label="Open work orders" value={d.workload.open_work_orders} note={`${d.workload.planned_hours} h planned · ${d.workload.pending_approval} pending approval`} />
        <Stat label="Outstanding inspections" value={d.outstanding_inspections} note={`${d.pending_recommendations} recommendations awaiting review`} />
        <Stat label="Parts shortages" value={d.parts_shortages.length} tone={d.parts_shortages.length ? 'crit' : 'ok'} note="reserved > on hand" />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Panel title="Maintenance status distribution" className="lg:col-span-1">
          <div className="flex h-3 overflow-hidden rounded-full bg-raised" role="img" aria-label="Fleet maintenance state distribution">
            {STATE_ORDER.map((s) => (d.maintenance_states[s] ?? 0) > 0 && (
              <div key={s} className={STATE_COLOR[s]} style={{ width: `${((d.maintenance_states[s] ?? 0) / d.aircraft_total) * 100}%` }} />
            ))}
          </div>
          <ul className="mt-3 space-y-1.5">
            {STATE_ORDER.map((s) => (
              <li key={s} className="flex items-center justify-between text-[13px]">
                <MaintBadge state={s} /><span className="num text-ink">{d.maintenance_states[s] ?? 0}</span>
              </li>
            ))}
          </ul>
          <div className="mt-4 border-t border-line pt-3">
            <div className="mb-2 text-xs text-muted">TrustTwin state of latest engine predictions</div>
            <div className="flex flex-wrap gap-3">
              {(['VALID', 'DEGRADED', 'UNAVAILABLE'] as TrustState[]).map((s) => (
                <span key={s} className="flex items-center gap-1.5"><TrustBadge state={s} /><span className="num">{d.trust_states[s] ?? 0}</span></span>
              ))}
            </div>
          </div>
        </Panel>

        <Panel title="Aircraft with active warnings" className="lg:col-span-2" meta={`${d.warnings.length} aircraft`}>
          <Table head={['Aircraft', 'State', 'Engines (trust · lower RUL bound)']}>
            {d.warnings.map((w) => (
              <tr key={w.aircraft_id}>
                <td><Link to={`/fleet/${w.aircraft_id}`} className="num whitespace-nowrap text-tech hover:underline">{w.tail}</Link></td>
                <td><MaintBadge state={w.state} /></td>
                <td>
                  <div className="flex flex-wrap gap-x-4 gap-y-1">
                    {w.engines.map((e) => (
                      <span key={e.serial} className="flex items-center gap-1.5">
                        <span className="num text-muted">{e.serial}</span><TrustBadge state={e.state} />
                        <span className="num">{e.rul_lower == null ? '—' : `≥${fmt(e.rul_lower)} cyc`}</span>
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </Table>
        </Panel>

        <Panel title="Simulated fleet availability" className="lg:col-span-2" meta={sim && <SimLabel />}>
          {sim ? (
            <>
              <div className="h-60">
                <ResponsiveContainer>
                  <LineChart data={simData} margin={{ top: 5, right: 10, bottom: 15, left: 0 }}>
                    <CartesianGrid strokeDasharray="2 4" />
                    <XAxis dataKey="day" label={{ value: 'simulated day', position: 'insideBottom', offset: -8 }} />
                    <YAxis domain={[50, 100]} unit="%" width={44} />
                    <Tooltip formatter={(v: number) => `${v}%`} labelFormatter={(l) => `Day ${l}`} />
                    <Legend verticalAlign="top" height={24} />
                    <Line dataKey="reactive" name="Policy A · reactive" stroke="var(--color-muted)" dot={false} strokeWidth={1.5} />
                    <Line dataKey="predictive" name="Policy B · predictive, human-reviewed" stroke="var(--color-tech)" dot={false} strokeWidth={1.5} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-1 text-[11px] text-muted">{sim.label} Run #{sim.run_id}, seed {sim.seed}. Compare details on the TrustTwin page.</p>
            </>
          ) : <p className="text-[13px] text-muted">No simulation run yet.</p>}
        </Panel>

        <Panel title="Latest prediction">
          {d.latest_prediction ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-[13px]">
                <span className="num text-muted">engine #{d.latest_prediction.engine_id} · cycle {d.latest_prediction.cycle}</span>
                <TrustBadge state={d.latest_prediction.state} />
              </div>
              <RulGauge rul={d.latest_prediction.rul} lo={d.latest_prediction.rul_lower} hi={d.latest_prediction.rul_upper} />
              <p className="text-xs text-muted">{d.latest_prediction.summary}</p>
              <p className="num text-[11px] text-muted">{d.latest_prediction.model_version} · {fmtTime(d.latest_prediction.created_at)}</p>
            </div>
          ) : <p className="text-[13px] text-muted">No predictions.</p>}
        </Panel>

        <Panel title="Parts shortages">
          {d.parts_shortages.length === 0 ? <p className="text-[13px] text-muted">No reserved-stock shortages.</p> : (
            <ul className="space-y-2 text-[13px]">
              {d.parts_shortages.map((p) => (
                <li key={p.part_number}>
                  <Link to="/parts" className="num text-crit hover:underline">{p.part_number}</Link>
                  <span className="text-muted"> — {p.available} available · blocks {p.affected_work_orders.map((w) => w.code).join(', ')}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-4 border-t border-line pt-3 text-xs text-muted">
            Workload by skill: {Object.entries(d.workload.by_skill).map(([k, v]) => `${k} ${v}`).join(' · ') || '—'}
          </div>
        </Panel>

        <Panel title="Recent events" className="lg:col-span-2" meta={<Link to="/reports" className="text-tech hover:underline">Audit log</Link>}>
          <ul className="divide-y divide-line/60 text-[13px]">
            {d.recent_events.map((e) => (
              <li key={e.id} className="flex flex-wrap justify-between gap-2 py-1.5">
                <span><span className="text-ink">{e.actor}</span> <span className="num text-tech">{e.action}</span> <span className="text-muted">{e.entity}</span></span>
                <span className="text-xs text-muted">{ago(e.at)}</span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </>
  )
}
