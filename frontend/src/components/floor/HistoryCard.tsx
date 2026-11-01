import type { Floor, HistoryCell, HistoryRow, Level } from '../../api/types'
import { LEGEND, LEVEL } from '../../lib/levels'
import { LevelSwatch } from '../ui'

const CELL_BG: Record<Level, string> = {
  critical: '#D93A2F', risk: '#E0702A', watch: '#C98A0B', ok: '#DCE3E7', empty: '#FFFFFF',
}

function Cell({ cell, tankId, tipClass, isToday }: { cell: HistoryCell; tankId: string; tipClass: string; isToday: boolean }) {
  const level = cell.level
  return (
    <span
      className="hc"
      aria-hidden="true"
      style={{
        background: level ? CELL_BG[level] : '#FFFFFF',
        border: level ? '0' : '1.5px dashed #C7CFD4',
        boxShadow: isToday ? '0 0 0 1.5px #FFFFFF, 0 0 0 3px #66737B' : 'none',
      }}
    >
      <span className={`tip ${tipClass} box-border flex w-[200px] flex-col gap-1 rounded-control border border-line bg-white px-2.5 py-2 shadow-pop`}>
        <span className="text-xs font-semibold text-ink"><span className="mono">{tankId}</span> · {cell.date_text}</span>
        <span className="flex items-center gap-1.5 text-xs font-medium" style={{ color: level ? LEVEL[level].text : '#66737B' }}>
          <LevelSwatch level={level ?? 'empty'} size={8} square />
          {cell.label}
        </span>
        <span className="text-xs text-ink-3">{cell.change}</span>
      </span>
    </span>
  )
}

function rowAria(row: HistoryRow): string {
  const runs: { label: string; from: string; to: string }[] = []
  for (const cell of row.cells) {
    const last = runs[runs.length - 1]
    if (last && last.label === cell.label) last.to = cell.date_text
    else runs.push({ label: cell.label, from: cell.date_text, to: cell.date_text })
  }
  const text = runs.map((run) => `${run.label.toLowerCase()} ${run.from}${run.to !== run.from ? ` to ${run.to}` : ''}`).join(', ')
  return `${row.tank_id}: ${text}`
}

export function HistoryCard({ history, selectedId, onPick }: {
  history: Pick<Floor['history'], 'days'> & { rows: HistoryRow[] }
  selectedId: string | null
  onPick: (id: string) => void
}) {
  return (
    <section aria-label="Last 14 days" className="rounded-card border border-line">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-divider px-4 py-3">
        <div className="flex flex-[1_1_260px] flex-col gap-0.5">
          <h2 className="text-sm font-semibold">Last 14 days</h2>
          <span className="text-xs text-ink-4">Each tank's status on each day, from its most recent check. Select a tank to inspect it.</span>
        </div>
        <div className="flex flex-wrap gap-x-3.5 gap-y-2 text-xs text-ink-3">
          {LEGEND.map((level) => (
            <span key={level} className="flex items-center gap-1.5">
              <LevelSwatch level={level} square />
              {LEVEL[level].label}
            </span>
          ))}
        </div>
      </div>
      <div className="px-4 pt-3 pb-4 max-[700px]:overflow-x-auto">
        <div className="flex min-w-[600px] flex-col gap-0.5">
          {history.rows.map((row, rowIndex) => {
            const isSelected = row.tank_id === selectedId
            return (
              <div
                key={row.tank_id}
                role="group"
                aria-label={rowAria(row)}
                onClick={() => onPick(row.tank_id)}
                className="-mx-1 flex cursor-pointer items-center gap-1 rounded-small px-1 py-0.5"
                style={{ background: isSelected ? '#F1F4F6' : 'transparent' }}
              >
                <button
                  type="button"
                  className="rowbtn flex h-5 w-16 flex-none items-center gap-1.5 rounded-[4px] border-0 bg-transparent px-1"
                  onClick={(event) => { event.stopPropagation(); onPick(row.tank_id) }}
                  aria-pressed={isSelected}
                >
                  <LevelSwatch level={row.level} size={6} />
                  <span className="mono text-xs" style={{ fontWeight: isSelected ? 600 : 500, color: isSelected ? '#0F1A20' : '#3E4B53' }}>{row.tank_id}</span>
                </button>
                {row.cells.map((cell, index) => {
                  const tipClass = `${rowIndex <= 3 ? 'below' : 'above'} ${index <= 2 ? 'l' : index >= 11 ? 'r' : 'c'}`
                  return <Cell key={cell.date} cell={cell} tankId={row.tank_id} tipClass={tipClass} isToday={index === row.cells.length - 1} />
                })}
              </div>
            )
          })}
          <div aria-hidden="true" className="flex gap-1 pt-1.5 pl-[68px]">
            {history.days.map((day) => (
              <span key={day.date} className="tnum flex flex-1 flex-col items-center gap-px">
                <span className="text-[11px]" style={{ color: day.is_today ? '#0F1A20' : '#5F6C74', fontWeight: day.is_today ? 600 : 400 }}>{day.num}</span>
                <span className="text-[10px]" style={{ color: day.is_today ? '#0F1A20' : '#66737B', fontWeight: day.is_today ? 600 : 400 }}>{day.sub}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
