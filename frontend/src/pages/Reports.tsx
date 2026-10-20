import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download, ShieldCheck } from 'lucide-react'
import { ApiError, api, download, type Page } from '../api'
import { useAuth } from '../auth'
import { Button, Empty, ErrorState, Loading, PageHeader, Panel, PriorityTag, Table, Tag, TrustBadge, fmt, fmtTime } from '../ui'

interface RecRow {
  recommendation_id: number; created_at: string; aircraft: string; engine: string; action: string; priority: number; status: string
  trust_state: 'VALID' | 'DEGRADED' | 'UNAVAILABLE'; rul: number | null; rul_lower: number | null; rul_upper: number | null
  model_version: string; data_source: string; scenario_run_id: number | ''; decided_by: string; decision: string; decision_reason: string; decided_at: string
}
interface AuditRow { id: number; created_at: string; actor: string; action: string; entity_type: string; entity_id: string; details: Record<string, unknown>; hash: string }

export default function Reports() {
  const { can } = useAuth()
  const recs = useQuery({ queryKey: ['report-recs'], queryFn: () => api.get<{ items: RecRow[] }>('/reports/recommendations') })
  const [offset, setOffset] = useState(0)
  const audit = useQuery({ queryKey: ['audit', offset], enabled: can('audit:read'), queryFn: () => api.get<Page<AuditRow>>(`/audit?limit=25&offset=${offset}`) })
  const [verify, setVerify] = useState<{ valid: boolean; events_checked: number; first_invalid_id: number | null; note: string } | null>(null)
  const [dlError, setDlError] = useState<string | null>(null)
  const exp = (name: string) => download(`/reports/${name}.csv`, `aeropulse_${name}.csv`).catch((e) => setDlError(e instanceof ApiError ? e.message : 'Export failed'))

  return (
    <>
      <PageHeader title="Reports & audit" subtitle="Recommendations with the model version and data source behind them, the human decisions taken, and the append-only audit trail."
        actions={<>
          <Button onClick={() => exp('recommendations')}><Download className="size-3.5" /> Recommendations CSV</Button>
          {can('audit:read') && <>
            <Button onClick={() => exp('decisions')}><Download className="size-3.5" /> Decisions CSV</Button>
            <Button onClick={() => exp('scenarios')}><Download className="size-3.5" /> Scenarios CSV</Button>
            <Button onClick={() => exp('audit')}><Download className="size-3.5" /> Audit CSV</Button>
          </>}
          <Button variant="ghost" onClick={() => window.print()}>Print / PDF</Button>
        </>} />
      {dlError && <p role="alert" className="mb-3 text-[13px] text-crit">{dlError}</p>}

      <div className="space-y-5">
        <Panel title="Maintenance recommendations and approval history">
          {recs.isPending ? <Loading /> : recs.isError ? <ErrorState error={recs.error} /> : recs.data.items.length === 0 ? <Empty>No recommendations.</Empty> : (
            <Table head={['Rec', 'Created', 'Aircraft · engine', 'Action', 'Trust', 'RUL [90% interval]', 'Status', 'Decision', 'Model · source']}>
              {[...recs.data.items].reverse().map((r) => (
                <tr key={r.recommendation_id}>
                  <td className="num text-muted">REC-{r.recommendation_id}{r.scenario_run_id !== '' && <div className="text-[11px]">scenario #{r.scenario_run_id}</div>}</td>
                  <td className="whitespace-nowrap text-muted">{fmtTime(r.created_at)}</td>
                  <td className="num whitespace-nowrap">{r.aircraft} · {r.engine}</td>
                  <td className="min-w-48"><PriorityTag p={r.priority} /> {r.action}</td>
                  <td><TrustBadge state={r.trust_state} /></td>
                  <td className="num whitespace-nowrap">{r.rul == null ? 'withheld' : `${fmt(r.rul)} [${fmt(r.rul_lower)}–${fmt(r.rul_upper)}]`}</td>
                  <td><Tag tone={r.status === 'approved' ? 'ok' : r.status === 'rejected' ? 'crit' : r.status === 'proposed' ? 'warn' : undefined}>{r.status}</Tag></td>
                  <td className="min-w-40 text-xs">{r.decision ? <><span className="text-ink">{r.decision}</span> by {r.decided_by}<div className="text-muted">“{r.decision_reason}”</div><div className="text-muted">{r.decided_at && fmtTime(r.decided_at.split('; ')[0])}</div></> : <span className="text-muted">awaiting review</span>}</td>
                  <td className="num text-[11px] text-muted">{r.model_version}<div>{r.data_source}</div></td>
                </tr>
              ))}
            </Table>
          )}
        </Panel>

        {can('audit:read') ? (
          <Panel title="Audit log" meta={<span className="flex items-center gap-2">append-only · SHA-256 hash-chained
            <Button variant="secondary" onClick={() => api.get<typeof verify>('/audit/verify').then(setVerify)}><ShieldCheck className="size-3.5" /> Verify chain</Button></span>}>
            {verify && (
              <div role="status" className={`mb-3 rounded border p-3 text-[13px] ${verify.valid ? 'border-ok/40 text-ok' : 'border-crit/40 text-crit'}`}>
                {verify.valid ? `Chain intact — ${verify.events_checked} events verified.` : `Chain broken at event #${verify.first_invalid_id} (after ${verify.events_checked} valid events).`}
                <div className="mt-1 text-xs text-muted">{verify.note}</div>
              </div>
            )}
            {audit.isPending ? <Loading /> : audit.isError ? <ErrorState error={audit.error} /> : (
              <>
                <Table head={['#', 'Time', 'Actor', 'Action', 'Entity', 'Details', 'Hash']} dense>
                  {audit.data.items.map((e) => (
                    <tr key={e.id}>
                      <td className="num text-muted">{e.id}</td><td className="whitespace-nowrap text-muted">{fmtTime(e.created_at)}</td>
                      <td>{e.actor}</td><td className="num text-tech">{e.action}</td><td className="num">{e.entity_type}:{e.entity_id}</td>
                      <td className="max-w-md break-words text-muted">{JSON.stringify(e.details).slice(0, 220)}</td>
                      <td className="num text-[11px] text-muted">{e.hash.slice(0, 10)}</td>
                    </tr>
                  ))}
                </Table>
                <div className="mt-3 flex items-center justify-between text-xs text-muted">
                  <span>{audit.data.total} events</span>
                  <span className="flex gap-2">
                    <Button variant="ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>Newer</Button>
                    <Button variant="ghost" disabled={offset + 25 >= audit.data.total} onClick={() => setOffset(offset + 25)}>Older</Button>
                  </span>
                </div>
              </>
            )}
          </Panel>
        ) : <Panel title="Audit log"><p className="text-[13px] text-muted">Your role does not include audit visibility.</p></Panel>}
      </div>
    </>
  )
}
