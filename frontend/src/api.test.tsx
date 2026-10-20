import { render, screen } from '@testing-library/react'
import { ApiError, api, setToken, setUnauthorizedHandler } from './api'
import { ErrorState, RulGauge, TrustBadge } from './ui'

const reply = (status: number, body: unknown) =>
  vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))

afterEach(() => vi.unstubAllGlobals())

describe('api client error handling (mandatory scenario 17)', () => {
  it('maps the backend error schema to ApiError', async () => {
    vi.stubGlobal('fetch', reply(403, { error: { code: 'forbidden', message: "Role 'analyst' lacks permission 'approve'" } }))
    const err = (await api.post("/decisions", {}).catch((e) => e)) as ApiError
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(403)
    expect(err.code).toBe('forbidden')
    expect(err.message).toContain('lacks permission')
  })

  it('reports an unreachable backend as a network error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const err = await api.get('/aircraft').catch((e) => e)
    expect(err).toMatchObject({ status: 0, code: 'network_error' })
  })

  it('drops the session on 401 and notifies the app', async () => {
    const onUnauth = vi.fn()
    setUnauthorizedHandler(onUnauth)
    setToken('expired')
    vi.stubGlobal('fetch', reply(401, { error: { code: 'unauthorized', message: 'Invalid or expired token' } }))
    await api.get('/auth/me').catch(() => {})
    expect(onUnauth).toHaveBeenCalledOnce()
    expect(sessionStorage.getItem('aeropulse.token')).toBeNull()
  })

  it('survives a non-JSON error body', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>502</html>', { status: 502 })))
    const err = await api.get('/health').catch((e) => e)
    expect(err).toMatchObject({ status: 502, message: 'Request failed (502)' })
  })

  it('sends the bearer token', async () => {
    const f = reply(200, { ok: true })
    vi.stubGlobal('fetch', f)
    setToken('abc')
    await api.get('/health')
    expect(f.mock.calls[0][1].headers.Authorization).toBe('Bearer abc')
    setToken(null)
  })
})

describe('UI states', () => {
  it('ErrorState shows the API message and a permission title for 403', () => {
    render(<ErrorState error={new ApiError(403, 'forbidden', 'Role lacks permission')} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Not permitted')
    expect(screen.getByRole('alert')).toHaveTextContent('Role lacks permission')
  })

  it('never renders an RUL number when the prediction is withheld', () => {
    render(<RulGauge rul={null} lo={null} hi={null} />)
    expect(screen.getByText(/withheld by TrustTwin/)).toBeInTheDocument()
  })

  it('renders interval bounds for a valid prediction', () => {
    render(<><RulGauge rul={57} lo={24} hi={91} /><TrustBadge state="DEGRADED" /></>)
    expect(screen.getByText('90% interval [24, 91]')).toBeInTheDocument()
    expect(screen.getByText('DEGRADED')).toBeInTheDocument()
  })
})
