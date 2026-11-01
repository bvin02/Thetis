import { ArrowUpRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ConditionRow, Level, TankDetail } from '../../api/types'
import { LARVA_COLOR, LEVEL, SEVERITY_DOT, severityText } from '../../lib/levels'
import { StatusPill } from '../ui'
import { OutlinedPhoto } from '../photo/OutlinedPhoto'
import { ActionRow } from './ActionRows'

const METER: Level[] = ['ok', 'watch', 'risk', 'critical']

/** The design shows a close crop of the photo so outlines read at this size; the review screen shows all of it. */
function closeCrop(width: number, height: number): [number, number, number, number] {
  const w = width * 0.62
  const h = Math.min(height, (w * 2) / 3)
  return [(width - w) / 2, (height - h) / 2, w, h]
}

function CountChip({ cls, count, label }: { cls: string; count: number; label: string }) {
  return (
    <span className="flex items-center gap-[5px]">
      <span className="box-border h-2 w-2 rounded-full" style={{ border: `2px solid ${LARVA_COLOR[cls]}` }} />
      {count} {label}
    </span>
  )
}

export function LatestCheck({ tank }: { tank: TankDetail }) {
  const latest = tank.latest_check
  if (!latest) return null
  const photo = latest.photo
  return (
    <section aria-label="Latest check" className="flex flex-col gap-2 px-4 pb-4">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-[13px] font-semibold">Latest check</h3>
        <span className="text-xs text-ink-4">{latest.when_text}</span>
      </div>
      {photo ? (
        <div className="relative box-border aspect-[3/2] w-full overflow-hidden rounded-control border border-line bg-muted-bg">
          <OutlinedPhoto
            url={photo.url} width={photo.width} height={photo.height} detections={photo.detections}
            view={closeCrop(photo.width, photo.height)}
            alt={`Microscope photo from the latest check of ${tank.id}, with each larva outlined: green live, orange abnormal, red dead`}
          >
            {photo.synthetic && (
              <span className="absolute top-2 left-2 rounded-small bg-white/95 px-1.5 py-0.5 text-[11px] font-medium text-ink-3 shadow-[0_1px_2px_rgba(15,26,32,0.08)]">
                Synthetic sample
              </span>
            )}
            <span className="tnum absolute bottom-2 left-2 flex flex-wrap gap-x-2.5 gap-y-1 rounded-small bg-white/95 px-2 py-1 text-xs text-ink shadow-[0_1px_2px_rgba(15,26,32,0.08)]">
              <CountChip cls="live" count={latest.n_live} label="live" />
              <CountChip cls="abnormal" count={latest.n_abnormal} label="abnormal" />
              <CountChip cls="dead" count={latest.n_dead} label="dead" />
            </span>
          </OutlinedPhoto>
        </div>
      ) : (
        <div className="grid aspect-[3/2] w-full place-items-center rounded-control border border-line bg-muted-bg text-xs text-ink-4">No photo</div>
      )}
      <div className="flex items-center justify-between gap-2 text-xs text-ink-4">
        <span className="tnum">
          {latest.n_counted} larvae{photo?.um_per_px ? ` · ${photo.um_per_px.toFixed(2)} µm/px` : ''}
        </span>
        <Link to={`/checks/${latest.id}`} className="font-medium whitespace-nowrap text-brand underline-offset-2">Review outlines</Link>
      </div>
    </section>
  )
}

export function RiskForecast({ tank }: { tank: TankDetail }) {
  const empty = tank.level === 'empty'
  return (
    <section aria-label="Risk forecast" className="flex flex-col gap-3 border-t border-divider p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-[13px] font-semibold">Risk forecast</h3>
        <span className="tag">Rules-based</span>
      </div>
      {!empty && (
        <div role="img" aria-label={`Risk level: ${tank.level_label}, on a scale of Normal, Watch, At risk, Critical`} className="flex gap-1">
          {METER.map((key) => {
            const on = key === tank.level
            return (
              <span key={key} className="flex flex-1 flex-col gap-1.5">
                <span className="h-1 rounded-[2px]" style={{ background: on ? LEVEL[key].color : '#E3E9EC' }} />
                <span className="text-[11px]" style={{ color: on ? LEVEL[key].text : '#66737B', fontWeight: on ? 600 : 400 }}>{LEVEL[key].label}</span>
              </span>
            )
          })}
        </div>
      )}
      <div className="flex flex-col gap-1">
        <span className="text-sm font-semibold">{tank.title}</span>
        <span className="text-[13px] leading-normal text-ink-2">{tank.forecast}</span>
      </div>
    </section>
  )
}

function ConditionLine({ row }: { row: ConditionRow }) {
  const dot = row.severity ? SEVERITY_DOT[row.severity] : 'transparent'
  return (
    <div className="flex min-h-8 items-center gap-3 border-t border-divider text-[13px]">
      <span className="flex min-w-0 flex-1 items-center gap-2 text-ink-2">
        <span className="h-1.5 w-1.5 flex-none rounded-full" style={{ background: dot }} />
        {row.label}
      </span>
      <span className="tnum w-[76px] text-right font-semibold" style={{ color: severityText(row.severity) }}>{row.now}</span>
      <span className="w-[108px] text-right text-xs leading-[1.35] text-ink-4">{row.cmp}</span>
    </div>
  )
}

export function ConditionTable({ tank }: { tank: TankDetail }) {
  if (tank.condition.length === 0) return null
  return (
    <section aria-label="Condition" className="flex flex-col border-t border-divider p-4">
      <div className="flex items-baseline gap-3 pb-2">
        <h3 className="flex-1 text-[13px] font-semibold">Condition</h3>
        <span className="w-[76px] text-right text-xs text-ink-4">Now</span>
        <span className="w-[108px] text-right text-xs text-ink-4">Compared with</span>
      </div>
      {tank.condition.map((row) => <ConditionLine key={`${row.key}-${row.severity}`} row={row} />)}
    </section>
  )
}

export function SurvivalChart({ tank }: { tank: TankDetail }) {
  const points = tank.series.points.filter((p) => p.survival !== null)
  if (points.length < 2) return null
  const lastDay = points[points.length - 1].day || 1
  const xy = points.map((p) => [4 + (p.day / lastDay) * 292, 6 + (1 - Math.min(p.survival ?? 0, 1)) * 52] as const)
  const line = xy.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const [endX, endY] = xy[xy.length - 1]
  const area = `M${xy[0][0].toFixed(1)},58 L${xy.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L')} L${endX.toFixed(1)},58 Z`
  const endColor = tank.level === 'ok' || tank.level === 'empty' ? '#0F1A20' : LEVEL[tank.level].color
  const nChecks = points.length - 1
  return (
    <section aria-label="Survival since spawn" className="flex flex-col gap-2 border-t border-divider p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-[13px] font-semibold">Survival since spawn</h3>
        <span className="tnum text-[13px] font-semibold">{tank.survival_text}</span>
      </div>
      <div className="flex gap-2">
        <div aria-hidden="true" className="tnum flex flex-col justify-between pb-0.5 text-[10px] text-ink-4">
          <span>100%</span><span>50%</span><span>0%</span>
        </div>
        <svg viewBox="0 0 300 64" width="100%" role="img" className="block min-w-0 flex-1"
          aria-label={`Survival fell from 100% at spawn to ${tank.survival_text} over ${nChecks} ${nChecks === 1 ? 'check' : 'checks'}`}>
          <line x1="0" y1="6" x2="300" y2="6" stroke="#EEF2F4" />
          <line x1="0" y1="32" x2="300" y2="32" stroke="#EEF2F4" />
          <line x1="0" y1="58" x2="300" y2="58" stroke="#E2E8EC" />
          <path d={area} fill="#0F1A20" fillOpacity="0.05" />
          <polyline points={line} fill="none" stroke="#0F1A20" strokeWidth="1.5" strokeLinejoin="round" />
          {xy.slice(0, -1).map(([x, y]) => (
            <circle key={`${x}-${y}`} cx={x} cy={y} r="2.4" fill="#FFFFFF" stroke="#0F1A20" strokeWidth="1.3" />
          ))}
          <circle cx={endX} cy={endY} r="4" fill={endColor} stroke="#FFFFFF" strokeWidth="1.5" />
        </svg>
      </div>
      <div className="flex justify-between pl-[34px] text-[11px] text-ink-4">
        <span>Spawn</span>
        <span>{nChecks} {nChecks === 1 ? 'check' : 'checks'}</span>
        <span>{points[points.length - 1].day_label}</span>
      </div>
    </section>
  )
}

export function RecommendedActions({ tank }: { tank: TankDetail }) {
  if (tank.actions.length === 0) return null
  const left = tank.actions_left
  return (
    <section aria-label="Recommended actions" className="flex flex-col border-t border-divider px-4 pt-4 pb-2">
      <div className="flex items-baseline justify-between gap-2 pb-1">
        <h3 className="text-[13px] font-semibold">Recommended actions</h3>
        <span className="text-xs text-ink-4">{left === 0 ? 'All decided' : `${left} to decide`}</span>
      </div>
      {tank.actions.map((action, index) => (
        <ActionRow key={action.id} action={action} number={index + 1} divider={index > 0} />
      ))}
    </section>
  )
}

export function InspectorHeader({ tank }: { tank: TankDetail }) {
  return (
    <div className="flex flex-col gap-1 p-4">
      <div className="flex items-center gap-2.5">
        <span className="mono flex-1 text-xl font-semibold tracking-[-0.01em]">{tank.id}</span>
        <StatusPill level={tank.level} large />
      </div>
      <span className="text-[13px] text-ink-2">{tank.age_text}</span>
      <span className="text-xs text-ink-4">
        {tank.room_name}{tank.batch_code ? ` · Batch ${tank.batch_code}` : ''} · <span style={{ color: tank.line_alert ? '#B54708' : '#0F1A20' }}>{tank.line_text}</span>
      </span>
    </div>
  )
}

export function Inspector({ tank, showOpenLink = true }: { tank: TankDetail; showOpenLink?: boolean }) {
  return (
    <>
      <InspectorHeader tank={tank} />
      <LatestCheck tank={tank} />
      <RiskForecast tank={tank} />
      <ConditionTable tank={tank} />
      <SurvivalChart tank={tank} />
      <RecommendedActions tank={tank} />
      {showOpenLink && (
        <Link to={`/tanks/${tank.id}`} className="rowbtn mt-auto flex items-center justify-between rounded-b-card border-t border-divider px-4 py-3 text-[13px] font-medium no-underline">
          Open {tank.id}
          <ArrowUpRight size={14} strokeWidth={2} aria-hidden="true" />
        </Link>
      )}
    </>
  )
}
