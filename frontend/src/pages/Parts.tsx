import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ApiError, api, type Part } from '../api'
import { useAuth } from '../auth-context'
import { fmtTime, inputCls } from '../format'
import { Button, ErrorState, Field, Loading, PageHeader, Panel, Stat, Table, Tag } from '../ui'

export default function Parts() {
  const { can } = useAuth()
  const q = useQuery({ queryKey: ['parts'], queryFn: () => api.get<{ items: Part[] }>('/parts') })
  const [editing, setEditing] = useState<string | null>(null)
  if (q.isPending) return <Loading />
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />
  const parts = q.data.items
  const shortages = parts.filter((p) => p.shortage)

  return (
    <>
      <PageHeader title="Spare parts" subtitle="Fictional part numbers. Reserved stock is derived from open, non-rejected work orders; changes here feed straight into the next maintenance plan and TrustTwin scenario." />
      <div className="mb-5 grid grid-cols-2 gap-4 rounded-md border border-line bg-surface p-4 sm:grid-cols-4">
        <Stat label="Part numbers" value={parts.length} />
        <Stat label="Shortages (reserved > on hand)" value={shortages.length} tone={shortages.length ? 'crit' : 'ok'} />
        <Stat label="Below reorder threshold" value={parts.filter((p) => p.below_reorder).length} tone="warn" />
        <Stat label="Replenishments due" value={parts.filter((p) => p.replenishment_eta).length} />
      </div>

      {shortages.length > 0 && (
        <div role="alert" className="mb-5 rounded-md border border-crit/40 bg-crit/5 p-4 text-[13px]">
          <div className="font-medium text-crit">Shortage alerts</div>
          <ul className="mt-1 space-y-1">
            {shortages.map((p) => (
              <li key={p.part_number}>
                <span className="num">{p.part_number}</span> <span className="text-muted">needs {p.reserved}, {p.on_hand} on hand
                {p.replenishment_eta ? `, ${p.replenishment_qty} due ${fmtTime(p.replenishment_eta)}` : ', no replenishment scheduled'} — affects </span>
                {p.affected_work_orders.map((w) => <span key={w.code} className="num">{w.code} ({w.aircraft}) </span>)}
                <Link to="/planner" className="text-tech hover:underline">open planner</Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      <Panel title="Inventory">
        <Table head={['Part number', 'Description', 'On hand', 'Reserved', 'Available', 'Reorder at', 'Replenishment', 'Lead time', 'Required by work orders', '']}>
          {parts.map((p) => (
            <tr key={p.part_number} className={p.shortage ? 'bg-crit/5' : ''}>
              <td className="num whitespace-nowrap">{p.part_number}</td>
              <td className="min-w-44">{p.name}</td>
              <td className="num">{p.on_hand}</td><td className="num">{p.reserved}</td>
              <td className="num">{p.shortage ? <span className="text-crit">{p.available}</span> : p.available}</td>
              <td className="num">{p.reorder_threshold} {p.below_reorder && <Tag tone="warn">low</Tag>}</td>
              <td className="whitespace-nowrap text-muted">{p.replenishment_eta ? <><span className="num">+{p.replenishment_qty}</span> {fmtTime(p.replenishment_eta)}</> : '—'}</td>
              <td className="num text-muted">{p.lead_time_days} d</td>
              <td className="text-xs">{p.affected_work_orders.map((w) => <div key={w.code}><span className="num">{w.code}</span> <span className="text-muted">{w.aircraft} ×{w.qty} · {w.approval_state}</span></div>)}</td>
              <td>{can('inventory:write') && <Button variant="ghost" onClick={() => setEditing(editing === p.part_number ? null : p.part_number)}>{editing === p.part_number ? 'Close' : 'Adjust'}</Button>}</td>
            </tr>
          ))}
        </Table>
        {editing && <EditPart part={parts.find((p) => p.part_number === editing)!} onDone={() => setEditing(null)} />}
      </Panel>
    </>
  )
}

function EditPart({ part, onDone }: { part: Part; onDone: () => void }) {
  const qc = useQueryClient()
  const [onHand, setOnHand] = useState(part.on_hand)
  const [eta, setEta] = useState(part.replenishment_eta ? part.replenishment_eta.slice(0, 16) : '')
  const [qty, setQty] = useState(part.replenishment_qty)
  const [reason, setReason] = useState('')
  const m = useMutation({
    mutationFn: () => api.patch<Part>(`/parts/${part.part_number}`, {
      on_hand: onHand, replenishment_qty: qty, reason,
      ...(eta ? { replenishment_eta: new Date(eta).toISOString() } : { clear_replenishment: true }),
    }),
    onSuccess: () => { qc.invalidateQueries(); onDone() },
  })
  const submit = (e: FormEvent) => { e.preventDefault(); m.mutate() }
  return (
    <form onSubmit={submit} className="mt-4 grid gap-3 rounded border border-line-strong bg-raised p-4 sm:grid-cols-2 lg:grid-cols-5">
      <div className="sm:col-span-2 lg:col-span-5 text-[13px] font-medium"><span className="num">{part.part_number}</span> — stock adjustment (audited)</div>
      <Field label="On hand"><input type="number" min={0} className={inputCls} value={onHand} onChange={(e) => setOnHand(Math.max(0, +e.target.value))} /></Field>
      <Field label="Replenishment qty"><input type="number" min={0} className={inputCls} value={qty} onChange={(e) => setQty(Math.max(0, +e.target.value))} /></Field>
      <Field label="Replenishment ETA (local)" hint="Empty = no replenishment scheduled"><input type="datetime-local" className={inputCls} value={eta} onChange={(e) => setEta(e.target.value)} /></Field>
      <Field label="Reason"><input className={inputCls} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. stock count correction" required minLength={3} /></Field>
      <div className="flex items-end gap-2">
        <Button type="submit" variant="primary" busy={m.isPending} disabled={reason.trim().length < 3}>Save</Button>
        <Button type="button" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
      {m.isError && <p role="alert" className="text-xs text-crit sm:col-span-2 lg:col-span-5">{m.error instanceof ApiError ? m.error.message : 'Update failed'}</p>}
    </form>
  )
}
