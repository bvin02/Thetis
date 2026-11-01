import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useFloor } from '../api/hooks'
import { TopBar } from '../components/shell/TopBar'
import { StartBatchDialog } from '../components/tank/BatchDialogs'
import { ErrorState, LevelSwatch, LoadingState } from '../components/ui'
import { LEVEL } from '../lib/levels'

const COLUMNS = '132px minmax(0, 1.2fr) minmax(0, 1fr) 84px 80px minmax(0, 1.1fr)'

export function RoomChips({ rooms, value, onChange }: { rooms: { id: string; name: string }[]; value: string | null; onChange: (id: string | null) => void }) {
  const options = [{ id: null as string | null, name: 'All rooms' }, ...rooms]
  return (
    <div role="group" aria-label="Filter by room" className="flex flex-wrap gap-1.5">
      {options.map((room) => {
        const active = room.id === value
        return (
          <button
            key={room.id ?? 'all'}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(room.id)}
            className="chip h-8 rounded-control border px-3 text-[13px] max-[660px]:h-11"
            style={{ borderColor: active ? '#0F1A20' : '#E2E8EC', background: '#FFFFFF', boxShadow: active ? '0 0 0 0.5px #0F1A20' : 'none', fontWeight: active ? 500 : 400 }}
          >
            {room.name}
          </button>
        )
      })}
    </div>
  )
}

export default function TanksListPage() {
  const query = useFloor()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [startFor, setStartFor] = useState<string | null>(null)
  const room = params.get('room')

  if (query.isError) return <><TopBar crumbs={['Tanks']} /><ErrorState error={query.error} onRetry={() => query.refetch()} /></>
  if (!query.data) return <><TopBar crumbs={['Tanks']} /><LoadingState /></>
  const tanks = query.data.tanks.filter((t) => !room || t.room_id === room)

  return (
    <>
      <TopBar crumbs={['Tanks']} />
      <div className="flex flex-col gap-4 px-7 pt-6 pb-7 max-[660px]:px-4">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
          <h1 className="flex-auto text-[28px] leading-[1.15] font-semibold tracking-[-0.025em]">Tanks</h1>
          <RoomChips rooms={query.data.rooms} value={room} onChange={(id) => setParams(id ? { room: id } : {}, { replace: true })} />
        </div>
        <section aria-label="Tanks" className="rounded-card border border-line">
          <div className="overflow-x-auto">
            <div className="flex min-w-[740px] flex-col text-[13px]">
              <div aria-hidden="true" className="grid gap-3 border-b border-divider px-4 py-2.5 text-xs text-ink-4" style={{ gridTemplateColumns: COLUMNS }}>
                <span>Tank</span><span>Room</span><span>Age</span><span className="text-right">Live (est.)</span><span className="text-right">Survival</span><span>Last check</span>
              </div>
              {tanks.map((tank, index) => {
                const open = () => navigate(`/tanks/${tank.id}`)
                return (
                  <div
                    key={tank.id}
                    role="link"
                    tabIndex={0}
                    aria-label={`${tank.id}, ${tank.level_label}, ${tank.room_name}, ${tank.age_text}, survival ${tank.survival_text}, last check ${tank.last_check_text}`}
                    onClick={open}
                    onKeyDown={(event) => { if (event.key === 'Enter') open() }}
                    className="rowbtn grid min-h-10 cursor-pointer items-center gap-3 px-4 py-1.5"
                    style={{ gridTemplateColumns: COLUMNS, borderTop: index === 0 ? '0' : '1px solid #EEF2F4' }}
                  >
                    <span className="flex items-center gap-2">
                      <LevelSwatch level={tank.level} />
                      <span className="mono font-semibold">{tank.id}</span>
                      <span className="text-xs" style={{ color: LEVEL[tank.level].text }}>{tank.level_label}</span>
                    </span>
                    <span className="text-ink-2">{tank.room_name}</span>
                    <span className="text-ink-2">{tank.age_text}</span>
                    <span className="tnum text-right">{tank.live_text}</span>
                    <span className="tnum text-right">{tank.survival_text}</span>
                    {tank.level === 'empty' ? (
                      <span>
                        <button type="button" className="ghost !h-7 !text-xs" onClick={(event) => { event.stopPropagation(); setStartFor(tank.id) }}>Start batch</button>
                      </span>
                    ) : (
                      <span className="text-ink-2">{tank.last_check_text}</span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </section>
      </div>
      {startFor && <StartBatchDialog tankId={startFor} onClose={() => setStartFor(null)} />}
    </>
  )
}
