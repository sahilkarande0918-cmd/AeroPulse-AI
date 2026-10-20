import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Upload } from 'lucide-react'
import { ApiError, api, download, type Page } from '../api'
import { useAuth } from '../auth-context'
import { fmtTime, inputCls } from '../format'
import { Button, Empty, ErrorState, Field, Loading, PageHeader, Panel, Table, Tag } from '../ui'

interface Status {
  app_env: string; mode: string; database_dialect: string; offline_capable: boolean; external_calls: string[]; llm_enabled: boolean
  data_sources: { name: string; type: string; kind: string; records?: number; batches?: number; last_import?: string | null }[]
  predictions_stored: number; scenario_runs: number
}
interface Batch {
  id: number; created_at: string; source_type: string; source_name: string; filename: string; mapping_version: string; content_hash: string
  accepted: number; updated: number; duplicates: number; conflicts: number; rejected: number; already_imported?: boolean
  report: { schema_errors: string[]; rejected_rows: { row: number; reason: string }[]; conflicts: { row: number; key: string; reason: string }[]; notes: string[] }
}

export default function Settings() {
  const { can, user } = useAuth()
  const status = useQuery({ queryKey: ['status'], queryFn: () => api.get<Status>('/system/status') })
  const health = useQuery({ queryKey: ['health'], queryFn: () => api.get<{ status: string; database: boolean; model_loaded: boolean; model_version: string }>('/health') })
  return (
    <>
      <PageHeader title="Settings & data connections" subtitle="Deployment mode, data sources, validated CSV/JSON import, model and trust thresholds, roles and system health." />
      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="System">
          {status.isPending ? <Loading /> : status.isError ? <ErrorState error={status.error} /> : (
            <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-2 text-[13px]">
              <dt className="text-muted">Mode</dt><dd><Tag tone={status.data.mode === 'demo' ? 'warn' : 'ok'}>{status.data.mode}</Tag> <span className="text-muted">APP_ENV={status.data.app_env}</span></dd>
              <dt className="text-muted">Database</dt><dd className="num">{status.data.database_dialect} {health.data?.database ? <Tag tone="ok">connected</Tag> : <Tag tone="crit">down</Tag>}</dd>
              <dt className="text-muted">Model</dt><dd className="num">{health.data?.model_version ?? '—'} {health.data?.model_loaded && <Tag tone="ok">loaded</Tag>}</dd>
              <dt className="text-muted">Offline operation</dt><dd>{status.data.offline_capable ? 'Core platform runs with no internet access' : '—'}</dd>
              <dt className="text-muted">External calls</dt><dd>{status.data.external_calls.length ? status.data.external_calls.join(', ') : 'None (LLM copilot disabled)'}</dd>
              <dt className="text-muted">Stored</dt><dd className="num">{status.data.predictions_stored} predictions · {status.data.scenario_runs} scenario runs</dd>
              <dt className="text-muted">Signed in as</dt><dd>{user?.username} · {user?.role} · {user?.permissions.join(', ')}</dd>
            </dl>
          )}
        </Panel>
        <Panel title="Configured data sources">
          {status.data && (
            <Table head={['Source', 'Type', 'Kind', 'Records / batches']} dense>
              {status.data.data_sources.map((d) => (
                <tr key={d.name + d.type}><td>{d.name}</td><td className="text-muted">{d.type}</td><td><Tag tone={d.kind === 'ingested' ? 'tech' : 'warn'}>{d.kind}</Tag></td>
                  <td className="num text-muted">{d.records ?? d.batches ?? '—'}{d.last_import && ` · ${fmtTime(d.last_import)}`}</td></tr>
              ))}
            </Table>
          )}
        </Panel>
        {can('ingest') ? <ImportPanel /> : <Panel title="Data import"><p className="text-[13px] text-muted">Only officers and administrators can import data.</p></Panel>}
        <BatchHistory />
        <Thresholds />
        {can('admin') && <Users />}
      </div>
    </>
  )
}

function ImportPanel() {
  const qc = useQueryClient()
  const samples = useQuery({ queryKey: ['samples'], queryFn: () => api.get<{ items: string[] }>('/ingestion/samples') })
  const [source, setSource] = useState('sensor')
  const [sourceName, setSourceName] = useState('EXT-CAMO')
  const [file, setFile] = useState<File | null>(null)
  const m = useMutation({
    mutationFn: () => { const fd = new FormData(); fd.append('file', file!); fd.append('source_name', sourceName); return api.post<Batch>(`/ingestion/${source}`, fd) },
    onSuccess: () => qc.invalidateQueries(),
  })
  const submit = (e: FormEvent) => { e.preventDefault(); if (file) m.mutate() }
  const b = m.data
  return (
    <Panel title="Import CSV / JSON" meta="mapping-v1 · schema, units, duplicates, conflicts validated">
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
        <Field label="Source type">
          <select className={inputCls} value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="sensor">Sensor time series</option><option value="maintenance">Technical maintenance records</option>
            <option value="parts">Spare-part inventory</option><option value="work_orders">Maintenance work orders</option>
          </select>
        </Field>
        <Field label="Source system identifier" hint="letters, digits, - and _">
          <input className={inputCls} value={sourceName} onChange={(e) => setSourceName(e.target.value)} pattern="[A-Za-z0-9_\-]+" maxLength={64} />
        </Field>
        <Field label="File (.csv or .json, ≤ 5 MB)">
          <input type="file" accept=".csv,.json" className={`${inputCls} file:mr-2 file:rounded file:border-0 file:bg-raised file:px-2 file:py-1 file:text-ink`} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </Field>
        <div className="flex items-end"><Button type="submit" variant="primary" busy={m.isPending} disabled={!file}><Upload className="size-3.5" /> Validate & import</Button></div>
      </form>
      {m.isError && <p role="alert" className="mt-2 text-[13px] text-crit">{m.error instanceof ApiError ? m.error.message : 'Import failed'}</p>}
      {b && (
        <div className="mt-4 rounded border border-line-strong bg-raised p-3 text-[13px]">
          <div className="flex flex-wrap gap-2">
            {b.already_imported && <Tag tone="warn">identical file already imported — no changes</Tag>}
            <Tag tone="ok">{b.accepted} accepted</Tag>{b.updated > 0 && <Tag tone="tech">{b.updated} updated</Tag>}
            <Tag>{b.duplicates} duplicates skipped</Tag><Tag tone={b.conflicts ? 'crit' : undefined}>{b.conflicts} conflicts (not merged)</Tag>
            <Tag tone={b.rejected ? 'warn' : undefined}>{b.rejected} rejected</Tag>
          </div>
          {b.report.schema_errors.map((e, i) => <p key={i} className="mt-2 text-crit">Schema error: {e}</p>)}
          {b.report.notes.map((n, i) => <p key={i} className="mt-1 text-xs text-muted">{n}</p>)}
          {[...b.report.rejected_rows.map((r) => ({ ...r, kind: 'rejected' })), ...b.report.conflicts.map((c) => ({ row: c.row, reason: `${c.key}: ${c.reason}`, kind: 'conflict' }))].length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs">
              {b.report.rejected_rows.map((r) => <li key={`r${r.row}`}><span className="num text-warn">row {r.row}</span> <span className="text-muted">{r.reason}</span></li>)}
              {b.report.conflicts.map((c) => <li key={`c${c.row}`}><span className="num text-crit">row {c.row}</span> <span className="text-muted">{c.key}: {c.reason}</span></li>)}
            </ul>
          )}
          <p className="num mt-2 text-[11px] text-muted">batch #{b.id} · {b.mapping_version} · sha256 {b.content_hash.slice(0, 16)}</p>
        </div>
      )}
      <div className="mt-4 border-t border-line pt-3">
        <div className="mb-1 text-xs text-muted">Sample files (contain deliberate duplicates, conflicts, bad units and unknown assets)</div>
        <div className="flex flex-wrap gap-2">
          {samples.data?.items.map((s) => <Button key={s} variant="ghost" onClick={() => download(`/ingestion/samples/${s}`, s)}><Download className="size-3.5" /> {s}</Button>)}
        </div>
      </div>
    </Panel>
  )
}

function BatchHistory() {
  const q = useQuery({ queryKey: ['batches'], queryFn: () => api.get<Page<Batch>>('/ingestion/batches?limit=10') })
  return (
    <Panel title="Ingestion log">
      {q.isPending ? <Loading /> : q.isError ? <ErrorState error={q.error} /> : q.data.items.length === 0 ? <Empty>No imports yet.</Empty> : (
        <Table head={['#', 'When', 'Source', 'File', 'Acc', 'Dup', 'Conf', 'Rej']} dense>
          {q.data.items.map((b) => (
            <tr key={b.id}><td className="num">{b.id}</td><td className="text-muted">{fmtTime(b.created_at)}</td><td>{b.source_type} · {b.source_name}</td>
              <td className="break-all">{b.filename}</td><td className="num">{b.accepted + b.updated}</td><td className="num">{b.duplicates}</td>
              <td className="num">{b.conflicts}</td><td className="num">{b.rejected}{b.report.schema_errors.length > 0 && <Tag tone="crit">schema</Tag>}</td></tr>
          ))}
        </Table>
      )}
    </Panel>
  )
}

function Thresholds() {
  const { can } = useAuth()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['thresholds'], queryFn: () => api.get<{ thresholds: Record<string, number>; defaults: Record<string, number>; note: string }>('/settings/thresholds') })
  const [draft, setDraft] = useState<Record<string, number> | null>(null)
  const [reason, setReason] = useState('')
  const save = useMutation({ mutationFn: () => api.put('/settings/thresholds', { thresholds: draft, reason }), onSuccess: () => { setDraft(null); setReason(''); qc.invalidateQueries() } })
  if (q.isPending) return <Panel title="TrustTwin thresholds"><Loading /></Panel>
  if (q.isError) return <Panel title="TrustTwin thresholds"><ErrorState error={q.error} /></Panel>
  const vals = draft ?? q.data.thresholds
  return (
    <Panel title="TrustTwin & recommendation thresholds" meta={<Tag tone="warn">prototype settings</Tag>}>
      <p className="mb-3 text-xs text-muted">{q.data.note} Real thresholds must come from approved maintenance authorities.</p>
      <div className="grid gap-3 sm:grid-cols-2">
        {Object.entries(vals).map(([k, v]) => (
          <Field key={k} label={k.replaceAll('_', ' ')} hint={v !== q.data.defaults[k] ? `default ${q.data.defaults[k]}` : undefined}>
            <input type="number" min={0} step="any" className={inputCls} value={v} disabled={!can('admin')} onChange={(e) => setDraft({ ...vals, [k]: +e.target.value })} />
          </Field>
        ))}
      </div>
      {can('admin') && draft && (
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <div className="min-w-48 flex-1"><Field label="Reason for change (audited)"><input className={inputCls} value={reason} onChange={(e) => setReason(e.target.value)} /></Field></div>
          <Button variant="primary" busy={save.isPending} disabled={reason.trim().length < 5} onClick={() => save.mutate()}>Save thresholds</Button>
          <Button variant="ghost" onClick={() => setDraft(null)}>Discard</Button>
        </div>
      )}
      {save.isError && <p role="alert" className="mt-2 text-xs text-crit">{(save.error as Error).message}</p>}
    </Panel>
  )
}

function Users() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['users'], queryFn: () => api.get<{ items: { username: string; full_name: string; role: string; active: boolean }[]; roles: string[] }>('/users') })
  const m = useMutation({ mutationFn: (v: { u: string; body: Record<string, unknown> }) => api.patch(`/users/${v.u}`, v.body), onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }) })
  return (
    <Panel title="Users & roles" meta="permissions enforced by the API">
      {q.isPending ? <Loading /> : q.isError ? <ErrorState error={q.error} /> : (
        <Table head={['User', 'Name', 'Role', 'Active']}>
          {q.data.items.map((u) => (
            <tr key={u.username}>
              <td className="num">{u.username}</td><td className="text-muted">{u.full_name}</td>
              <td><select aria-label={`Role for ${u.username}`} className={`${inputCls} w-auto`} value={u.role} onChange={(e) => m.mutate({ u: u.username, body: { role: e.target.value } })}>
                {q.data.roles.map((r) => <option key={r}>{r}</option>)}</select></td>
              <td><Button variant="ghost" onClick={() => m.mutate({ u: u.username, body: { active: !u.active } })}>{u.active ? 'Active' : 'Disabled'}</Button></td>
            </tr>
          ))}
        </Table>
      )}
      {m.isError && <p role="alert" className="mt-2 text-xs text-crit">{(m.error as Error).message}</p>}
      <p className="mt-3 text-[11px] text-muted">Production path: replace local login with the organisation's OIDC/SSO and map its groups to these four roles (see docs/security.md).</p>
    </Panel>
  )
}
