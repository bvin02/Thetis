import { useQuery } from '@tanstack/react-query'
import { keepPreviousData } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { getJSON } from '../api/client'
import type { DecisionView, Level } from '../api/types'
import { ActionRow } from '../components/inspector/ActionRows'
import { TopBar } from '../components/shell/TopBar'
import { EmptyState, ErrorState, LoadingState, Segmented } from '../components/ui'
import { LEVEL } from '../lib/levels'

type Filter = 'pending' | 'decided' | 'all'

interface Group {
  key: string
  kind: 'tank' | 'line'
  tank_id: string | null
  line_id: string | null
  title: string
  level: Level
  level_label: string | null
  subtitle: string
  items: DecisionView[]
}

interface DecisionsResponse {
  groups: Group[]
  counts: { pending: number; decided: number; all: number }
}

function GroupCard({ group }: { group: Group }) {
  const lv = LEVEL[group.level]
  const pendingNumbers = new Map<number, number>()
  let n = 0
  for (const item of group.items) {
    if (item.status === 'pending') {
      n += 1
      pendingNumbers.set(item.id, n)
    }
  }
  return (
    <section aria-label={group.title} className="rounded-card border border-line">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-divider px-4 py-3 text-[13px]">
        <span className="h-2 w-2 flex-none rounded-full" style={{ background: lv.color }} />
        {group.kind === 'tank' ? (
          <Link to={`/tanks/${group.tank_id}`} className="mono font-semibold no-underline hover:underline">{group.title}</Link>
        ) : (
          <span className="font-semibold">{group.title}</span>
        )}
        {group.level_label && <><span aria-hidden="true" className="text-faint">·</span><span className="font-medium" style={{ color: lv.text }}>{group.level_label}</span></>}
        {group.subtitle && (
          <span className="flex items-center gap-2 text-ink-2 max-[660px]:basis-full">
            <span aria-hidden="true" className="text-faint max-[660px]:hidden">·</span>
            {group.subtitle}
          </span>
        )}
      </div>
      <div className="flex flex-col px-4">
        {group.items.map((item, index) => (
          <ActionRow key={item.id} action={item} number={pendingNumbers.get(item.id) ?? index + 1} divider={index > 0} showContext />
        ))}
      </div>
    </section>
  )
}

const EMPTY_TEXT: Record<Filter, { title: string; body: string }> = {
  pending: { title: 'Nothing is waiting', body: 'New recommendations appear here when a saved check calls for them.' },
  decided: { title: 'Nothing decided yet', body: 'Approved and dismissed recommendations collect here.' },
  all: { title: 'No decisions yet', body: 'Recommendations appear here when a saved check calls for them.' },
}

export default function DecisionsPage() {
  const [filter, setFilter] = useState<Filter>('pending')
  const query = useQuery({
    queryKey: ['decisions', filter],
    queryFn: () => getJSON<DecisionsResponse>(`/api/decisions?status=${filter}`),
    placeholderData: keepPreviousData,
  })
  const data = query.data
  return (
    <>
      <TopBar crumbs={['Decisions']} />
      <div className="flex flex-col gap-5 px-7 pt-6 pb-7 max-[660px]:px-4">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <h1 className="flex-auto text-[28px] leading-[1.15] font-semibold tracking-[-0.025em]">Decisions</h1>
          <Segmented
            label="Show"
            value={filter}
            onChange={setFilter}
            options={[
              { value: 'pending', label: `Waiting (${data?.counts.pending ?? 0})` },
              { value: 'decided', label: 'Decided' },
              { value: 'all', label: 'All' },
            ]}
          />
        </div>
        <p className="m-0 max-w-[72ch] text-[13px] leading-normal text-ink-3">Thetis recommends. A person decides. Nothing here acts on equipment.</p>
        {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}
        {!data && query.isPending && <LoadingState />}
        {data && data.groups.length === 0 && (
          <div className="rounded-card border border-line"><EmptyState title={EMPTY_TEXT[filter].title}>{EMPTY_TEXT[filter].body}</EmptyState></div>
        )}
        {data && data.groups.length > 0 && (
          <div className="flex max-w-[820px] flex-col gap-4">
            {data.groups.map((group) => <GroupCard key={group.key} group={group} />)}
          </div>
        )}
      </div>
    </>
  )
}
