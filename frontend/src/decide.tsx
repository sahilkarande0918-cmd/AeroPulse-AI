import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ApiError, api, type Decision } from './api'
import { useAuth } from './auth-context'
import { inputCls } from './format'
import { Button } from './ui'

type Target = 'recommendation' | 'schedule' | 'work_order'
type Kind = 'approve' | 'reject' | 'request_inspection' | 'request_data'

const LABEL: Record<Kind, string> = { approve: 'Approve', reject: 'Reject', request_inspection: 'Request inspection', request_data: 'Request more data' }

/** Human decision control. The backend enforces the role check; the UI only hides it for convenience. */
export function DecisionForm({ target, id, options = ['approve', 'reject'], onDone }: {
  target: Target; id: number; options?: Kind[]; onDone?: (d: Decision & { effect: Record<string, unknown> }) => void
}) {
  const { can } = useAuth()
  const qc = useQueryClient()
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const m = useMutation({
    mutationFn: (decision: Kind) => api.post<Decision & { effect: Record<string, unknown> }>('/decisions', { target_type: target, target_id: id, decision, reason }),
    onSuccess: (d) => { setReason(''); setError(null); qc.invalidateQueries(); onDone?.(d) },
    onError: (e) => setError(e instanceof ApiError ? e.message : 'Decision failed'),
  })
  if (!can('approve')) return <p className="text-xs text-muted">Your role can view but not decide. Maintenance officers or administrators approve.</p>
  return (
    <div className="space-y-2">
      <textarea className={`${inputCls} min-h-14`} placeholder="Reason / override justification (required to reject or request)"
        value={reason} onChange={(e) => setReason(e.target.value)} maxLength={2000} aria-label="Decision reason" aria-invalid={!!error} />
      <div className="flex flex-wrap gap-2">
        {options.map((o) => (
          <Button key={o} variant={o === 'approve' ? 'primary' : o === 'reject' ? 'danger' : 'secondary'}
            busy={m.isPending && m.variables === o} disabled={m.isPending} onClick={() => m.mutate(o)}>{LABEL[o]}</Button>
        ))}
      </div>
      {error && <p role="alert" className="text-xs text-crit">{error}</p>}
    </div>
  )
}
