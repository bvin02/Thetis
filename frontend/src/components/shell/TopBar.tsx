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

export function TopBar({ crumbs, newCheckHref = '/checks/new' }: { crumbs: string[]; newCheckHref?: string }) {
  const now = useNow()
  const { data } = useFloor()
  return (
    <header className="flex min-h-[52px] flex-wrap items-center gap-x-3 gap-y-2 border-b border-divider px-7 py-2 max-[660px]:px-4">
      <nav aria-label="Location" className="flex flex-[1_1_240px] items-center gap-2 text-[13px]">
        <span className="text-ink-4 max-[480px]:hidden">{data?.hatchery.name ?? 'Thetis'}</span>
        {crumbs.map((c, i) => (
          <span key={c} className="flex items-center gap-2">
            <span aria-hidden="true" className="text-faint max-[480px]:first:hidden">/</span>
            <span className={i === crumbs.length - 1 ? 'font-medium' : 'text-ink-4'}>{c}</span>
          </span>
        ))}
        {data?.is_example && <span className="tag ml-1">Example data</span>}
      </nav>
      <span className="tnum text-[13px] text-ink-4">{clockText(now)}</span>
      <Link to={newCheckHref} className="solid no-underline">
        <Plus size={14} strokeWidth={2} aria-hidden="true" />
        New check
      </Link>
    </header>
  )
}
