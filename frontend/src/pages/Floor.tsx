import { X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useFloor, useTank } from '../api/hooks'
import { FloorPlanCard, type PlanView } from '../components/floor/FloorPlanCard'
import { HistoryCard } from '../components/floor/HistoryCard'
import { Metrics } from '../components/floor/Metrics'
import { UrgencyCard } from '../components/floor/UrgencyCard'
import { Inspector } from '../components/inspector/Inspector'
import { TopBar } from '../components/shell/TopBar'
import { EmptyState, ErrorState, LoadingState } from '../components/ui'
import { useMedia } from '../lib/useMedia'

function InspectorPanel({ tankId }: { tankId: string | null }) {
  const query = useTank(tankId)
  if (!tankId) return null
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />
  if (!query.data) return <LoadingState />
  return <Inspector tank={query.data} />
}

export default function FloorPage() {
  const floorQuery = useFloor()
  const [params, setParams] = useSearchParams()
  const [view, setView] = useState<PlanView>('plan')
  const [sheetWanted, setSheetOpen] = useState(false)
  const isPhone = useMedia('(max-width: 660px)')
  const sheetOpen = sheetWanted && isPhone

  const floor = floorQuery.data
  const roomId = params.get('room')
  const room = floor?.rooms.find((r) => r.id === roomId) ?? null
  const requested = params.get('tank')
  const selectedId = useMemo(() => {
    if (!floor) return null
    const inView = (id: string | null | undefined) =>
      floor.tanks.some((t) => t.id === id && (!room || t.room_id === room.id))
    if (inView(requested)) return requested
    if (!room) return floor.default_tank
    const worstHere = [...floor.act_now, ...floor.monitor].find((c) => inView(c.id))
    return worstHere?.id ?? floor.tanks.find((t) => t.room_id === room.id)?.id ?? null
  }, [floor, room, requested])

  const pick = (id: string) => {
    const next = new URLSearchParams(params)
    next.set('tank', id)
    setParams(next, { replace: true })
    if (isPhone) setSheetOpen(true)
  }

  useEffect(() => {
    if (!sheetOpen) return
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setSheetOpen(false) }
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [sheetOpen])

  const visibleIds = useMemo(() => {
    if (!floor) return new Set<string>()
    return new Set(floor.tanks.filter((t) => !room || t.room_id === room.id).map((t) => t.id))
  }, [floor, room])

  const selected = floor?.tanks.find((t) => t.id === selectedId)
  const newCheckHref = selected && selected.level !== 'empty' ? `/checks/new?tank=${selected.id}` : '/checks/new'

  if (floorQuery.isError) {
    return (
      <>
        <TopBar crumbs={['Floor']} />
        <ErrorState error={floorQuery.error} onRetry={() => floorQuery.refetch()} />
      </>
    )
  }
  if (!floor) {
    return (
      <>
        <TopBar crumbs={['Floor']} />
        <LoadingState />
      </>
    )
  }
  if (!floor.seeded || floor.tanks.length === 0) {
    return (
      <>
        <TopBar crumbs={['Floor']} />
        <EmptyState title="No hatchery set up yet">
          Stop the servers and run <span className="mono">npm run seed</span> to load the example hatchery.
        </EmptyState>
      </>
    )
  }

  const visibleTanks = floor.tanks.filter((t) => visibleIds.has(t.id))
  const actNow = floor.act_now.filter((c) => visibleIds.has(c.id))
  const monitor = floor.monitor.filter((c) => visibleIds.has(c.id))
  const clearRoom = () => {
    const next = new URLSearchParams(params)
    next.delete('room')
    setParams(next, { replace: true })
  }

  return (
    <>
      <TopBar crumbs={['Floor']} newCheckHref={newCheckHref} />

      <section aria-label="Summary" className="flex flex-col gap-3 px-7 pt-7 max-[660px]:px-4 max-[660px]:pt-5">
        <h1 className="text-[28px] leading-[1.15] font-semibold tracking-[-0.025em] [text-wrap:balance]">{floor.headline}</h1>
        <p className="m-0 max-w-[72ch] text-[15px] leading-[1.55] text-ink-2">{floor.summary}</p>
        {room && (
          <div className="flex flex-wrap items-center gap-2 text-[13px] text-ink-3">
            <span>Showing {room.name}</span>
            <button type="button" className="ghost !h-7 !px-2 !text-xs" onClick={clearRoom}>
              <X size={12} strokeWidth={2} aria-hidden="true" />
              Show all rooms
            </button>
          </div>
        )}
        <UrgencyCard
          actNow={actNow} actLabel={room ? `${actNow.length} in this room` : floor.act_label}
          monitor={monitor} monitorLabel={room ? `${monitor.length} on watch here` : floor.monitor_label}
          selected={selectedId} onPick={pick}
        />
        <Metrics metrics={floor.metrics} />
      </section>

      <div className="flex flex-wrap items-start gap-5 px-7 pt-6 pb-7 max-[660px]:px-4">
        <div className="flex min-w-0 flex-[999_1_600px] flex-col gap-5 max-[660px]:flex-[1_1_100%]">
          <FloorPlanCard
            tanks={floor.tanks} visibleTanks={visibleTanks} lines={floor.lines} room={room}
            selectedId={selectedId} view={view} onViewChange={setView} onPick={pick}
          />
          <HistoryCard
            history={{ days: floor.history.days, rows: floor.history.rows.filter((r) => visibleIds.has(r.tank_id)) }}
            selectedId={selectedId} onPick={pick}
          />
        </div>

        {!sheetOpen && (
          <aside aria-label="Selected tank" className="flex min-w-0 flex-[1_1_378px] flex-col rounded-card border border-line min-[1276px]:max-w-[402px]">
            <InspectorPanel tankId={selectedId} />
          </aside>
        )}
      </div>

      {sheetOpen && (
        <div role="dialog" aria-modal="true" aria-label={`${selectedId} details`} className="fixed inset-0 z-50 flex flex-col overflow-y-auto bg-white">
          <div className="sticky top-0 z-10 flex h-12 flex-none items-center justify-between border-b border-divider bg-white px-4">
            <span className="text-[13px] font-medium">Tank details</span>
            <button type="button" className="ghost !h-11 !w-11 !border-0 !p-0" aria-label="Close" onClick={() => setSheetOpen(false)}>
              <X size={18} strokeWidth={1.75} />
            </button>
          </div>
          <InspectorPanel tankId={selectedId} />
        </div>
      )}
    </>
  )
}
