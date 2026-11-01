import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTank } from '../api/hooks'
import type { DecisionView } from '../api/types'
import { ExplainBlock } from '../components/inspector/Explain'
import { ConditionTable, LatestCheck, RecommendedActions, RiskForecast, SurvivalChart } from '../components/inspector/Inspector'
import { TopBar } from '../components/shell/TopBar'
import { CloseBatchDialog, StartBatchDialog } from '../components/tank/BatchDialogs'
import { ChecksTable } from '../components/tank/ChecksTable'
import { TrendsCard } from '../components/tank/TrendsCard'
import { ErrorState, LoadingState, StatusPill } from '../components/ui'

const OUTCOME: Record<string, string> = {
  moved_to_setting: 'Moved to setting', harvested: 'Harvested', crashed: 'Crashed', discarded: 'Discarded',
}

function HistoryRow({ item, divider }: { item: DecisionView; divider: boolean }) {
  const approved = item.status === 'approved'
  return (
    <div className="flex flex-col gap-1 py-2.5" style={{ borderTop: divider ? '1px solid #EEF2F4' : '0' }}>
      <span className="text-[13px] font-medium" style={{ color: approved ? '#2E7D57' : '#3E4B53' }}>{approved ? item.done_text : 'Dismissed'}</span>
      <span className="text-[13px] leading-[1.45] text-ink-2">{item.title}</span>
      <span className="text-xs text-ink-4">{item.decided_text}</span>
      {item.note && <span className="text-xs leading-[1.45] text-ink-3">{item.note}</span>}
    </div>
  )
}

export default function TankPage() {
  const { id } = useParams()
  const query = useTank(id)
  const tank = query.data && query.data.id === id ? query.data : null
  const [dialog, setDialog] = useState<'start' | 'close' | null>(null)

  if (query.isError) return <><TopBar crumbs={['Tanks', id ?? '']} /><ErrorState error={query.error} onRetry={() => query.refetch()} /></>
  if (!tank) return <><TopBar crumbs={['Tanks', id ?? '']} /><LoadingState /></>

  const empty = tank.level === 'empty'
  return (
    <>
      <TopBar crumbs={['Tanks', tank.id]} newCheckHref={empty ? '/checks/new' : `/checks/new?tank=${tank.id}`} hideNewCheck />
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-7 pt-6 pb-5 max-[660px]:px-4">
        <div className="flex min-w-0 flex-[1_1_320px] flex-col gap-1">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="mono text-2xl font-semibold tracking-[-0.01em]">{tank.id}</h1>
            <StatusPill level={tank.level} large />
          </div>
          <span className="text-[13px] text-ink-2">
            {tank.age_text} · {tank.room_name}{tank.batch_code ? ` · Batch ${tank.batch_code}` : ''} · <span style={{ color: tank.line_alert ? '#B54708' : undefined }}>{tank.line_text}</span>
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {empty ? (
            <button type="button" className="solid max-[660px]:!h-11" onClick={() => setDialog('start')}>Start batch</button>
          ) : (
            <>
              <Link to={`/checks/new?tank=${tank.id}`} className="solid no-underline max-[660px]:!h-11">
                <Plus size={14} strokeWidth={2} aria-hidden="true" />
                New check
              </Link>
              <button type="button" className="ghost max-[660px]:!h-11" onClick={() => setDialog('close')}>Close batch</button>
            </>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-start gap-5 px-7 pb-7 max-[660px]:px-4">
        <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-5 max-[660px]:flex-[1_1_100%]">
          {empty ? (
            <section aria-label="Empty tank" className="flex flex-col items-center gap-3 rounded-card border border-line px-6 py-14 text-center">
              <span className="text-sm font-semibold">{tank.status === 'cleaning' ? `${tank.id} is being cleaned` : `${tank.id} is empty`}</span>
              <span className="max-w-[46ch] text-[13px] leading-normal text-ink-3">Start a batch to begin tracking survival, growth and water here.</span>
              <button type="button" className="ghost" onClick={() => setDialog('start')}>Start batch</button>
            </section>
          ) : (
            <>
              <TrendsCard tank={tank} />
              <ChecksTable checks={tank.checks} />
            </>
          )}
          {tank.past_batches.length > 0 && (
            <section aria-label="Past batches" className="rounded-card border border-line">
              <h2 className="border-b border-divider px-4 py-3 text-sm font-semibold">Past batches</h2>
              {tank.past_batches.map((batch, index) => (
                <div key={batch.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-[13px]" style={{ borderTop: index === 0 ? '0' : '1px solid #EEF2F4' }}>
                  <span className="font-medium">{batch.code}</span>
                  <span className="tnum text-ink-3">{batch.outcome ? OUTCOME[batch.outcome] ?? batch.outcome : 'Closed'}{batch.closed_text ? ` · ${batch.closed_text}` : ''}</span>
                </div>
              ))}
            </section>
          )}
        </div>

        <aside aria-label={`${tank.id} details`} className="flex min-w-0 flex-[1_1_378px] flex-col rounded-card border border-line min-[1220px]:max-w-[402px]">
          {tank.latest_check && <div className="pt-4"><LatestCheck tank={tank} /></div>}
          <RiskForecast tank={tank} />
          <ExplainBlock tankId={tank.id} checkId={tank.latest_check_id} />
          <ConditionTable tank={tank} />
          <SurvivalChart tank={tank} />
          <RecommendedActions tank={tank} />
          {tank.decision_history.length > 0 && (
            <section aria-label="Decision history" className="flex flex-col border-t border-divider px-4 pt-4 pb-1.5">
              <h3 className="pb-1 text-[13px] font-semibold">Decision history</h3>
              {tank.decision_history.map((item, index) => <HistoryRow key={item.id} item={item} divider={index > 0} />)}
            </section>
          )}
        </aside>
      </div>

      {dialog === 'start' && <StartBatchDialog tankId={tank.id} onClose={() => setDialog(null)} />}
      {dialog === 'close' && tank.batch && (
        <CloseBatchDialog batchId={tank.batch.id} code={tank.batch.code} tankId={tank.id} spawnDate={tank.batch.spawn_date} onClose={() => setDialog(null)} />
      )}
    </>
  )
}
