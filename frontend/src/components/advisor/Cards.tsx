import { ChevronDown } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { DecisionView, InsightCard, RiskCard, YieldCard } from '../../api/types'
import { ActionRow } from '../inspector/ActionRows'
import { KeepIds, StatusPill } from '../ui'
import { TileRow } from './Tile'

function TankLinks({ ids }: { ids: string[] }) {
  return (
    <span className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
      {ids.map((id) => (
        <Link key={id} to={`/tanks/${id}`} onClick={(event) => event.stopPropagation()} className="mono inline-flex items-center rounded-small bg-muted-bg px-1.5 py-0.5 text-xs font-semibold text-ink no-underline hover:bg-line max-[660px]:min-h-11 max-[660px]:px-3">{id}</Link>
      ))}
    </span>
  )
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex max-w-[170px] flex-none flex-col items-end gap-0.5 text-right max-[660px]:max-w-none max-[660px]:items-start max-[660px]:text-left">
      <span className="tnum text-xl font-semibold tracking-[-0.015em]">{value}</span>
      <span className="text-xs leading-[1.3] text-ink-4">{label}</span>
    </div>
  )
}

function Steps({ steps, title = 'What to do', left }: { steps: DecisionView[]; title?: string; left: number }) {
  if (steps.length === 0) return null
  return (
    <div className="flex flex-col border-t border-divider px-4 pt-3 pb-1">
      <div className="flex items-baseline justify-between gap-2 pb-0.5">
        <h4 className="text-[13px] font-semibold">{title}</h4>
        <span className="text-xs text-ink-4">{left === 0 ? 'All decided' : `${left} to decide`}</span>
      </div>
      {steps.map((step, index) => <ActionRow key={step.id ?? step.action} action={step} number={index + 1} divider={index > 0} />)}
    </div>
  )
}

function Source({ text }: { text: string | null }) {
  if (!text) return null
  return <span className="text-[11px] text-ink-4">Source: {text}</span>
}

export interface Fold {
  open: boolean
  onToggle: () => void
}

/** A card that shows the point and its next step closed, and everything behind them open. */
function FoldCard({ id, title, fold, top, side, summary, children }: {
  id?: string
  title: string
  fold: Fold
  top?: ReactNode
  side?: ReactNode
  summary: ReactNode
  children: ReactNode
}) {
  const { open, onToggle } = fold
  return (
    <article id={id} aria-label={title} className="scroll-mt-4 rounded-card border border-line">
      {/* The whole header toggles for a mouse; the title is the real button for a keyboard or screen reader */}
      <div className="rowbtn flex cursor-pointer items-start gap-3 rounded-card p-4" onClick={onToggle}>
        <div className="flex min-w-0 flex-1 flex-wrap items-start justify-between gap-x-6 gap-y-3">
          <div className="flex min-w-0 flex-[1_1_320px] flex-col gap-2">
            {top && <div className="flex flex-wrap items-center gap-2">{top}</div>}
            <h3 className="text-[15px] leading-[1.3] font-semibold [text-wrap:balance]">
              <button type="button" aria-expanded={open} className="cursor-pointer border-0 bg-transparent p-0 text-left font-semibold" onClick={(event) => { event.stopPropagation(); onToggle() }}>
                {title}
              </button>
            </h3>
            {summary}
          </div>
          {side}
        </div>
        <ChevronDown size={16} strokeWidth={1.75} aria-hidden="true" className="mt-0.5 flex-none text-ink-4 transition-transform" style={{ transform: open ? 'rotate(180deg)' : 'none' }} />
      </div>
      {open && <div className="appear">{children}</div>}
    </article>
  )
}

/** The tanks, then the next step still waiting: readable with the card closed. */
function Summary({ ids, steps, open }: { ids: string[]; steps: DecisionView[]; open: boolean }) {
  const next = steps.find((step) => step.status === 'pending')
  return (
    <div className="flex flex-col gap-1.5">
      <TankLinks ids={ids} />
      {!open && steps.length > 0 && (
        <span className="text-[13px] leading-[1.45] text-ink-2">
          {next ? <><span className="font-medium text-ink">Next:</span> {next.title}</> : 'All steps decided'}
        </span>
      )}
    </div>
  )
}

export function RiskCardView({ risk, fold }: { risk: RiskCard; fold: Fold }) {
  const single = risk.tank_ids.length === 1 ? risk.tank_ids[0] : null
  return (
    <FoldCard
      id={risk.id} title={risk.title} fold={fold}
      top={<><StatusPill level={risk.level} /><span className="tag">Rules-based</span></>}
      side={<Stat value={risk.at_stake_text} label="larvae at stake" />}
      summary={<Summary ids={risk.tank_ids} steps={risk.steps} open={fold.open} />}
    >
      <div className="flex flex-col gap-3 px-4 pb-4">
        <TileRow tiles={risk.tiles} />
        <div className="flex flex-col gap-1.5">
          <p className="m-0 text-[13px] leading-[1.5] text-ink"><span className="font-medium">{risk.forecast}</span>{risk.outlook ? <> <KeepIds text={risk.outlook} /></> : null}</p>
          <p className="m-0 text-[13px] leading-[1.5] text-ink-2"><KeepIds text={risk.why} /></p>
          <Source text={risk.source} />
        </div>
      </div>
      <Steps steps={risk.steps} left={risk.steps_left} />
      {single && (
        <div className="border-t border-divider px-4 py-2.5 text-[13px]">
          <Link to={`/checks/new?tank=${single}`} className="text-brand underline-offset-2">New check for {single}</Link>
          <span className="text-ink-4"> to see if it's getting better or worse</span>
        </div>
      )}
    </FoldCard>
  )
}

export function YieldCardView({ item, fold }: { item: YieldCard; fold: Fold }) {
  return (
    <FoldCard
      id={item.id} title={item.title} fold={fold}
      top={<span className="tag">Rules-based</span>}
      side={<Stat value={item.stat_text} label={item.stat_label} />}
      summary={<Summary ids={item.tank_ids} steps={item.steps} open={fold.open} />}
    >
      <div className="flex flex-col gap-3 px-4 pb-4">
        {item.tiles.length > 0 && <TileRow tiles={item.tiles} />}
        <div className="flex flex-col gap-1.5">
          <p className="m-0 text-[13px] leading-[1.5] text-ink-2"><KeepIds text={item.why} /></p>
          <Source text={item.source} />
        </div>
      </div>
      <Steps steps={item.steps} left={item.steps_left} />
    </FoldCard>
  )
}

const CONFIDENCE = { low: 'Low confidence', medium: 'Medium confidence', high: 'High confidence' } as const

export function InsightCardView({ insight, fold }: { insight: InsightCard; fold: Fold }) {
  const left = insight.step.status === 'pending' ? 1 : 0
  return (
    <FoldCard
      title={insight.title} fold={fold}
      top={<><span className="tag !border-[#B9D0DD] !text-brand">Found by Claude</span><span className="tag">{CONFIDENCE[insight.confidence]}</span></>}
      summary={<Summary ids={insight.tank_ids} steps={[insight.step]} open={fold.open} />}
    >
      <div className="flex flex-col gap-3 px-4 pb-4">
        <p className="m-0 text-[13px] leading-[1.5] text-ink-2"><KeepIds text={insight.body} /></p>
        <div className="flex flex-col gap-1.5">
          <span className="text-xs text-ink-4">Readings behind this, each checked against your records</span>
          <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0">
            {insight.evidence.map((item) => (
              <li key={`${item.tank_id}-${item.label}-${item.when_text}`} className="tnum flex flex-wrap items-baseline gap-x-1.5 rounded-small border border-divider px-2 py-1 text-xs">
                <span className="mono font-semibold">{item.tank_id}</span>
                <span className="text-ink-3">{item.label}</span>
                <span className="font-medium text-ink">{item.value_text}</span>
                <span className="text-ink-4">{item.when_text}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <Steps steps={[insight.step]} title="Suggested step" left={left} />
    </FoldCard>
  )
}
