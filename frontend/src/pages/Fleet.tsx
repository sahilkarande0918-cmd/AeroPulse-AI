import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import { api, type AircraftRow, type Page } from '../api'
import { Empty, ErrorState, Field, Loading, MaintBadge, PageHeader, Panel, Table, TrustBadge, ago, fmt, inputCls } from '../ui'

export default function Fleet() {
  const [search, setSearch] = useState('')
  const [state, setState] = useState('')
  const [trust, setTrust] = useState('')
  const params = new URLSearchParams({ search, ...(state && { state }), ...(trust && { trust }) })
  const q = useQuery({ queryKey: ['aircraft', search, state, trust], queryFn: () => api.get<Page<AircraftRow>>(`/aircraft?${params}`) })

  return (
    <>
      <PageHeader title="Aircraft fleet" subtitle="Fictional aircraft identifiers (synthetic demo fleet). Each engine replays a NASA C-MAPSS FD001 hold-out trajectory never used to fit the model." />
      <Panel bodyClass="p-0">
        <div className="grid gap-3 border-b border-line p-4 sm:grid-cols-3">
          <Field label="Search tail or engine serial">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2 top-2 size-4 text-muted" aria-hidden />
              <input className={`${inputCls} pl-8`} value={search} onChange={(e) => setSearch(e.target.value)} placeholder="AP-104 or AP-ENG-08" />
            </div>
          </Field>
          <Field label="Maintenance state">
            <select className={inputCls} value={state} onChange={(e) => setState(e.target.value)}>
              <option value="">All states</option>
              <option value="action_required">Action required</option><option value="watch">Watch</option>
              <option value="in_maintenance">In maintenance</option><option value="routine">Routine</option>
            </select>
          </Field>
          <Field label="TrustTwin validity">
            <select className={inputCls} value={trust} onChange={(e) => setTrust(e.target.value)}>
              <option value="">Any</option><option>VALID</option><option>DEGRADED</option><option>UNAVAILABLE</option>
            </select>
          </Field>
        </div>
        <div className="p-4">
          {q.isPending ? <Loading /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : q.data.items.length === 0 ? <Empty>No aircraft match these filters.</Empty> : (
            <Table head={['Aircraft', 'Maintenance state', 'Engine', 'TrustTwin', 'RUL estimate (cycles)', '90% interval', 'Last data', 'Open tasks']}>
              {q.data.items.flatMap((a) => a.engines.map((e, i) => (
                <tr key={e.id} className={i === 0 ? '' : '!border-t-0'}>
                  <td>{i === 0 && <Link to={`/fleet/${a.id}`} className="num font-medium text-tech hover:underline">{a.tail}</Link>}</td>
                  <td>{i === 0 && <MaintBadge state={a.maintenance_state} />}</td>
                  <td className="num whitespace-nowrap text-muted">#{e.position} {e.serial}</td>
                  <td><TrustBadge state={e.prediction?.state} /></td>
                  <td className="num">{fmt(e.prediction?.rul)}</td>
                  <td className="num text-muted">{e.prediction?.rul_lower == null ? '—' : `${fmt(e.prediction.rul_lower)}–${fmt(e.prediction.rul_upper)}`}</td>
                  <td className="whitespace-nowrap text-muted">{i === 0 && ago(a.last_data_update)}</td>
                  <td className="num">{i === 0 && a.open_work_orders}</td>
                </tr>
              )))}
            </Table>
          )}
        </div>
      </Panel>
    </>
  )
}
