import { useState, type FormEvent } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { ApiError, api } from './api'
import { inputCls } from './format'
import { Button } from './ui'

/** Optional LLM explainer. Renders nothing unless the server has an LLM configured. */
export function CopilotBox({ predictionId, scenarioRunId, question }: { predictionId?: number; scenarioRunId?: number; question: string }) {
  const status = useQuery({ queryKey: ['status'], queryFn: () => api.get<{ llm_enabled: boolean }>('/system/status'), staleTime: 300_000 })
  const [q, setQ] = useState(question)
  const m = useMutation({
    mutationFn: () => api.post<{ answer: string; disclaimer: string }>('/copilot/explain',
      { question: q, prediction_id: predictionId, scenario_run_id: scenarioRunId }),
  })
  if (!status.data?.llm_enabled) return null
  const submit = (e: FormEvent) => { e.preventDefault(); m.mutate() }
  return (
    <form onSubmit={submit} className="space-y-2 rounded border border-line-strong p-3">
      <div className="flex items-center gap-1.5 text-xs text-muted"><Sparkles className="size-3.5" /> Explain with AI (rephrases stored results only)</div>
      <div className="flex gap-2">
        <input className={inputCls} value={q} onChange={(e) => setQ(e.target.value)} maxLength={500} aria-label="Question" />
        <Button type="submit" busy={m.isPending} disabled={q.trim().length < 3}>Ask</Button>
      </div>
      {m.data && <div className="text-[13px] text-ink">{m.data.answer}<p className="mt-1 text-[11px] text-muted">{m.data.disclaimer}</p></div>}
      {m.isError && <p role="alert" className="text-xs text-crit">{m.error instanceof ApiError ? m.error.message : 'Copilot failed'}</p>}
    </form>
  )
}
