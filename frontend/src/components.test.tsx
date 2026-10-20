import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { Prediction } from './api'
import { CopilotBox } from './copilot'
import { EngineSchematic } from './engine-schematic'

const pred = (over: Partial<Prediction>): Prediction => ({
  id: 1, engine_id: 1, created_at: '', cycle: 120, model_version: 'v', state: 'DEGRADED', rul: 40, rul_lower: 20, rul_upper: 60,
  summary: '', reasons: [], last_recorded_at: null, data_age_hours: 1, checks: [], evidence: [], imputed: {}, ...over,
})

const wrap = (ui: ReactNode) => render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>)

afterEach(() => vi.unstubAllGlobals())

describe('EngineSchematic', () => {
  it('outlines the module whose sensor TrustTwin flagged and sums contributions per module', () => {
    const { container } = render(<EngineSchematic p={pred({
      imputed: { s11: 47.2 },
      checks: [{ id: 'invalid', label: 'Invalid', status: 'fail', detail: 'outside physical plausibility bounds: s4' }],
      evidence: [{ feature: 's3_mean10', value: 1, contribution: -6, sensor: 'T30' }, { feature: 's9_mean10', value: 1, contribution: -2, sensor: 'Nc' }],
    })} />)
    const titles = [...container.querySelectorAll('title')].map((t) => t.textContent ?? '')
    expect(titles.find((t) => t.startsWith('HPC'))).toMatch(/contribution -8\.0 cycles · suspect s11/)
    expect(titles.find((t) => t.startsWith('LPT'))).toMatch(/suspect s4/)
    expect(titles.find((t) => t.startsWith('Fan'))).not.toMatch(/suspect/)
  })
})

describe('CopilotBox', () => {
  const status = (enabled: boolean) =>
    vi.fn().mockResolvedValue(new Response(JSON.stringify({ llm_enabled: enabled }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

  it('renders nothing when no LLM is configured', async () => {
    const f = status(false)
    vi.stubGlobal('fetch', f)
    const { container } = wrap(<CopilotBox predictionId={1} question="why?" />)
    await waitFor(() => expect(f).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('appears when the server reports an LLM', async () => {
    vi.stubGlobal('fetch', status(true))
    wrap(<CopilotBox predictionId={1} question="why?" />)
    expect(await screen.findByText(/Explain with AI/)).toBeInTheDocument()
  })
})
