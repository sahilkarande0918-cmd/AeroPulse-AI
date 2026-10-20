import { useState, type ComponentType } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Activity, BrainCircuit, CalendarRange, ChevronsLeft, ChevronsRight, FileText, Gauge, LogOut, Menu, Package, Plane,
  Settings as SettingsIcon, ShieldCheck, X,
} from 'lucide-react'
import { api } from './api'
import { useAuth } from './auth-context'
import { cx } from './format'
import Overview from './pages/Overview'
import Fleet from './pages/Fleet'
import AircraftDetail from './pages/AircraftDetail'
import Intelligence from './pages/Intelligence'
import Planner from './pages/Planner'
import Parts from './pages/Parts'
import TrustTwin from './pages/TrustTwin'
import Reports from './pages/Reports'
import Settings from './pages/Settings'

const NAV: [string, string, ComponentType<{ className?: string }>][] = [
  ['/', 'Command overview', Gauge],
  ['/fleet', 'Aircraft fleet', Plane],
  ['/trusttwin', 'TrustTwin', ShieldCheck],
  ['/planner', 'Maintenance planner', CalendarRange],
  ['/parts', 'Spare parts', Package],
  ['/intelligence', 'Predictive intelligence', BrainCircuit],
  ['/reports', 'Reports & audit', FileText],
  ['/settings', 'Settings & data', SettingsIcon],
]

export default function App() {
  const { user, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const health = useQuery({ queryKey: ['health'], queryFn: () => api.get<{ status: string; model_version: string }>('/health'), refetchInterval: 60_000 })

  const nav = (
    <nav aria-label="Main" className="flex flex-col gap-0.5 p-2">
      {NAV.map(([to, label, Icon]) => (
        <NavLink key={to} to={to} end={to === '/'} onClick={() => setMobileOpen(false)} title={collapsed ? label : undefined}
          className={({ isActive }) => cx('flex items-center gap-2.5 whitespace-nowrap rounded px-2.5 py-2 text-[13px] transition-colors duration-150',
            isActive ? 'bg-raised text-ink' : 'text-muted hover:bg-raised/60 hover:text-ink')}>
          <Icon className="size-4 shrink-0" />
          <span className={cx(collapsed && 'md:sr-only')}>{label}</span>
        </NavLink>
      ))}
    </nav>
  )

  return (
    <div className="flex min-h-dvh">
      <aside className={cx('sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-line bg-surface md:flex', collapsed ? 'w-14' : 'w-56')}>
        <div className="flex h-12 items-center gap-2 border-b border-line px-3">
          <Activity className="size-5 shrink-0 text-tech" aria-hidden />
          {!collapsed && <span className="text-sm font-semibold tracking-tight">AeroPulse AI</span>}
        </div>
        <div className="flex-1 overflow-y-auto">{nav}</div>
        <button onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
          className="flex items-center gap-2 border-t border-line px-4 py-2.5 text-xs text-muted hover:text-ink">
          {collapsed ? <ChevronsRight className="size-4" /> : <><ChevronsLeft className="size-4" /> Collapse</>}
        </button>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button aria-label="Close navigation" className="absolute inset-0 bg-canvas/70" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 border-r border-line bg-surface">
            <div className="flex h-12 items-center justify-between border-b border-line px-3">
              <span className="text-sm font-semibold">AeroPulse AI</span>
              <button aria-label="Close navigation" onClick={() => setMobileOpen(false)} className="p-1 text-muted hover:text-ink"><X className="size-4" /></button>
            </div>
            {nav}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="app-topbar sticky top-0 z-30 flex h-12 items-center gap-3 border-b border-line bg-canvas/95 px-4">
          <button className="p-1 text-muted hover:text-ink md:hidden" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu className="size-5" /></button>
          <span className="hidden truncate text-xs text-muted sm:inline">Advisory decision support · synthetic demo fleet · NASA C-MAPSS FD001 replay</span>
          <span className="ml-auto flex items-center gap-3 text-xs">
            <span className="hidden items-center gap-1.5 text-muted lg:flex" title="API health">
              <span className={cx('size-2 rounded-full', health.data?.status === 'ok' ? 'bg-ok' : health.isError ? 'bg-crit' : 'bg-warn')} />
              <span className="num">{health.data?.model_version ?? 'API…'}</span>
            </span>
            <span className="truncate text-ink">{user?.full_name}</span>
            <span className="rounded border border-line-strong px-1.5 py-px text-muted">{user?.role}</span>
            <button onClick={logout} aria-label="Sign out" className="p-1 text-muted hover:text-ink"><LogOut className="size-4" /></button>
          </span>
        </header>
        <main className="mx-auto w-full max-w-[1500px] min-w-0 flex-1 px-4 py-5 md:px-6">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/fleet" element={<Fleet />} />
            <Route path="/fleet/:id" element={<AircraftDetail />} />
            <Route path="/trusttwin" element={<TrustTwin />} />
            <Route path="/planner" element={<Planner />} />
            <Route path="/parts" element={<Parts />} />
            <Route path="/intelligence" element={<Intelligence />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        <footer className="border-t border-line px-6 py-3 text-[11px] text-muted">
          AeroPulse AI prototype (SIH26249). Outputs are advisory maintenance intelligence and never constitute airworthiness, dispatch or flight authorisation.
          Not validated on military aircraft.
        </footer>
      </div>
    </div>
  )
}
