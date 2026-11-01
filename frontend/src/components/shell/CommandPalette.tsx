import { CornerDownLeft, FlaskConical, LayoutGrid, Search } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useFloor } from '../../api/hooks'
import type { TankSummary } from '../../api/types'
import { LevelSwatch } from '../ui'

interface Item {
  id: string
  group: 'Tanks' | 'New check' | 'Pages'
  label: ReactNode
  hint?: string
  search: string
  to: string
}

const PAGES: { label: string; to: string; words?: string }[] = [
  { label: 'Floor', to: '/', words: 'home plan overview' },
  { label: 'Advisor', to: '/advisor', words: 'risks crash yield suggestions ask claude brief forecast' },
  { label: 'Tanks', to: '/tanks' },
  { label: 'Checks', to: '/checks', words: 'history samples' },
  { label: 'Decisions', to: '/decisions', words: 'actions recommended approve' },
  { label: 'Photo library', to: '/photos', words: 'images pictures' },
]

function tankWords(tank: TankSummary) {
  return `${tank.id} ${tank.id.replace('-', '')} ${tank.batch_code ?? ''} ${tank.room_name} ${tank.line_name ?? ''} ${tank.level_label} ${tank.chip} ${tank.stage ?? ''}`.toLowerCase()
}

/** ⌘K: jump to a tank, start a check, or open a page. Everything it searches is already on the Floor. */
export function CommandPalette({ onClose }: { onClose: () => void }) {
  const { data } = useFloor()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [cursor, setCursor] = useState(0)
  const input = useRef<HTMLInputElement | null>(null)
  const list = useRef<HTMLDivElement | null>(null)

  useEffect(() => { input.current?.focus() }, [])

  const items = useMemo(() => {
    const q = query.trim().toLowerCase()
    const all: Item[] = []
    for (const tank of data?.tanks ?? []) {
      all.push({
        id: `tank-${tank.id}`, group: 'Tanks', search: tankWords(tank), to: `/tanks/${tank.id}`, hint: tank.age_text,
        label: (
          <span className="flex min-w-0 items-center gap-2">
            <LevelSwatch level={tank.level} size={8} />
            <span className="mono font-semibold">{tank.id}</span>
            <span className="truncate text-ink-3">{tank.level_label}{tank.chip ? ` · ${tank.chip}` : ''}</span>
          </span>
        ),
      })
    }
    // Starting a check only appears once someone is typing: the empty list stays short
    if (q) {
      for (const tank of data?.tanks ?? []) {
        if (tank.level === 'empty') continue
        all.push({
          id: `check-${tank.id}`, group: 'New check', search: `new check sample photo ${tankWords(tank)}`, to: `/checks/new?tank=${tank.id}`,
          label: (
            <span className="flex items-center gap-2">
              <FlaskConical size={14} strokeWidth={1.75} className="text-ink-4" aria-hidden="true" />
              New check for <span className="mono font-semibold">{tank.id}</span>
            </span>
          ),
        })
      }
    }
    for (const page of PAGES) {
      all.push({
        id: `page-${page.to}`, group: 'Pages', search: `${page.label} ${page.words ?? ''}`.toLowerCase(), to: page.to,
        label: (
          <span className="flex items-center gap-2">
            <LayoutGrid size={14} strokeWidth={1.75} className="text-ink-4" aria-hidden="true" />
            {page.label}
          </span>
        ),
      })
    }
    if (!q) return all
    const words = q.split(/\s+/)
    return all.filter((item) => words.every((word) => item.search.includes(word))).slice(0, 12)
  }, [data, query])

  const safeCursor = Math.min(cursor, Math.max(items.length - 1, 0))
  const go = (item: Item | undefined) => {
    if (!item) return
    onClose()
    navigate(item.to)
  }
  const onKey = (event: React.KeyboardEvent) => {
    if (event.key === 'ArrowDown' && items.length > 0) { event.preventDefault(); setCursor((safeCursor + 1) % items.length) }
    if (event.key === 'ArrowUp' && items.length > 0) { event.preventDefault(); setCursor((safeCursor - 1 + items.length) % items.length) }
    if (event.key === 'Enter') { event.preventDefault(); go(items[safeCursor]) }
    if (event.key === 'Escape') { event.preventDefault(); onClose() }
  }

  useEffect(() => {
    list.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [safeCursor])

  const activeId = items[safeCursor] ? `palette-${items[safeCursor].id}` : undefined
  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-[rgba(15,26,32,0.28)] px-4 pt-[12vh]" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <div role="dialog" aria-modal="true" aria-label="Search tanks and pages" className="appear flex max-h-[70vh] w-[540px] max-w-full flex-col overflow-hidden rounded-panel border border-line bg-white shadow-pop">
        <div className="flex items-center gap-2.5 border-b border-divider px-4">
          <Search size={15} strokeWidth={1.75} className="flex-none text-ink-4" aria-hidden="true" />
          <input
            ref={input}
            value={query}
            onChange={(event) => { setQuery(event.target.value); setCursor(0) }}
            onKeyDown={onKey}
            role="combobox"
            aria-expanded="true"
            aria-controls="palette-list"
            aria-activedescendant={activeId}
            aria-label="Search tanks and pages"
            placeholder="Search tanks, batches and pages"
            className="h-12 min-w-0 flex-1 border-0 bg-transparent text-sm outline-none placeholder:text-faint focus-visible:outline-none"
          />
          <span className="mono flex-none text-[11px] text-ink-4">esc</span>
        </div>
        <div ref={list} id="palette-list" role="listbox" aria-label="Results" className="flex-1 overflow-y-auto p-1.5">
          {items.length === 0 && <div className="px-2.5 py-6 text-center text-[13px] text-ink-3">Nothing matches "{query}".</div>}
          {items.map((item, index) => {
            const firstOfGroup = index === 0 || items[index - 1].group !== item.group
            const active = index === safeCursor
            return (
              <div key={item.id}>
                {firstOfGroup && <div className="px-2.5 pt-2 pb-1 text-xs font-medium text-ink-4">{item.group}</div>}
                <div
                  id={`palette-${item.id}`}
                  role="option"
                  aria-selected={active}
                  className="flex min-h-9 cursor-pointer items-center justify-between gap-3 rounded-small px-2.5 py-1.5 text-[13px] max-[660px]:min-h-11"
                  style={{ background: active ? '#F1F4F6' : 'transparent' }}
                  onMouseMove={() => { if (!active) setCursor(index) }}
                  onClick={() => go(item)}
                >
                  {item.label}
                  {active
                    ? <CornerDownLeft size={13} strokeWidth={1.75} className="flex-none text-ink-4" aria-hidden="true" />
                    : item.hint && <span className="flex-none truncate text-xs text-ink-4">{item.hint}</span>}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
