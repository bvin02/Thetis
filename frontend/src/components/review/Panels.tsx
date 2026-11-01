import { ChevronDown, ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Estimate, LineWater, Summary, WaterReadings } from '../../api/types'
import { LARVA_COLOR } from '../../lib/levels'
import { EMPTY_WATER, type WaterForm } from '../../lib/water'

const fmtCount = (n: number | null | undefined) => {
  if (n === null || n === undefined) return '—'
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (Math.abs(n) >= 1e3) return `${Math.round(n / 1e3)}k`
  return String(Math.round(n))
}

export function PanelSection({ title, aside, children, label }: { title?: ReactNode; aside?: ReactNode; children: ReactNode; label?: string }) {
  return (
    <section aria-label={label} className="flex flex-col gap-2.5 border-t border-divider p-4 first:border-t-0">
      {(title || aside) && (
        <div className="flex items-baseline justify-between gap-2">
          <h3 className="text-[13px] font-semibold">{title}</h3>
          {aside && <span className="text-xs text-ink-4">{aside}</span>}
        </div>
      )}
      {children}
    </section>
  )
}

function Fact({ label, value, note, cls, first }: { label: string; value: string; note: string; cls: string; first: boolean }) {
  return (
    <div className="flex flex-col gap-0.5 px-3 py-2.5" style={{ borderLeft: first ? '0' : '1px solid #EEF2F4' }}>
      <dt className="flex items-center gap-1.5 text-xs text-ink-4">
        <span className="box-border h-2 w-2 rounded-full" style={{ border: `2px solid ${LARVA_COLOR[cls]}` }} />
        {label}
      </dt>
      <dd className="tnum text-base font-semibold">{value}</dd>
      <dd className="tnum text-xs text-ink-4">{note}</dd>
    </div>
  )
}

export function CountsPanel({ summary, children }: { summary: Pick<Summary, 'n_live' | 'n_abnormal' | 'n_dead' | 'pct_dead' | 'pct_abnormal'>; children?: ReactNode }) {
  const counted = summary.n_live + summary.n_abnormal + summary.n_dead
  const pct = (n: number) => (counted ? `${Math.round((100 * n) / counted)}%` : '0%')
  return (
    <PanelSection title="Counts" aside={`${counted} counted`} label="Counts">
      <dl className="grid grid-cols-3 rounded-card border border-line">
        <Fact label="Live" value={String(summary.n_live)} note={`${pct(summary.n_live)} of counted`} cls="live" first />
        <Fact label="Abnormal" value={String(summary.n_abnormal)} note={`${pct(summary.n_abnormal)} of counted`} cls="abnormal" first={false} />
        <Fact label="Dead" value={String(summary.n_dead)} note={`${pct(summary.n_dead)} of counted`} cls="dead" first={false} />
      </dl>
      {children}
    </PanelSection>
  )
}

function Histogram({ hist, previous }: { hist: number[]; previous: number[] | null }) {
  const lo = 40
  const bin = 10
  let first = hist.findIndex((v) => v > 0)
  let last = hist.length - 1 - [...hist].reverse().findIndex((v) => v > 0)
  if (previous) {
    const pf = previous.findIndex((v) => v > 0)
    const pl = previous.length - 1 - [...previous].reverse().findIndex((v) => v > 0)
    if (pf >= 0) { first = Math.min(first, pf); last = Math.max(last, pl) }
  }
  first = Math.max(0, first - 1)
  last = Math.min(hist.length - 1, last + 1)
  const span = last - first + 1
  const height = 64
  const width = 340
  const barWidth = width / span
  const max = Math.max(...hist.slice(first, last + 1), ...(previous ? previous.slice(first, last + 1) : [0]), 1)
  const bars = hist.slice(first, last + 1)
  const prev = previous ? previous.slice(first, last + 1) : null
  const text = `Shell lengths from ${lo + first * bin} to ${lo + (last + 1) * bin} µm${previous ? ', with the previous check outlined' : ''}`
  return (
    <div className="flex flex-col gap-1">
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label={text} className="block">
        <line x1="0" y1={height - 0.5} x2={width} y2={height - 0.5} stroke="#E2E8EC" />
        {bars.map((v, i) => {
          const h = (v / max) * (height - 4)
          return v > 0 ? <rect key={i} x={i * barWidth + 1} y={height - h} width={Math.max(barWidth - 2, 1)} height={h} fill="#A7B3BA" rx="1" /> : null
        })}
        {prev && prev.map((v, i) => {
          const h = (v / max) * (height - 4)
          return v > 0 ? <rect key={i} x={i * barWidth + 1} y={height - h} width={Math.max(barWidth - 2, 1)} height={h} fill="none" stroke="#0F1A20" strokeWidth="1" rx="1" /> : null
        })}
      </svg>
      <div className="tnum flex justify-between text-[11px] text-ink-4">
        <span>{lo + first * bin} µm</span>
        {previous && <span>Outline: previous check</span>}
        <span>{lo + (last + 1) * bin} µm</span>
      </div>
    </div>
  )
}

export function SizePanel({ summary, previousHist, calibrated }: { summary: Pick<Summary, 'mean_len_um' | 'sd_len_um' | 'cv' | 'stage' | 'hist'>; previousHist: number[] | null; calibrated: boolean }) {
  if (!calibrated || summary.mean_len_um === null) {
    return (
      <PanelSection title="Size" label="Size">
        <span className="text-[13px] leading-normal text-ink-3">
          {calibrated ? 'No whole larvae to measure yet.' : 'Sizes need a scale. Add a scale under the photo to see length, stage and growth.'}
        </span>
      </PanelSection>
    )
  }
  return (
    <PanelSection title="Size" label="Size" aside={summary.stage ? <span className="tag">{summary.stage}</span> : undefined}>
      <div className="flex items-baseline gap-4">
        <span className="tnum text-base font-semibold">
          {Math.round(summary.mean_len_um)}{summary.sd_len_um !== null && ` ± ${Math.round(summary.sd_len_um)}`} <span className="text-[13px] font-normal text-ink-4">µm</span>
        </span>
        {summary.cv !== null && <span className="tnum text-[13px] text-ink-2">CV {summary.cv.toFixed(2)}</span>}
      </div>
      {summary.hist && <Histogram hist={summary.hist} previous={previousHist} />}
    </PanelSection>
  )
}

export function GutPanel({ gut }: { gut: number | null }) {
  return (
    <PanelSection title={<>Gut fullness <span className="font-normal text-ink-4">beta</span></>} label="Gut fullness">
      <span className="tnum text-base font-semibold">{gut === null ? '—' : gut.toFixed(2)}</span>
    </PanelSection>
  )
}

export function EstimateText({ estimate }: { estimate: Estimate | null }) {
  if (!estimate || estimate.live_est === null) {
    return <span className="text-[13px] leading-normal text-ink-3">The estimate needs a scale, because the volume in view comes from it.</span>
  }
  return (
    <div className="flex flex-col gap-1.5">
      <span className="tnum text-sm font-semibold">
        ≈ {fmtCount(estimate.live_est)} live larvae
        {estimate.survival !== null && estimate.stocked !== null && (
          <span className="font-normal text-ink-3"> ({Math.round(estimate.survival * 100)}% of {fmtCount(estimate.stocked)} stocked)</span>
        )}
      </span>
      {estimate.over_stocked && (
        <span role="alert" className="text-xs font-medium text-watch-text">More than were stocked. Check the concentration.</span>
      )}
    </div>
  )
}

function NumberField({ id, label, value, onChange, step = 'any', min = '0', suffix }: {
  id: string; label: string; value: string; onChange: (value: string) => void; step?: string; min?: string; suffix?: string
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <label htmlFor={id} className="text-xs text-ink-4">{label}</label>
      <div className="relative">
        <input id={id} type="number" inputMode="decimal" className="field tnum max-[660px]:!h-11" step={step} min={min} value={value} onChange={(event) => onChange(event.target.value)} />
        {suffix && <span className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-xs text-ink-4">{suffix}</span>}
      </div>
    </div>
  )
}

export function EstimatePanel({ bucket, concentration, onBucket, onConcentration, estimate, note }: {
  bucket: string; concentration: string; onBucket: (v: string) => void; onConcentration: (v: string) => void; estimate: Estimate | null; note?: string
}) {
  return (
    <PanelSection title="Estimate for the tank" label="Estimate for the tank">
      <div className="grid grid-cols-2 gap-2">
        <NumberField id="bucket" label="Bucket volume (L)" value={bucket} onChange={onBucket} />
        <NumberField id="concentration" label="Sample concentrated ×" value={concentration} onChange={onConcentration} />
      </div>
      <EstimateText estimate={estimate} />
      {note && <span className="text-xs leading-normal text-ink-4">{note}</span>}
    </PanelSection>
  )
}

const WATER_FIELDS: { key: keyof WaterReadings; label: string; id: string }[] = [
  { key: 'temp_c', label: 'Temperature °C', id: 'w-temp' },
  { key: 'salinity_ppt', label: 'Salinity ppt', id: 'w-sal' },
  { key: 'ph', label: 'pH', id: 'w-ph' },
  { key: 'omega_arag', label: 'Ω aragonite', id: 'w-omega' },
  { key: 'do_mgl', label: 'Oxygen mg/L', id: 'w-do' },
]

function readingText(water: LineWater) {
  const parts = []
  if (water.omega_arag !== null) parts.push(`Ω ${water.omega_arag.toFixed(1)}`)
  if (water.ph !== null) parts.push(`pH ${water.ph.toFixed(2)}`)
  parts.push(water.when_text)
  return parts.join(' · ')
}

export function WaterPanel({ value, onChange, lineName, lineWater, open, onToggle }: {
  value: WaterForm; onChange: (value: WaterForm) => void; lineName: string | null; lineWater: LineWater | null; open: boolean; onToggle: () => void
}) {
  const useThese = () => {
    if (!lineWater) return
    const next = { ...EMPTY_WATER }
    for (const field of WATER_FIELDS) {
      const reading = lineWater[field.key]
      next[field.key] = reading === null ? '' : String(reading)
    }
    onChange(next)
  }
  const filled = Object.values(value).filter((v) => v !== '').length
  return (
    <section aria-label="Water readings" className="flex flex-col gap-2.5 border-t border-divider p-4">
      <button type="button" className="flex cursor-pointer items-center justify-between gap-2 border-0 bg-transparent p-0 text-left" aria-expanded={open} onClick={onToggle}>
        <span className="text-[13px] font-semibold">Water readings <span className="font-normal text-ink-4">(optional)</span></span>
        <span className="flex items-center gap-1 text-xs text-ink-4">
          {filled > 0 && !open && `${filled} added`}
          {open ? <ChevronDown size={14} strokeWidth={1.75} /> : <ChevronRight size={14} strokeWidth={1.75} />}
        </span>
      </button>
      {open && (
        <>
          {lineWater && (
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs text-ink-3">
              <span className="tnum">{lineName} · last reading {readingText(lineWater)}</span>
              <button type="button" className="lnk font-medium" onClick={useThese}>Use these</button>
            </div>
          )}
          <div className="grid grid-cols-2 gap-2">
            {WATER_FIELDS.map((field) => (
              <NumberField key={field.key} id={field.id} label={field.label} value={value[field.key]} onChange={(next) => onChange({ ...value, [field.key]: next })} />
            ))}
          </div>
        </>
      )}
    </section>
  )
}

export function WaterReadOnly({ water, severities }: { water: WaterReadings; severities: Record<string, string> }) {
  const rows: { label: string; text: string | null; key?: string }[] = [
    { label: 'Temperature', text: water.temp_c === null ? null : `${water.temp_c.toFixed(1)} °C`, key: 'temp' },
    { label: 'Salinity', text: water.salinity_ppt === null ? null : `${water.salinity_ppt} ppt` },
    { label: 'pH', text: water.ph === null ? null : water.ph.toFixed(2), key: 'ph' },
    { label: 'Ω aragonite', text: water.omega_arag === null ? null : water.omega_arag.toFixed(1), key: 'omega' },
    { label: 'Oxygen', text: water.do_mgl === null ? null : `${water.do_mgl.toFixed(1)} mg/L`, key: 'oxygen' },
  ]
  const present = rows.filter((r) => r.text !== null)
  const color = (key?: string) => {
    const severity = key ? severities[key] : undefined
    if (severity === 'critical') return '#B42318'
    if (severity === 'risk') return '#B54708'
    if (severity === 'watch') return '#8E6206'
    return '#0F1A20'
  }
  return (
    <PanelSection title="Water readings" label="Water readings">
      {present.length === 0 ? (
        <span className="text-[13px] text-ink-3">No water readings with this check.</span>
      ) : (
        <div className="flex flex-col">
          {present.map((row, index) => (
            <div key={row.label} className="flex min-h-7 items-center justify-between text-[13px]" style={{ borderTop: index === 0 ? '0' : '1px solid #EEF2F4' }}>
              <span className="text-ink-2">{row.label}</span>
              <span className="tnum font-medium" style={{ color: color(row.key) }}>{row.text}</span>
            </div>
          ))}
        </div>
      )}
    </PanelSection>
  )
}
