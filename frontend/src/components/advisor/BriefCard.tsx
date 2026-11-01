import { ArrowDown, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { AdvisorPage, AnalysisProgress, Priority } from '../../api/types'
import { KeepIds, Spinner } from '../ui'

function useElapsed(running: boolean) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    if (!running) return
    const started = Date.now()
    const timer = window.setInterval(() => setSeconds(Math.round((Date.now() - started) / 1000)), 1000)
    return () => {
      window.clearInterval(timer)
      setSeconds(0)
    }
  }, [running])
  return seconds
}

function PriorityRow({ item, number, onGo }: { item: Partial<Priority>; number: number; onGo: (ref: string) => void }) {
  return (
    <li className="appear flex gap-3 py-2.5 first:pt-0 last:pb-0 not-first:border-t not-first:border-divider">
      <span aria-hidden="true" className="tnum box-border grid h-[22px] w-[22px] flex-none place-items-center rounded-full border border-border-strong text-[11px] font-semibold text-ink-2">{number}</span>
      <div className="flex min-w-0 flex-1 flex-wrap items-start justify-between gap-x-4 gap-y-1">
        <div className="flex min-w-0 flex-[1_1_300px] flex-col gap-0.5">
          <span className="text-[13px] leading-[1.45] font-medium text-ink"><KeepIds text={item.action ?? ''} /></span>
          {item.why && <span className="text-[13px] leading-[1.45] text-ink-3"><KeepIds text={item.why} /></span>}
        </div>
        {item.ref && (
          <button type="button" className="lnk flex-none text-xs no-underline hover:underline" onClick={() => onGo(item.ref as string)}>
            <span className="inline-flex items-center gap-1">Go to steps<ArrowDown size={12} strokeWidth={2} aria-hidden="true" /></span>
          </button>
        )}
      </div>
    </li>
  )
}

function Reading({ text, lookingAt, seconds }: { text: string; lookingAt: string[]; seconds: number }) {
  return (
    <div role="status" className="flex flex-col gap-3">
      <div className="flex items-start gap-2.5">
        <span className="mt-[3px] flex-none"><Spinner /></span>
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-sm leading-[1.45] text-ink">Claude is reading {text}.</span>
          <span className="tnum flex min-h-[18px] flex-wrap items-center gap-x-1.5 text-xs text-ink-4">
            {seconds > 0 && <span>{seconds} s</span>}
            {lookingAt.length > 0 && (
              <>
                <span aria-hidden="true" className="text-faint">·</span>
                <span>Now looking at</span>
                {lookingAt.map((id) => <span key={id} className="mono rounded-small bg-muted-bg px-1.5 py-px text-[11px] font-semibold text-ink-2">{id}</span>)}
              </>
            )}
          </span>
        </div>
      </div>
      <div aria-hidden="true" className="flex animate-pulse flex-col gap-2 motion-reduce:animate-none">
        <span className="h-3 w-[86%] rounded-small bg-muted-bg" />
        <span className="h-3 w-[72%] rounded-small bg-muted-bg" />
        <span className="h-3 w-[44%] rounded-small bg-muted-bg" />
      </div>
    </div>
  )
}

/** Today's brief: Claude's read of the whole hatchery. The rest of the page works without it. */
export function BriefCard({ page, progress, running, error, onRun, onGo }: {
  page: AdvisorPage
  progress: AnalysisProgress | null
  running: boolean
  error: string | null
  onRun: (force: boolean) => void
  onGo: (ref: string) => void
}) {
  const seconds = useElapsed(running)
  const written = progress?.analysis ?? null
  const stored = page.analysis
  const headline = written?.headline ?? (running ? null : stored?.headline)
  const brief = written?.brief ?? (running ? null : stored?.brief)
  const priorities: Partial<Priority>[] = written?.do_first ?? (running ? [] : stored?.do_first ?? [])
  const reading = running && !written?.headline
  const staleOnly = !running && !page.analysis_fresh && !!stored

  return (
    <section aria-label="Today's brief" aria-busy={running} className="flex flex-col gap-3 rounded-card border border-line p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">Today's brief</h2>
          <span className="tag !border-[#B9D0DD] !text-brand">Written by Claude</span>
        </div>
        {!running && (
          <button type="button" className="ghost !h-7 !gap-1.5 !px-2 !text-xs" onClick={() => onRun(true)}>
            <RefreshCw size={12} strokeWidth={2} aria-hidden="true" />
            {stored ? 'Run again' : 'Run analysis'}
          </button>
        )}
      </div>

      {reading && <Reading text={page.reading_text} lookingAt={progress?.looking_at ?? []} seconds={seconds} />}

      {!reading && headline && (
        <p className="m-0 text-[17px] leading-[1.35] font-semibold tracking-[-0.01em] [text-wrap:pretty]"><KeepIds text={headline} /></p>
      )}
      {!reading && brief && <p className="m-0 text-sm leading-[1.55] text-ink-2"><KeepIds text={brief} /></p>}

      {!reading && priorities.length > 0 && (
        <div className="flex flex-col gap-2 border-t border-divider pt-3">
          <h3 className="text-[13px] font-semibold">Do these first</h3>
          <ol className="m-0 flex list-none flex-col p-0">
            {priorities.filter((item) => item.action).map((item, index) => <PriorityRow key={index} item={item} number={index + 1} onGo={onGo} />)}
          </ol>
        </div>
      )}

      {!running && !stored && !error && (
        <p className="m-0 text-[13px] leading-[1.5] text-ink-3">Claude reads {page.reading_text}, then says what matters most today.</p>
      )}
      {error && <p role="alert" className="m-0 text-[13px] text-critical-text">{error}</p>}

      {!running && stored && (
        <span className="flex flex-wrap items-center gap-x-1.5 text-xs text-ink-4">
          {staleOnly ? <span className="font-medium text-watch-text">Written before the latest changes</span> : <span>From your checks, water readings and decisions</span>}
          <span aria-hidden="true" className="text-faint">·</span>
          <span>{stored.when_text}</span>
        </span>
      )}
      {running && !reading && (
        <span role="status" className="flex items-center gap-2 text-xs text-ink-4"><Spinner />Still writing</span>
      )}
    </section>
  )
}
