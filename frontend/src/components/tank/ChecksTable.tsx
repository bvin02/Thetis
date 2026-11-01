import { useNavigate } from 'react-router-dom'
import type { CheckRow, Severity } from '../../api/types'
import { severityText } from '../../lib/levels'
import { EmptyState } from '../ui'

const HEAD = 'px-1 py-2.5 text-left text-xs font-normal whitespace-nowrap text-ink-4'
const CELL = 'tnum px-1 py-1.5 text-[13px] whitespace-nowrap'

function Value({ text, severity }: { text: string; severity?: Severity }) {
  return <span style={{ color: severity ? severityText(severity) : undefined, fontWeight: severity ? 500 : undefined }}>{text}</span>
}

export function ChecksTable({ checks }: { checks: CheckRow[] }) {
  const navigate = useNavigate()
  return (
    <section aria-label="Checks" className="rounded-card border border-line">
      <div className="flex items-baseline justify-between gap-2 border-b border-divider px-4 py-3">
        <h2 className="text-sm font-semibold">Checks</h2>
        <span className="tnum text-xs text-ink-4">{checks.length} this batch</span>
      </div>
      {checks.length === 0 ? (
        <EmptyState title="No checks yet">New checks for this batch show up here.</EmptyState>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[740px] border-collapse">
            <thead>
              <tr className="border-b border-divider">
                <th scope="col" className={`${HEAD} pl-4`}>When</th>
                <th scope="col" className={HEAD}>Day</th>
                <th scope="col" className={`${HEAD} text-right`}>Larvae</th>
                <th scope="col" className={`${HEAD} text-right`}>Survival</th>
                <th scope="col" className={`${HEAD} text-right`}>Length</th>
                <th scope="col" className={`${HEAD} text-right`}>Growth</th>
                <th scope="col" className={`${HEAD} text-right`}>Dead</th>
                <th scope="col" className={`${HEAD} text-right`}>Abnormal</th>
                <th scope="col" className={`${HEAD} text-right`}>Gut</th>
                <th scope="col" className={`${HEAD} text-right`}>Ω</th>
                <th scope="col" className={`${HEAD} text-right`}>pH</th>
                <th scope="col" className={`${HEAD} text-right`}>Temp</th>
                <th scope="col" className={`${HEAD} pr-4 text-right`}>Photos</th>
              </tr>
            </thead>
            <tbody>
              {checks.map((row, index) => {
                const s = row.severities
                return (
                  <tr
                    key={row.id}
                    className="rowbtn cursor-pointer"
                    style={{ borderTop: index === 0 ? '0' : '1px solid #EEF2F4' }}
                    tabIndex={0}
                    aria-label={`Open the check from ${row.when_text}`}
                    onClick={() => navigate(`/checks/${row.id}`)}
                    onKeyDown={(event) => { if (event.key === 'Enter') navigate(`/checks/${row.id}`) }}
                  >
                    <td className={`${CELL} pl-4`}>{row.when_text}</td>
                    <td className={`${CELL} text-ink-2`}>{row.day}</td>
                    <td className={`${CELL} text-right`}><Value text={row.live_text} severity={s.loss} /></td>
                    <td className={`${CELL} text-right`}>{row.survival_text}</td>
                    <td className={`${CELL} text-right`}>{row.length_text}</td>
                    <td className={`${CELL} text-right`}><Value text={row.growth_text} severity={s.growth} /></td>
                    <td className={`${CELL} text-right`}><Value text={row.dead_text} severity={s.dead} /></td>
                    <td className={`${CELL} text-right`}><Value text={row.abnormal_text} severity={s.abnormal} /></td>
                    <td className={`${CELL} text-right`}><Value text={row.gut_text} severity={s.gut} /></td>
                    <td className={`${CELL} text-right`}><Value text={row.omega_text} severity={s.omega} /></td>
                    <td className={`${CELL} text-right`}><Value text={row.ph_text} severity={s.ph} /></td>
                    <td className={`${CELL} text-right`}><Value text={row.temp_text} severity={s.temp} /></td>
                    <td className={`${CELL} pr-4 text-right text-ink-2`}>{row.n_photos}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
