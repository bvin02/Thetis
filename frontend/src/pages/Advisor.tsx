import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useAdvisor } from '../api/hooks'
import type { AdvisorPage as AdvisorData } from '../api/types'
import { AskPanel } from '../components/advisor/AskPanel'
import { BriefCard } from '../components/advisor/BriefCard'
import { InsightCardView, RiskCardView, YieldCardView } from '../components/advisor/Cards'
import { ForecastCard } from '../components/advisor/ForecastCard'
import { PlantCard } from '../components/advisor/PlantCard'
import { useAnalysis } from '../components/advisor/useAnalysis'
import { TopBar } from '../components/shell/TopBar'
import { EmptyState, ErrorState, LoadingState, Spinner } from '../components/ui'

function Metric({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-xs text-ink-4">{label}</dt>
      <dd className="tnum text-xl font-semibold tracking-[-0.015em]">
        {value}
        {unit && <span className="text-[13px] font-normal tracking-normal text-ink-4">{unit}</span>}
      </dd>
    </div>
  )
}

function SectionTitle({ title, children }: { title: string; children: string }) {
  return (
    <div className="flex flex-col gap-1">
      <h2 className="text-[17px] font-semibold tracking-[-0.01em]">{title}</h2>
      <p className="m-0 max-w-[68ch] text-[13px] leading-[1.5] text-ink-3">{children}</p>
    </div>
  )
}

function Finding({ running }: { running: boolean }) {
  if (!running) return null
  return <span role="status" className="flex items-center gap-2 rounded-card border border-dashed border-line px-4 py-3 text-[13px] text-ink-3"><Spinner />Claude is looking for anything the rules missed.</span>
}

/**
 * Which cards are open. The first of each kind starts open, so the page shows what a card holds; the rest are closed
 * until asked for, so every risk and suggestion fits on a screen or two.
 */
function useOpenCards(firstOpen: string[]) {
  const [changed, setChanged] = useState<Record<string, boolean>>({})
  const isOpen = (id: string) => changed[id] ?? firstOpen.includes(id)
  const toggle = (id: string) => setChanged((now) => ({ ...now, [id]: !(now[id] ?? firstOpen.includes(id)) }))
  const openAndGo = useCallback((id: string) => {
    setChanged((now) => ({ ...now, [id]: true }))
    // After the card has opened, so it scrolls to where it really ends up
    window.requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }, [])
  return { isOpen, toggle, openAndGo }
}

function Content({ data }: { data: AdvisorData }) {
  const { progress, running, error, start } = useAnalysis(data)
  const insights = running ? [] : data.analysis?.insights ?? []
  const riskInsights = insights.filter((i) => i.kind === 'crash_risk')
  const yieldInsights = insights.filter((i) => i.kind === 'yield')
  const claudeOn = data.claude.enabled
  const { totals, forecast } = data
  const { isOpen, toggle, openAndGo } = useOpenCards([
    data.risks[0]?.id, data.opportunities[0]?.id, riskInsights[0]?.title, yieldInsights[0]?.title,
  ].filter((id): id is string => !!id))
  const fold = (id: string) => ({ open: isOpen(id), onToggle: () => toggle(id) })

  // Arriving from the Floor's "See how"
  const { hash } = useLocation()
  const arrived = useRef(false)
  useEffect(() => {
    if (arrived.current || !hash) return
    arrived.current = true
    openAndGo(decodeURIComponent(hash.slice(1)))
  }, [hash, openAndGo])

  return (
    <>
      <section aria-label="Summary" className="flex flex-col gap-3 px-7 pt-7 max-[660px]:px-4 max-[660px]:pt-5">
        <h1 className="text-[28px] leading-[1.15] font-semibold tracking-[-0.025em] [text-wrap:balance]">{data.headline}</h1>
        <p className="m-0 max-w-[72ch] text-[15px] leading-[1.55] text-ink-2">
          Thetis reads every check and water reading, flags what could turn into a crash, says how to head it off, and finds where more larvae can make it through. A person approves every step. Nothing acts on equipment.
        </p>
        <dl className="mt-2 flex flex-wrap gap-x-12 gap-y-4 max-[660px]:gap-x-8">
          <Metric label="Larvae in tanks at risk" value={totals.at_risk_text} unit={` of ${totals.total_live_text}`} />
          <Metric label="On course to eyed stage" value={totals.on_course_text} />
          <Metric label={forecast.pace ? `Possible at ${forecast.pace.tank_id}'s pace` : 'Possible'} value={totals.possible_text} unit={` ${totals.gain_text}`} />
          <Metric label="Steps to decide" value={String(totals.steps_waiting)} />
        </dl>
        {claudeOn && (
          <a href="#ask" className="ghost self-start no-underline min-[1276px]:hidden max-[660px]:!h-11">Ask Thetis a question</a>
        )}
      </section>

      <div className="flex flex-wrap items-start gap-5 px-7 pt-6 pb-7 max-[660px]:px-4">
        <div className="flex min-w-0 flex-[999_1_600px] flex-col gap-6 max-[660px]:flex-[1_1_100%]">
          {claudeOn && <BriefCard page={data} progress={progress} running={running} error={error} onRun={start} onGo={openAndGo} />}

          <section aria-label="Crash risks" className="flex flex-col gap-3">
            <SectionTitle title="Crash risks">What could turn into a crash in the next few days, and how to head it off.</SectionTitle>
            {data.risks.length === 0 && riskInsights.length === 0 && (
              <div className="rounded-card border border-line"><EmptyState title="No crash risks right now">Every tank's last check looks normal.</EmptyState></div>
            )}
            {data.risks.map((risk) => <RiskCardView key={risk.id} risk={risk} fold={fold(risk.id)} />)}
            {riskInsights.map((insight) => <InsightCardView key={insight.title} insight={insight} fold={fold(insight.title)} />)}
            <Finding running={running} />
          </section>

          <section aria-label="Raise yield" className="flex flex-col gap-3">
            <SectionTitle title="Raise yield">Where this hatchery can get more larvae through to setting.</SectionTitle>
            {data.opportunities.length === 0 && yieldInsights.length === 0 && (
              <div className="rounded-card border border-line"><EmptyState title="No suggestions right now">New ones appear as checks come in.</EmptyState></div>
            )}
            {data.opportunities.map((item) => <YieldCardView key={item.id} item={item} fold={fold(item.id)} />)}
            {yieldInsights.map((insight) => <InsightCardView key={insight.title} insight={insight} fold={fold(insight.title)} />)}
            <ForecastCard forecast={forecast} />
          </section>
        </div>

        <aside aria-label="Ask and plant settings" className="flex min-w-0 flex-[1_1_378px] flex-col gap-5 min-[1276px]:max-w-[402px] min-[1276px]:self-stretch">
          {claudeOn && (
            <div id="ask" className="scroll-mt-4 bg-white min-[1276px]:sticky min-[1276px]:top-3 min-[1276px]:z-10">
              <AskPanel questions={data.questions} />
            </div>
          )}
          <PlantCard plant={data.plant} />
        </aside>
      </div>
    </>
  )
}

export default function AdvisorPage() {
  const query = useAdvisor()
  const data = query.data
  if (query.isError) return <><TopBar crumbs={['Advisor']} /><ErrorState error={query.error} onRetry={() => query.refetch()} /></>
  if (!data) return <><TopBar crumbs={['Advisor']} /><LoadingState /></>
  if (!data.seeded) {
    return (
      <>
        <TopBar crumbs={['Advisor']} />
        <EmptyState title="No hatchery set up yet">
          Stop the servers and run <span className="mono">npm run seed</span> to load the example hatchery.
        </EmptyState>
      </>
    )
  }
  return (
    <>
      <TopBar crumbs={['Advisor']} />
      <Content data={data} />
    </>
  )
}
