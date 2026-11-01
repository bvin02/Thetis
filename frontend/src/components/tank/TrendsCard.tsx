import { useMemo, useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Level, SeriesPoint, TankDetail } from '../../api/types'
import { LEVEL } from '../../lib/levels'
import { EmptyState, Segmented } from '../ui'

type Trend = 'survival' | 'length' | 'mortality' | 'water'

const INK = '#0F1A20'
const SECOND = '#7D8A92'
const GUIDE = '#C7CFD4'
const AXIS = { fontSize: 11, fill: '#66737B' }

interface Row {
  day: number
  label: string
  a: number | null
  b?: number | null
  guide?: number | null
  level: Level
  isLast: boolean
}

function endDot(color: string) {
  // The last point takes the level colour; the others are small ink points
  return function Dot(props: { cx?: number; cy?: number; payload?: Row; index?: number; value?: number | null }) {
    const { cx, cy, payload, index, value } = props
    if (cx === undefined || cy === undefined || value === null || value === undefined) return <g key={index} />
    if (payload?.isLast) {
      const level = payload.level
      const fill = level === 'ok' || level === 'empty' ? color : LEVEL[level].color
      return <circle key={index} cx={cx} cy={cy} r={4} fill={fill} stroke="#FFFFFF" strokeWidth={1.5} />
    }
    return <circle key={index} cx={cx} cy={cy} r={3} fill="#FFFFFF" stroke={color} strokeWidth={1.5} />
  }
}

function TipBox({ active, payload, names, format }: {
  active?: boolean
  payload?: { dataKey?: string; value?: number | null; payload?: Row }[]
  names: Record<string, string>
  format: (key: string, value: number) => string
}) {
  if (!active || !payload || payload.length === 0) return null
  const row = payload[0].payload
  return (
    <div className="flex flex-col gap-1 rounded-control border border-line bg-white px-2.5 py-2 text-xs shadow-pop">
      <span className="font-semibold text-ink">{row?.label}</span>
      {payload.filter((p) => p.dataKey !== 'guide' && p.value !== null && p.value !== undefined).map((p) => (
        <span key={String(p.dataKey)} className="tnum flex justify-between gap-4 text-ink-2">
          <span>{names[String(p.dataKey)]}</span>
          <span className="font-medium text-ink">{format(String(p.dataKey), p.value as number)}</span>
        </span>
      ))}
    </div>
  )
}

function lastValid(points: SeriesPoint[], pick: (p: SeriesPoint) => number | null): SeriesPoint | null {
  for (let i = points.length - 1; i >= 0; i--) if (pick(points[i]) !== null) return points[i]
  return null
}

function buildRows(points: SeriesPoint[], pickA: (p: SeriesPoint) => number | null, pickB?: (p: SeriesPoint) => number | null, guide?: (p: SeriesPoint) => number | null): Row[] {
  const last = lastValid(points, pickA)
  return points.map((p) => ({
    day: p.day,
    label: p.day_label,
    a: pickA(p),
    b: pickB ? pickB(p) : undefined,
    guide: guide ? guide(p) : undefined,
    level: p.level,
    isLast: last !== null && p === last,
  }))
}

export function TrendsCard({ tank }: { tank: TankDetail }) {
  const [trend, setTrend] = useState<Trend>('survival')
  const points = tank.series.points
  const checks = useMemo(() => points.filter((p) => p.check_id !== null), [points])
  const lastDay = points.length ? Math.ceil(points[points.length - 1].day) : 1

  const view = useMemo(() => {
    if (trend === 'survival') {
      const rows = buildRows(points, (p) => (p.survival === null ? null : Math.round(p.survival * 1000) / 10))
      const last = lastValid(points, (p) => p.survival)
      return {
        rows, names: { a: 'Survival' }, format: (_: string, v: number) => `${Math.round(v)}%`, unit: '%', domain: [0, 100] as [number, number],
        guides: [] as { y: number; label: string }[], hasB: false, hasGuide: false, legend: null as string[] | null,
        summary: last ? `Survival fell from 100% at spawn to ${tank.survival_text} by ${last.day_label}.` : 'No survival estimates yet.',
      }
    }
    if (trend === 'length') {
      const first = checks.find((p) => p.length_um !== null)
      const expected = tank.expected_growth_um_day
      const rows = buildRows(
        checks,
        (p) => p.length_um,
        undefined,
        (p) => (first && p.day >= first.day ? Math.round((first.length_um as number) + expected * (p.day - first.day)) : null),
      )
      const last = lastValid(checks, (p) => p.length_um)
      return {
        rows, names: { a: 'Shell length' }, format: (_: string, v: number) => `${Math.round(v)} µm`, unit: ' µm', domain: ['auto', 'auto'] as [string, string],
        guides: [] as { y: number; label: string }[], hasB: false, hasGuide: true, legend: [`Dashed: expected ${expected} µm/day`],
        summary: last && first ? `Shell length went from ${Math.round(first.length_um as number)} to ${Math.round(last.length_um as number)} µm; ${expected} µm a day is expected.` : 'No sizes yet.',
      }
    }
    if (trend === 'mortality') {
      const rows = buildRows(checks, (p) => p.pct_dead, (p) => p.pct_abnormal)
      const last = lastValid(checks, (p) => p.pct_dead)
      return {
        rows, names: { a: 'Dead', b: 'Abnormal' }, format: (_: string, v: number) => `${Math.round(v)}%`, unit: '%', domain: [0, (max: number) => Math.max(25, Math.ceil(max / 5) * 5)] as [number, (max: number) => number],
        guides: [{ y: 10, label: 'Dead: watch 10%' }, { y: 20, label: 'Dead: critical 20%' }], hasB: true, hasGuide: false, legend: ['Dead', 'Abnormal'],
        summary: last ? `Dead larvae at ${Math.round(last.pct_dead as number)}%, abnormal at ${Math.round((last.pct_abnormal ?? 0))}% at the last check.` : 'No counts yet.',
      }
    }
    const rows = buildRows(checks, (p) => p.omega, (p) => p.ph)
    const last = lastValid(checks, (p) => p.omega)
    return {
      rows, names: { a: 'Ω aragonite', b: 'pH' }, format: (key: string, v: number) => (key === 'b' ? v.toFixed(2) : v.toFixed(1)), unit: '',
      domain: [0, (max: number) => Math.max(4, Math.ceil(max))] as [number, (max: number) => number],
      guides: [{ y: 2, label: 'Ω target 2' }], hasB: true, hasGuide: false, legend: ['Ω aragonite (left)', 'pH (right)'],
      summary: last ? `Ω aragonite was ${(last.omega as number).toFixed(1)} at the last reading; the target is 2 or higher.` : 'No water readings yet.',
    }
  }, [trend, points, checks, tank.survival_text, tank.expected_growth_um_day])

  // The spawn point alone is not a trend
  const hasData = view.rows.filter((r) => r.a !== null).length > (trend === 'survival' ? 1 : 0)

  return (
    <section aria-label="Trends" className="rounded-card border border-line">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-divider px-4 py-3 max-[660px]:px-3">
        <h2 className="flex-auto text-sm font-semibold">Trends</h2>
        {view.legend && hasData && (
          <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1 text-xs text-ink-3">
            {view.legend.map((label, index) => (
              <span key={label} className="flex items-center gap-1.5">
                {!label.startsWith('Dashed') && <span className="h-0.5 w-4 rounded-[1px]" style={{ background: index === 0 ? INK : SECOND }} />}
                {label}
              </span>
            ))}
          </div>
        )}
        <Segmented
          label="Trend"
          value={trend}
          onChange={setTrend}
          options={[
            { value: 'survival', label: 'Survival' },
            { value: 'length', label: 'Shell length' },
            { value: 'mortality', label: 'Dead & abnormal' },
            { value: 'water', label: 'Water' },
          ]}
        />
      </div>
      {hasData ? (
        <div role="img" aria-label={view.summary} className="px-2 pt-4 pb-2" style={{ height: 276 }}>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={view.rows} margin={{ top: 8, right: trend === 'water' ? 0 : 16, bottom: 4, left: 0 }}>
              <CartesianGrid vertical={false} stroke="#EEF2F4" />
              <XAxis
                type="number" dataKey="day" domain={[trend === 'survival' ? 0 : 'dataMin', Math.max(lastDay, 1)]} tick={AXIS} tickLine={false}
                axisLine={{ stroke: '#E2E8EC' }} allowDecimals={false} tickFormatter={(v: number) => `Day ${Math.round(v)}`} minTickGap={32}
              />
              <YAxis yAxisId="left" domain={view.domain as never} tick={AXIS} tickLine={false} axisLine={false} width={48} tickFormatter={(v: number) => (trend === 'water' ? String(v) : `${Math.round(v)}${view.unit}`)} />
              {trend === 'water' && (
                <YAxis yAxisId="right" orientation="right" domain={[7.4, 8.2]} ticks={[7.4, 7.6, 7.8, 8, 8.2]} tick={AXIS} tickLine={false} axisLine={false} width={36} tickFormatter={(v: number) => v.toFixed(1)} />
              )}
              <Tooltip
                cursor={{ stroke: '#CCD5DB', strokeDasharray: '3 3' }} isAnimationActive={false}
                content={(props) => <TipBox active={props.active} payload={props.payload as never} names={view.names as Record<string, string>} format={view.format} />}
              />
              {view.guides.map((guide) => (
                <ReferenceLine key={guide.y} yAxisId="left" y={guide.y} stroke={GUIDE} strokeDasharray="4 3" label={{ value: guide.label, position: 'insideTopLeft', fontSize: 10.5, fill: '#66737B' }} />
              ))}
               {view.hasGuide && <Line yAxisId="left" type="linear" dataKey="guide" stroke={GUIDE} strokeWidth={1.5} strokeDasharray="4 3" dot={false} activeDot={false} isAnimationActive={false} connectNulls />}
               {view.hasB && <Line yAxisId={trend === 'water' ? 'right' : 'left'} type="linear" dataKey="b" stroke={SECOND} strokeWidth={1.5} dot={{ r: 2.5, fill: '#FFFFFF', stroke: SECOND, strokeWidth: 1.5 }} isAnimationActive={false} connectNulls />}
              <Line yAxisId="left" type="linear" dataKey="a" stroke={INK} strokeWidth={1.5} dot={endDot(INK)} activeDot={{ r: 4, fill: INK, stroke: '#FFFFFF', strokeWidth: 1.5 }} isAnimationActive={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <EmptyState title="Nothing to chart yet">{tank.batch ? 'Save a check with this measure to start the trend.' : 'Start a batch in this tank first.'}</EmptyState>
      )}
    </section>
  )
}
