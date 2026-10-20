import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, RefreshCw } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, type AircraftRow, type EngineRow, type Prediction, type Recommendation, type WorkOrder } from '../api'
import { useAuth } from '../auth'
import { DecisionForm } from '../decide'
import {
  Button, CheckList, Empty, ErrorState, Field, Loading, MaintBadge, PageHeader, Panel, PriorityTag, RulGauge, Table, Tag, TrustBadge,
  ago, fmt, fmtTime, inputCls,
} from '../ui'

interface Detail extends AircraftRow {
  work_orders: WorkOrder[]
  maintenance_records: { id: number; performed_at: string; record_type: string; description: string; engine_id: number | null; performed_by: string; source: string }[]
  recommendations: Recommendation[]
}

export default function AircraftDetail() {
  const { id } = useParams()
  const q = useQuery({ queryKey: ['aircraft', id], queryFn: () => api.get<Detail>(`/aircraft/${id}`) })
  if (q.isPending) return <Loading />
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />
  const a = q.data
  return (
    <>
      <Link to="/fleet" className="mb-3 inline-flex items-center gap-1 text-xs text-muted hover:text-ink"><ArrowLeft className="size-3.5" /> Fleet</Link>
      <PageHeader title={`${a.tail} · health detail`} subtitle={`${a.type_name} · ${a.base} · last data ${ago(a.last_data_update)}`}
        actions={<MaintBadge state={a.maintenance_state} />} />
      <div className="space-y-5">
        {a.engines.map((e) => <EnginePanel key={e.id} engine={e} />)}
        <div className="grid gap-5 lg:grid-cols-2">
          <Panel title="Recommendations" meta="model output → human decision">
            {a.recommendations.length === 0 ? <Empty>No recommendations for this aircraft.</Empty> : (
              <ul className="space-y-4">
                {a.recommendations.map((r) => (
                  <li key={r.id} className="border-b border-line/60 pb-3 last:border-0">
                    <div className="flex flex-wrap items-center gap-2 text-[13px]">
                      <PriorityTag p={r.priority} /><span className="font-medium text-ink">{r.action}</span>
                      <Tag tone={r.status === 'approved' ? 'ok' : r.status === 'rejected' ? 'crit' : undefined}>{r.status}</Tag>
                    </div>
                    <p className="mt-1 text-xs text-muted">{r.rationale}</p>
                    <p className="num mt-1 text-[11px] text-muted">REC-{r.id} · prediction #{r.prediction_id} · {fmtTime(r.created_at)}</p>
                    {r.status === 'proposed' && <div className="mt-2"><DecisionForm target="recommendation" id={r.id} options={['approve', 'reject', 'request_inspection', 'request_data']} /></div>}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel title="Work orders">
            {a.work_orders.length === 0 ? <Empty>No work orders.</Empty> : (
              <Table head={['Code', 'Task', 'Priority', 'Due', 'Status']}>
                {a.work_orders.map((w) => (
                  <tr key={w.id}>
                    <td className="num text-muted">{w.code}</td><td>{w.title}<div className="text-[11px] text-muted">{w.required_skill} · {w.duration_hours} h</div></td>
                    <td><PriorityTag p={w.priority} /></td><td className="whitespace-nowrap text-muted">{fmtTime(w.due_at)}</td>
                    <td><Tag>{w.status}</Tag> <Tag tone={w.approval_state === 'approved' ? 'ok' : w.approval_state === 'rejected' ? 'crit' : 'warn'}>{w.approval_state}</Tag></td>
                  </tr>
                ))}
              </Table>
            )}
          </Panel>
        </div>
        <Panel title="Technical maintenance records" meta="integrated from technical-log sources">
          {a.maintenance_records.length === 0 ? <Empty>No records.</Empty> : (
            <Table head={['Date', 'Type', 'Description', 'By', 'Source']}>
              {a.maintenance_records.map((m) => (
                <tr key={m.id}>
                  <td className="whitespace-nowrap text-muted">{fmtTime(m.performed_at)}</td><td><Tag>{m.record_type}</Tag></td>
                  <td>{m.description}</td><td className="text-muted">{m.performed_by}</td><td className="num text-[11px] text-muted">{m.source}</td>
                </tr>
              ))}
            </Table>
          )}
        </Panel>
      </div>
    </>
  )
}

function EnginePanel({ engine }: { engine: EngineRow }) {
  const { can } = useAuth()
  const qc = useQueryClient()
  const p = engine.prediction
  const rerun = useMutation({ mutationFn: () => api.post<Prediction>(`/engines/${engine.id}/predict`), onSuccess: () => qc.invalidateQueries() })
  return (
    <Panel title={<span className="num">Engine #{engine.position} · {engine.serial}</span>}
      meta={<span className="flex items-center gap-2">{engine.source}{p && <TrustBadge state={p.state} />}</span>}>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)]">
        <div className="space-y-4">
          {p ? (
            <>
              <RulGauge rul={p.rul} lo={p.rul_lower} hi={p.rul_upper} />
              <p className="text-[13px] text-muted">{p.summary}</p>
              <div>
                <div className="mb-2 text-xs font-medium text-muted">Data-quality assessment (TrustTwin)</div>
                <CheckList checks={p.checks ?? []} />
                {p.imputed && Object.keys(p.imputed).length > 0 && (
                  <p className="mt-2 text-xs text-warn">Imputed (last valid value carried forward): {Object.keys(p.imputed).join(', ')}</p>
                )}
              </div>
              <p className="num text-[11px] text-muted">prediction #{p.id} · cycle {p.cycle} · {p.n_cycles} cycles of history · model {p.model_version} · {fmtTime(p.created_at)}</p>
            </>
          ) : <Empty>No prediction yet.</Empty>}
          {can('scenario:run') && (
            <Button busy={rerun.isPending} onClick={() => rerun.mutate()}><RefreshCw className="size-3.5" /> Re-assess with trained model</Button>
          )}
          {rerun.isError && <ErrorState error={rerun.error} />}
        </div>
        <div className="space-y-5">
          {p?.evidence && p.evidence.length > 0 && <Evidence p={p} />}
          <SensorChart engineId={engine.id} />
        </div>
      </div>
    </Panel>
  )
}

function Evidence({ p }: { p: Prediction }) {
  const data = (p.evidence ?? []).map((e) => ({ name: e.feature, sensor: e.sensor, c: +e.contribution.toFixed(2), v: e.value }))
  return (
    <div>
      <div className="mb-1 text-xs font-medium text-muted">Prediction evidence — TreeSHAP contribution to RUL (cycles); negative pulls the estimate down</div>
      <div className="h-56">
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ left: 10, right: 16, top: 4, bottom: 14 }}>
            <CartesianGrid strokeDasharray="2 4" horizontal={false} />
            <XAxis type="number" label={{ value: 'contribution (cycles)', position: 'insideBottom', offset: -6 }} />
            <YAxis type="category" dataKey="name" width={110} />
            <Tooltip formatter={(v: number, _n, item) => [`${v} cycles (value ${(item.payload as { v: number }).v.toFixed(3)})`, (item.payload as { sensor: string }).sensor]} />
            <Bar dataKey="c" isAnimationActive={false}>
              {data.map((d) => <Cell key={d.name} fill={d.c < 0 ? 'var(--color-crit)' : 'var(--color-ok)'} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

interface Readings { sensors: Record<string, { symbol: string; description: string; unit: string }>; readings: Record<string, number | string>[] }

function SensorChart({ engineId }: { engineId: number }) {
  const q = useQuery({ queryKey: ['readings', engineId], queryFn: () => api.get<Readings>(`/engines/${engineId}/readings?last=400`) })
  const [sensor, setSensor] = useState('s4')
  if (q.isPending) return <Loading label="Loading sensor history" />
  if (q.isError) return <ErrorState error={q.error} />
  const meta = q.data.sensors[sensor]
  const rows = q.data.readings.map((r) => ({ cycle: r.cycle as number, v: (r[sensor] as number | undefined) ?? null }))
  const vals = rows.map((r) => r.v).filter((v): v is number => v != null)
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
        <div className="text-xs font-medium text-muted">Sensor history — {meta?.description} ({meta?.symbol})</div>
        <div className="w-56"><Field label="Sensor">
          <select className={inputCls} value={sensor} onChange={(e) => setSensor(e.target.value)}>
            {Object.entries(q.data.sensors).map(([k, m]) => <option key={k} value={k}>{k} · {m.symbol} · {m.description}</option>)}
          </select>
        </Field></div>
      </div>
      <div className="h-56">
        <ResponsiveContainer>
          <LineChart data={rows} margin={{ left: 0, right: 12, top: 4, bottom: 14 }}>
            <CartesianGrid strokeDasharray="2 4" />
            <XAxis dataKey="cycle" label={{ value: 'operating cycle', position: 'insideBottom', offset: -6 }} />
            <YAxis domain={[Math.min(...vals), Math.max(...vals)]} width={64} tickFormatter={(v: number) => v.toFixed(2)}
              label={{ value: meta?.unit, angle: -90, position: 'insideLeft', offset: 10 }} />
            <Tooltip formatter={(v: number) => [`${v} ${meta?.unit}`, meta?.symbol]} labelFormatter={(l) => `cycle ${l}`} />
            <Line dataKey="v" stroke="var(--color-tech)" dot={false} strokeWidth={1.25} isAnimationActive={false} connectNulls={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-[11px] text-muted">{rows.length} readings · gaps indicate missing values (not interpolated in the chart) · min {fmt(Math.min(...vals), 2)} · max {fmt(Math.max(...vals), 2)}</p>
    </div>
  )
}
