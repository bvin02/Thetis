import type { Floor } from '../../api/types'

function Metric({ label, value, unit, valueColor }: { label: string; value: string; unit?: string; valueColor?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-xs text-ink-4">{label}</dt>
      <dd className="tnum text-xl font-semibold tracking-[-0.015em]" style={valueColor ? { color: valueColor } : undefined}>
        {value}
        {unit && <span className="text-[13px] font-normal tracking-normal text-ink-4">{unit}</span>}
      </dd>
    </div>
  )
}

export function Metrics({ metrics }: { metrics: Floor['metrics'] }) {
  const next = metrics.next_check
  return (
    <dl className="mt-2 flex flex-wrap gap-x-12 gap-y-4 max-[660px]:gap-x-8">
      <Metric label="Larvae in hatchery" value={metrics.larvae_value} unit={metrics.larvae_unit} />
      <Metric label="Tanks running" value={String(metrics.tanks_running)} unit={` of ${metrics.tanks_total}`} />
      <Metric label="Average survival" value={metrics.avg_survival === null ? '—' : String(metrics.avg_survival)} unit={metrics.avg_survival === null ? '' : '%'} />
      <Metric label="Decisions waiting" value={String(metrics.decisions_waiting)} />
      {next ? (
        <div className="flex flex-col gap-1">
          <dt className="text-xs text-ink-4">Next check</dt>
          <dd className="tnum text-xl font-semibold tracking-[-0.015em]">
            {next.tank_id}
            <span className="text-[13px] font-normal tracking-normal" style={{ color: next.overdue ? '#8E6206' : '#66737B', fontWeight: next.overdue ? 500 : 400 }}>
              {` · ${next.text}`}
            </span>
          </dd>
        </div>
      ) : (
        <Metric label="Next check" value="—" />
      )}
    </dl>
  )
}
