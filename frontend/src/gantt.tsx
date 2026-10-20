import { useState } from 'react'
import type { Assignment } from './api'
import { cx } from './format'
import { PriorityTag } from './ui'

const PX = 7 // pixels per hour
const BAR: Record<number, string> = { 1: 'bg-crit/80', 2: 'bg-warn/80', 3: 'bg-tech/75', 4: 'bg-muted/60' }

/** Technician-row Gantt. Dark bands are off-shift/leave; red outline = finishes after due. */
export function Gantt({ assignments, techs, blocked, horizonStart, hours = 168 }: {
  assignments: Assignment[]; techs: string[]; blocked?: Record<string, [number, number][]>; horizonStart: string; hours?: number
}) {
  const [sel, setSel] = useState<Assignment | null>(null)
  const t0 = new Date(horizonStart)
  const days = Math.ceil(hours / 24)
  const label = (h: number) => new Date(t0.getTime() + h * 36e5).toLocaleString(undefined, { weekday: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  return (
    <div>
      <div className="overflow-x-auto rounded border border-line">
        <div style={{ width: 96 + hours * PX }} className="relative">
          <div className="flex border-b border-line text-[11px] text-muted">
            <div className="sticky left-0 z-10 w-24 shrink-0 bg-surface px-2 py-1">Technician</div>
            {Array.from({ length: days }, (_, d) => (
              <div key={d} style={{ width: 24 * PX }} className="shrink-0 border-l border-line px-1 py-1">
                {new Date(t0.getTime() + d * 864e5).toLocaleDateString(undefined, { weekday: 'short', day: '2-digit', month: 'short' })}
              </div>
            ))}
          </div>
          {techs.map((tech) => (
            <div key={tech} className="relative flex h-9 border-b border-line/60 last:border-0">
              <div className="num sticky left-0 z-10 flex w-24 shrink-0 items-center bg-surface px-2 text-xs text-ink">{tech}</div>
              <div className="relative flex-1">
                {(blocked?.[tech] ?? []).filter(([a]) => a < hours).map(([a, b], i) => (
                  <div key={i} aria-hidden className="absolute inset-y-0 bg-canvas/80"
                    style={{ left: a * PX, width: (Math.min(b, hours) - a) * PX }} />
                ))}
                {Array.from({ length: days }, (_, d) => <div key={d} aria-hidden className="absolute inset-y-0 border-l border-line/70" style={{ left: d * 24 * PX }} />)}
                {assignments.filter((a) => a.technician === tech && a.start < hours).map((a) => (
                  <button key={a.task} onClick={() => setSel(a)} title={`${a.task} · ${a.title} · ${a.aircraft}`}
                    className={cx('num absolute top-1.5 h-6 overflow-hidden truncate rounded-sm px-1 text-left text-[10px] font-medium text-on-accent transition-opacity hover:opacity-90',
                      BAR[a.priority] ?? 'bg-tech/70', a.late_hours > 0 && 'ring-2 ring-crit', sel?.task === a.task && 'outline outline-2 outline-ink')}
                    style={{ left: a.start * PX, width: Math.max(10, (Math.min(a.end, hours) - a.start) * PX) }}>
                    {a.task}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-muted">
        <span>Bars by priority:</span>{[1, 2, 3, 4].map((p) => <span key={p} className="flex items-center gap-1"><span className={cx('size-2.5 rounded-sm', BAR[p])} />P{p}</span>)}
        <span className="flex items-center gap-1"><span className="size-2.5 rounded-sm ring-2 ring-crit" />late vs due</span>
        <span>dark band = off-shift / leave · times local · horizon start {label(0)}</span>
      </div>
      {sel && (
        <div className="mt-3 rounded border border-line-strong bg-raised p-3 text-[13px]">
          <div className="flex flex-wrap items-center gap-2"><span className="num font-medium">{sel.task}</span><PriorityTag p={sel.priority} /><span>{sel.title}</span><span className="num text-muted">{sel.aircraft}</span></div>
          <div className="num mt-1 text-xs text-muted">{sel.technician} · {label(sel.start)} → {label(sel.end)} · due {label(sel.due)} · late {sel.late_hours} h</div>
          <div className="mt-1 text-xs text-ink">Why this slot: {sel.explanation}</div>
        </div>
      )}
    </div>
  )
}
