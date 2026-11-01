import { Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useFloor } from '../../api/hooks'

function useNow(intervalMs = 20_000) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), intervalMs)
    return () => window.clearInterval(id)
  }, [intervalMs])
  return now
}

function clockText(d: Date) {
  const day = d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
  const time = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  return `${day} · ${time}`
}

export function TopBar({ crumbs, newCheckHref = '/checks/new', hideNewCheck = false }: { crumbs: string[]; newCheckHref?: string; hideNewCheck?: boolean }) {
  const now = useNow()
  const { data } = useFloor()
  return (
    <header className="flex min-h-[52px] flex-wrap items-center gap-x-3 gap-y-2 border-b border-divider px-7 py-2 max-[660px]:px-4">
      <nav aria-label="Location" className="flex min-w-0 flex-[1_1_240px] flex-wrap items-center gap-x-2 gap-y-1 text-[13px]">
        <span className="whitespace-nowrap text-ink-4 max-[660px]:hidden">{data?.hatchery.name ?? 'Thetis'}</span>
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1
          return (
            <span key={c} className={`flex items-center gap-2 ${last ? '' : 'max-[660px]:hidden'}`}>
              <span aria-hidden="true" className="text-faint max-[660px]:hidden">/</span>
              <span className={`whitespace-nowrap ${last ? 'font-medium' : 'text-ink-4'}`}>{c}</span>
            </span>
          )
        })}
        {data?.is_example && <span className="tag ml-1">Example data</span>}
      </nav>
      <span className="tnum text-[13px] text-ink-4">{clockText(now)}</span>
      {!hideNewCheck && (
        <Link to={newCheckHref} className="solid no-underline">
          <Plus size={14} strokeWidth={2} aria-hidden="true" />
          New check
        </Link>
      )}
    </header>
  )
}
