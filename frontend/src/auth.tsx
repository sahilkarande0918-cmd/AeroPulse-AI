import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ApiError, api, setToken, setUnauthorizedHandler, type User } from './api'
import { Ctx } from './auth-context'
import { inputCls } from './format'
import { Button, Field } from './ui'


export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [checking, setChecking] = useState(true)
  const qc = useQueryClient()
  const logout = useCallback(() => { setToken(null); setUser(null); qc.clear() }, [qc])

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null))
    // Always ask: a stored token, or (OIDC mode) an identity injected by the organisation's SSO proxy.
    api.get<User>('/auth/me').then(setUser).catch(() => setToken(null)).finally(() => setChecking(false))
  }, [])

  if (checking) return null
  if (!user) return <Login onLogin={setUser} />
  return <Ctx.Provider value={{ user, can: (p) => user.permissions.includes(p), logout }}>{children}</Ctx.Provider>
}

function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const [username, setUsername] = useState('officer')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const r = await api.post<{ access_token: string; user: User }>('/auth/login', { username, password })
      setToken(r.access_token)
      onLogin(r.user)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="grid min-h-dvh place-items-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6">
          <div className="text-lg font-semibold text-ink">AeroPulse AI</div>
          <div className="text-[13px] text-muted">Predict early. Maintain smarter. Fly ready.</div>
        </div>
        <form onSubmit={submit} className="space-y-3 rounded-md border border-line bg-surface p-5" noValidate>
          <Field label="Username">
            <input className={inputCls} value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
          </Field>
          <Field label="Password">
            <input className={inputCls} type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                   autoComplete="current-password" required aria-invalid={!!error} />
          </Field>
          {error && <p role="alert" className="text-[13px] text-crit">{error}</p>}
          <Button type="submit" variant="primary" busy={busy} className="w-full" disabled={!username || !password}>Sign in</Button>
          <p className="text-[11px] leading-relaxed text-muted">
            Demo accounts: admin · officer · technician · analyst (password configured by your administrator).
            Prototype for SIH26249 — advisory output only, not an airworthiness or dispatch system.
          </p>
        </form>
      </div>
    </main>
  )
}
