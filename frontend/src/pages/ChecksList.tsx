import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getJSON } from '../api/client'
import { useFloor } from '../api/hooks'
import type { CheckRow } from '../api/types'
import { TopBar } from '../components/shell/TopBar'
import { EmptyState, ErrorState, LoadingState, StatusPill } from '../components/ui'
import { severityText } from '../lib/levels'
import { RoomChips } from './TanksList'

const HEAD = 'px-2 py-2.5 text-left text-xs font-normal whitespace-nowrap text-ink-4'
const CELL = 'tnum px-2 py-1.5 text-[13px] whitespace-nowrap'

export default function ChecksListPage() {
  const floor = useFloor()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const room = params.get('room')
  const query = useQuery({
    queryKey: ['checks', room],
    queryFn: () => getJSON<{ checks: CheckRow[] }>(`/api/checks${room ? `?room=${room}` : ''}`),
    placeholderData: keepPreviousData,
  })
  const checks = query.data?.checks
  return (
    <>
      <TopBar crumbs={['Checks']} />
      <div className="flex flex-col gap-4 px-7 pt-6 pb-7 max-[660px]:px-4">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
          <h1 className="flex-auto text-[28px] leading-[1.15] font-semibold tracking-[-0.025em]">Checks</h1>
          <RoomChips rooms={floor.data?.rooms ?? []} value={room} onChange={(id) => setParams(id ? { room: id } : {}, { replace: true })} />
        </div>
        {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}
        {!checks && query.isPending && <LoadingState />}
        {checks && checks.length === 0 && <div className="rounded-card border border-line"><EmptyState title="No checks yet">Saved checks appear here, newest first.</EmptyState></div>}
        {checks && checks.length > 0 && (
          <section aria-label="Checks" className="rounded-card border border-line">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[780px] border-collapse">
                <thead>
                  <tr className="border-b border-divider">
                    <th scope="col" className={`${HEAD} pl-4`}>When</th>
                    <th scope="col" className={HEAD}>Tank</th>
                    <th scope="col" className={HEAD}>Batch</th>
                    <th scope="col" className={`${HEAD} text-right`}>Larvae counted</th>
                    <th scope="col" className={`${HEAD} text-right`}>Dead</th>
                    <th scope="col" className={`${HEAD} text-right`}>Abnormal</th>
                    <th scope="col" className={`${HEAD} text-right`}>Length</th>
                    <th scope="col" className={HEAD}>Level after check</th>
                    <th scope="col" className={`${HEAD} pr-4 text-right`}>Photos</th>
                  </tr>
                </thead>
                <tbody>
                  {checks.map((row, index) => (
                    <tr
                      key={row.id}
                      className="rowbtn cursor-pointer"
                      style={{ borderTop: index === 0 ? '0' : '1px solid #EEF2F4' }}
                      tabIndex={0}
                      aria-label={`Open the check of ${row.tank_id} from ${row.when_text}`}
                      onClick={() => navigate(`/checks/${row.id}`)}
                      onKeyDown={(event) => { if (event.key === 'Enter') navigate(`/checks/${row.id}`) }}
                    >
                      <td className={`${CELL} pl-4`}>{row.when_text}</td>
                      <td className={`${CELL} mono font-semibold`}>{row.tank_id}</td>
                      <td className={`${CELL} text-ink-2`}>{row.batch_code}</td>
                      <td className={`${CELL} text-right`}>{row.n_counted}</td>
                      <td className={`${CELL} text-right`} style={{ color: row.severities.dead ? severityText(row.severities.dead) : undefined }}>{row.dead_text}</td>
                      <td className={`${CELL} text-right`} style={{ color: row.severities.abnormal ? severityText(row.severities.abnormal) : undefined }}>{row.abnormal_text}</td>
                      <td className={`${CELL} text-right`}>{row.length_text}</td>
                      <td className={CELL}><StatusPill level={row.level} /></td>
                      <td className={`${CELL} pr-4 text-right text-ink-2`}>{row.n_photos}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </>
  )
}
