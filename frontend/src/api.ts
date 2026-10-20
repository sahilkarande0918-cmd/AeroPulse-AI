// Thin typed client for the AeroPulse API. Errors surface the backend's {error:{code,message}} schema.

export class ApiError extends Error {
  status: number
  code: string
  details: unknown
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

const TOKEN_KEY = 'aeropulse.token'
let token: string | null = null
try { token = sessionStorage.getItem(TOKEN_KEY) } catch { /* storage unavailable */ }
let onUnauthorized: () => void = () => {}

export function setToken(t: string | null) {
  token = t
  try { if (t) sessionStorage.setItem(TOKEN_KEY, t); else sessionStorage.removeItem(TOKEN_KEY) } catch { /* ignore */ }
}
export const hasToken = () => !!token
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn }

async function request<T>(method: string, path: string, body?: unknown, raw = false): Promise<T> {
  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`
  let payload: BodyInit | undefined
  if (body instanceof FormData) payload = body
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }
  let res: Response
  try {
    res = await fetch(`/api${path}`, { method, headers, body: payload })
  } catch {
    throw new ApiError(0, 'network_error', 'Cannot reach the AeroPulse API. Check that the backend is running.')
  }
  if (!res.ok) {
    let code = 'error', message = `Request failed (${res.status})`, details: unknown
    try {
      const j = await res.json()
      code = j?.error?.code ?? code
      message = j?.error?.message ?? message
      details = j?.error?.details
    } catch { /* non-JSON error body */ }
    if (res.status === 401 && path !== '/auth/login') { setToken(null); onUnauthorized() }
    throw new ApiError(res.status, code, message, details)
  }
  if (raw) return (await res.blob()) as T
  return (await res.json()) as T
}

export const api = {
  get: <T>(p: string) => request<T>('GET', p),
  post: <T>(p: string, b?: unknown) => request<T>('POST', p, b ?? {}),
  patch: <T>(p: string, b: unknown) => request<T>('PATCH', p, b),
  put: <T>(p: string, b: unknown) => request<T>('PUT', p, b),
  blob: (p: string) => request<Blob>('GET', p, undefined, true),
}

export async function download(path: string, filename: string) {
  const blob = await api.blob(path)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// ---------------------------------------------------------------- types (mirror backend responses)
export type TrustState = 'VALID' | 'DEGRADED' | 'UNAVAILABLE'
export type MaintState = 'routine' | 'watch' | 'action_required' | 'in_maintenance'

export interface Check { id: string; label: string; status: 'pass' | 'warn' | 'fail' | 'skipped'; detail: string }
export interface Evidence { feature: string; value: number; contribution: number; sensor: string }
export interface Prediction {
  id: number; engine_id: number; created_at: string; cycle: number; model_version: string; state: TrustState
  rul: number | null; rul_lower: number | null; rul_upper: number | null; summary: string; reasons: string[]
  last_recorded_at: string | null; data_age_hours: number | null
  checks?: Check[]; evidence?: Evidence[]; imputed?: Record<string, number>; n_cycles?: number
}
export interface EngineRow { id: number; serial: string; position: number; source: string; prediction: Prediction | null }
export interface AircraftRow {
  id: number; tail: string; type_name: string; base: string; maintenance_state: MaintState
  last_data_update: string | null; open_work_orders: number; engines: EngineRow[]
}
export interface WorkOrder {
  id: number; code: string; aircraft_id: number; aircraft: string; engine_id: number | null; title: string; task_type: string
  required_skill: string; duration_hours: number; priority: number; due_at: string; status: string; approval_state: string
  predecessors: string[]; parts: { part_number: string; qty: number }[]; planned_start: string | null
  assigned_technician: string | null; source: string; external_id: string | null
}
export interface Recommendation {
  id: number; prediction_id: number; aircraft_id: number; engine_id: number; action: string; priority: number
  rationale: string; status: string; created_at: string; work_order_id?: number | null; scenario_run_id?: number | null
}
export interface Assignment {
  task: string; technician: string; start: number; end: number; aircraft: string; title: string; priority: number
  due: number; late_hours: number; explanation: string
}
export interface PlanResult {
  solver: string; status: string; objective: number; assignments: Assignment[]; unscheduled: { task: string; reason: string }[]
  kpis: { scheduled: number; unscheduled: number; late_tasks: number; total_late_hours: number; makespan_h: number }
  problem?: { horizon: number; techs: { id: string; skills: string[]; blocked: [number, number][] }[] }
}
export interface Schedule {
  id: number; created_at: string; solver: string; status: string; horizon_start: string; input_hash: string
  scenario_run_id: number | null; kpis: PlanResult['kpis']; objective: number; solver_status: string
  assignments?: Assignment[]; unscheduled?: PlanResult['unscheduled']; technicians?: string[]; blocked?: Record<string, [number, number][]>
}
export interface Part {
  part_number: string; name: string; unit: string; on_hand: number; reserved: number; available: number
  reorder_threshold: number; replenishment_qty: number; replenishment_eta: string | null; lead_time_days: number
  shortage: boolean; below_reorder: boolean
  affected_work_orders: { code: string; aircraft: string; title: string; qty: number; approval_state: string }[]
}
export interface Technician { code: string; name: string; skills: string[]; shift: string; available: boolean; unavailable: { start: string; end: string; reason: string }[] }
export interface Decision { id: number; target_type: string; target_id: number; decision: string; reason: string; user: string; role: string; created_at: string }
export interface User { username: string; full_name: string; role: string; permissions: string[] }
export interface Page<T> { items: T[]; total: number; limit: number; offset: number }
