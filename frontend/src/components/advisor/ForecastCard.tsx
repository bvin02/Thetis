import { Link } from 'react-router-dom'
import type { Forecast, ForecastRow } from '../../api/types'
import { LevelSwatch } from '../ui'

const ON_COURSE = '#0F1A20'
const POSSIBLE = '#CCD5DB'

/** Two amounts for one tank on one scale: dark is on course, the grey behind it is what's possible. */
function Bar({ row, max }: { row: ForecastRow; max: number }) {
  const possible = max > 0 ? (row.possible / max) * 100 : 0
  const onCourse = max > 0 ? (row.on_course / max) * 100 : 0
  return (
    <div aria-hidden="true" className="relative h-2 w-full min-w-[72px] rounded-full bg-divider">
      <span className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${possible}%`, background: POSSIBLE }} />
      {onCourse > 0 && <span className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${onCourse}%`, background: ON_COURSE, boxShadow: '0 0 0 2px #FFFFFF' }} />}
    </div>
  )
}

export function ForecastCard({ forecast }: { forecast: Forecast }) {
  if (forecast.rows.length === 0) return null
  const max = Math.max(...forecast.rows.map((r) => r.possible), 1)
  const pace = forecast.pace
  return (
    <section aria-label="Forecast to the eyed stage" className="flex flex-col rounded-card border border-line">
      <div className="flex flex-col gap-2 p-4 pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-[15px] font-semibold">Forecast to the eyed stage</h3>
          <span className="tag">Rules-based</span>
        </div>
        <p className="m-0 max-w-[68ch] text-[13px] leading-[1.5] text-ink-2">
          At today's rates about <span className="tnum font-semibold text-ink">{forecast.on_course_text}</span> larvae reach the eyed stage.
          {pace && <> If every tank kept <Link to={`/tanks/${pace.tank_id}`} className="mono font-semibold text-ink no-underline hover:underline">{pace.tank_id}</Link>'s pace, about <span className="tnum font-semibold text-ink">{forecast.possible_text}</span> could.</>}
        </p>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-3">
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: ON_COURSE }} />On course</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: POSSIBLE }} />Possible at {pace?.tank_id ?? 'the best'} pace</span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] border-collapse text-[13px]">
          <thead>
            <tr className="text-left text-xs text-ink-4">
              <th scope="col" className="px-4 py-1.5 font-medium">Tank</th>
              <th scope="col" className="px-2 py-1.5 text-right font-medium">Live now</th>
              <th scope="col" className="px-2 py-1.5 font-medium">Eyed in</th>
              <th scope="col" className="w-[28%] px-2 py-1.5 font-medium"><span className="sr-only">On course and possible, as bars</span></th>
              <th scope="col" className="px-2 py-1.5 text-right font-medium">On course</th>
              <th scope="col" className="px-2 py-1.5 text-right font-medium">Possible</th>
              <th scope="col" className="px-4 py-1.5 text-right font-medium">Gap</th>
            </tr>
          </thead>
          <tbody>
            {forecast.rows.map((row) => (
              <tr key={row.tank_id} className="border-t border-divider">
                <td className="px-4 py-2">
                  <span className="flex items-center gap-2">
                    <LevelSwatch level={row.level} size={8} />
                    <Link to={`/tanks/${row.tank_id}`} className="mono font-semibold whitespace-nowrap no-underline hover:underline">{row.tank_id}</Link>
                  </span>
                </td>
                <td className="tnum px-2 py-2 text-right text-ink-2">{row.live_text}</td>
                <td className="px-2 py-2 whitespace-nowrap text-ink-2">{row.when_text}</td>
                <td className="px-2 py-2"><Bar row={row} max={max} /></td>
                <td className="tnum px-2 py-2 text-right font-medium">{row.on_course_text}</td>
                <td className="tnum px-2 py-2 text-right text-ink-2">{row.possible_text}</td>
                <td className="tnum px-4 py-2 text-right text-ink-2">{row.gain_text}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-line font-semibold">
              <td className="px-4 py-2" colSpan={4}>All larval tanks</td>
              <td className="tnum px-2 py-2 text-right">{forecast.on_course_text}</td>
              <td className="tnum px-2 py-2 text-right">{forecast.possible_text}</td>
              <td className="tnum px-4 py-2 text-right">{forecast.gain_text}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="m-0 border-t border-divider px-4 py-2.5 text-xs leading-[1.5] text-ink-4">
        A rough straight line from each tank's latest growth and losses, not a promise.
        {pace && ` "Possible" assumes at least the expected growth and no more than ${pace.tank_id}'s ${pace.loss_pct_per_day}% loss a day.`}
      </p>
    </section>
  )
}
