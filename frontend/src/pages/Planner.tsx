import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Page, type Schedule, type Technician, type WorkOrder } from '../api'
import { useAuth } from '../auth'
import { DecisionForm } from '../decide'
import { Gantt } from '../gantt'
import { Button, Empty, ErrorState, Field, Loading, PageHeader, Panel, PriorityTag, Stat, Table, Tag, fmt, fmtTime, inputCls } from '../ui'

export default function Planner() {
  const { can } = useAuth()
  const qc = useQueryClient()
  const wos = useQuery({ queryKey: ['work-orders'], queryFn: () => api.get<Page<WorkOrder>>('/work-orders?limit=200') })
  const techs = useQuery({ queryKey: ['technicians'], queryFn: () => api.get<{ items: Technician[] }>('/technicians') })
  const list = useQuery({ queryKey: ['schedules'], queryFn: () => api.get<Page<Schedule>>('/schedules?limit=10') })
  const [selected, setSelected] = useState<number | null>(null)
  const current = selected ?? list.data?.items[0]?.id ?? null
  const sched = useQuery({ queryKey: ['schedule', current], enabled: current != null, queryFn: () => api.get<Schedule & { problem?: never }>(`/schedules/${current}`) })
  const [solver, setSolver] = useState<'cp-sat' | 'greedy'>('cp-sat')
  const [w, setW] = useState({ lateness_weight: 10, unscheduled_weight: 2000, completion_weight: 1 })
  const propose = useMutation({
    mutationFn: () => api.post<Schedule>('/schedules', { solver, ...w }),
    onSuccess: (s) => { setSelected(s.id); qc.invalidateQueries({ queryKey: ['schedules'] }) },
  })
  const toggleTech = useMutation({
    mutationFn: (t: Technician) => api.patch(`/technicians/${t.code}`, { available: !t.available, reason: t.available ? 'Marked unavailable from planner' : 'Marked available from planner' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['technicians'] }),
  })
  const open = wos.data?.items.filter((x) => ['open', 'scheduled', 'in_progress'].includes(x.status)) ?? []

  return (
    <>
      <PageHeader title="Maintenance planner"
        subtitle="Google OR-Tools CP-SAT schedules approved and pending work orders against technician skills and shifts, spare-part stock and arrivals, task precedence, aircraft access conflicts and approval lead time. Every plan is independently re-verified against the hard constraints before it is shown."
        actions={can('plan') && (
          <>
            <select aria-label="Solver" className={`${inputCls} w-auto`} value={solver} onChange={(e) => setSolver(e.target.value as 'cp-sat' | 'greedy')}>
              <option value="cp-sat">OR-Tools CP-SAT (optimiser)</option><option value="greedy">Rule-based baseline (EDD)</option>
            </select>
            <Button variant="primary" busy={propose.isPending} onClick={() => propose.mutate()}>Generate plan</Button>
          </>
        )} />
      {propose.isError && <div className="mb-4"><ErrorState error={propose.error} /></div>}

      {can('plan') && (
        <details className="mb-5 rounded-md border border-line bg-surface px-4 py-3 text-[13px]">
          <summary className="cursor-pointer text-muted hover:text-ink">Objective weights (prototype settings)</summary>
          <p className="mt-2 text-xs text-muted">Minimise Σ priority-weight × (lateness-weight × hours late + unscheduled-weight × [not scheduled] + completion-weight × finish hour). Priority weights P1–P4: 8, 4, 2, 1.</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            {(Object.keys(w) as (keyof typeof w)[]).map((k) => (
              <Field key={k} label={k.replace('_', ' ')}>
                <input type="number" min={0} className={inputCls} value={w[k]} onChange={(e) => setW({ ...w, [k]: Math.max(0, +e.target.value) })} />
              </Field>
            ))}
          </div>
        </details>
      )}

      <div className="space-y-5">
        <Panel title="Proposed schedule" meta={sched.data && <span className="num">#{sched.data.id} · {sched.data.solver} · {sched.data.solver_status} · input {sched.data.input_hash.slice(0, 10)}</span>}>
          {current == null ? <Empty>No plan yet. Generate one to see the timeline.</Empty> : sched.isPending ? <Loading /> : sched.isError ? <ErrorState error={sched.error} /> : (
            <ScheduleView s={sched.data} />
          )}
        </Panel>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <Panel title="Work orders" meta={`${open.length} open`}>
            {wos.isPending ? <Loading /> : wos.isError ? <ErrorState error={wos.error} /> : (
              <Table head={['Code', 'Aircraft', 'Task', 'Skill · hours', 'Priority', 'Due', 'Parts', 'Depends on', 'Status']}>
                {open.map((x) => (
                  <tr key={x.id}>
                    <td className="num text-muted">{x.code}</td><td className="num">{x.aircraft}</td>
                    <td className="min-w-48">{x.title}<div className="text-[11px] text-muted">source {x.source}</div></td>
                    <td className="whitespace-nowrap">{x.required_skill} · <span className="num">{x.duration_hours} h</span></td>
                    <td><PriorityTag p={x.priority} /></td><td className="whitespace-nowrap text-muted">{fmtTime(x.due_at)}</td>
                    <td className="num text-xs">{x.parts.map((p) => `${p.part_number}×${p.qty}`).join(', ') || '—'}</td>
                    <td className="num text-xs">{x.predecessors.join(', ') || '—'}</td>
                    <td className="space-y-1">
                      <Tag>{x.status}</Tag> <Tag tone={x.approval_state === 'approved' ? 'ok' : 'warn'}>{x.approval_state}</Tag>
                      {x.assigned_technician && <div className="num text-[11px] text-muted">{x.assigned_technician} · {fmtTime(x.planned_start)}</div>}
                      {x.approval_state === 'pending' && <div className="pt-1"><DecisionForm target="work_order" id={x.id} /></div>}
                    </td>
                  </tr>
                ))}
              </Table>
            )}
          </Panel>
          <Panel title="Technician availability">
            {techs.isPending ? <Loading /> : techs.isError ? <ErrorState error={techs.error} /> : (
              <ul className="space-y-3">
                {techs.data.items.map((t) => (
                  <li key={t.code} className="flex items-start justify-between gap-2 text-[13px]">
                    <div className="min-w-0">
                      <div><span className="num">{t.code}</span> <span className="text-muted">{t.name}</span></div>
                      <div className="text-[11px] text-muted">{t.skills.join(', ')} · {t.shift}</div>
                      {t.unavailable.map((u, i) => <div key={i} className="text-[11px] text-warn">{u.reason}: {fmtTime(u.start)} → {fmtTime(u.end)}</div>)}
                    </div>
                    {can('plan') ? (
                      <Button variant={t.available ? 'secondary' : 'danger'} busy={toggleTech.isPending && toggleTech.variables?.code === t.code} onClick={() => toggleTech.mutate(t)}
                        aria-pressed={!t.available}>{t.available ? 'Available' : 'Unavailable'}</Button>
                    ) : <Tag tone={t.available ? 'ok' : 'crit'}>{t.available ? 'available' : 'unavailable'}</Tag>}
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 text-[11px] text-muted">Availability changes apply to the next generated plan.</p>
          </Panel>
        </div>

        <Panel title="Plan history">
          {list.isPending ? <Loading /> : list.isError ? <ErrorState error={list.error} /> : list.data.items.length === 0 ? <Empty>No plans yet.</Empty> : (
            <Table head={['Plan', 'Created', 'Solver', 'Status', 'Scheduled', 'Unscheduled', 'Late', 'Objective', '']}>
              {list.data.items.map((s) => (
                <tr key={s.id}>
                  <td className="num">#{s.id}</td><td className="text-muted">{fmtTime(s.created_at)}</td><td>{s.solver}</td>
                  <td><Tag tone={s.status === 'approved' ? 'ok' : s.status === 'rejected' ? 'crit' : s.status === 'proposed' ? 'warn' : undefined}>{s.status}</Tag></td>
                  <td className="num">{s.kpis.scheduled}</td><td className="num">{s.kpis.unscheduled}</td><td className="num">{s.kpis.late_tasks}</td>
                  <td className="num">{fmt(s.objective)}</td>
                  <td><Button variant="ghost" onClick={() => setSelected(s.id)} aria-current={current === s.id}>View</Button></td>
                </tr>
              ))}
            </Table>
          )}
        </Panel>
      </div>
    </>
  )
}

function ScheduleView({ s }: { s: Schedule }) {
  const techs = s.technicians ?? [...new Set(s.assignments?.map((a) => a.technician))]
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
        <Stat label="Scheduled tasks" value={s.kpis.scheduled} />
        <Stat label="Unscheduled" value={s.kpis.unscheduled} tone={s.kpis.unscheduled ? 'crit' : 'ok'} />
        <Stat label="Late tasks" value={s.kpis.late_tasks} tone={s.kpis.late_tasks ? 'warn' : 'ok'} note={`${s.kpis.total_late_hours} h total`} />
        <Stat label="Makespan" value={s.kpis.makespan_h} unit="h" />
        <Stat label="Objective" value={fmt(s.objective)} note="lower is better" />
      </div>
      <Gantt assignments={s.assignments ?? []} techs={techs} blocked={s.blocked} horizonStart={s.horizon_start} />
      {(s.unscheduled?.length ?? 0) > 0 && (
        <div className="rounded border border-crit/40 bg-crit/5 p-3">
          <div className="text-[13px] font-medium text-crit">Infeasible within the planning horizon — actionable reasons</div>
          <ul className="mt-1 space-y-1 text-[13px]">
            {s.unscheduled!.map((u) => <li key={u.task}><span className="num">{u.task}</span> <span className="text-muted">— {u.reason}</span></li>)}
          </ul>
        </div>
      )}
      {s.status === 'proposed' && s.scenario_run_id == null && (
        <div className="max-w-xl">
          <div className="mb-1 text-xs text-muted">Officer review: approving assigns technicians and planned start times to these work orders.</div>
          <DecisionForm target="schedule" id={s.id} />
        </div>
      )}
      {s.status !== 'proposed' && <p className="text-xs text-muted">Plan status: {s.status}.</p>}
    </div>
  )
}
