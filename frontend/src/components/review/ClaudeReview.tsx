import { useMutation } from '@tanstack/react-query'
import { postJSON } from '../../api/client'
import { useClaudeStatus } from '../../api/hooks'
import type { ClaudeOpinion, Detection } from '../../api/types'
import { OPINION_NAME, type Opinions, decideOpinion, pendingOpinions } from '../../lib/opinions'
import { Spinner } from '../ui'

const MAX_OBJECTS = 12

/** Review plus Ask Claude, under the counts. Ask Claude is absent when there is no API key. */
export function CheckActions({ photoRef, detections, totalUnsure, onOpinions, onReview }: {
  photoRef: string | number | null
  detections: Detection[]
  totalUnsure: number
  onOpinions: (photo: string | number, opinions: Opinions) => void
  onReview: () => void
}) {
  const status = useClaudeStatus()
  const unsure = detections.filter((d) => d.unsure && d.cls !== 'ignore' && !d.claude && d.source !== 'manual')
  const toSend = unsure.slice(0, MAX_OBJECTS)
  const ask = useMutation({
    mutationFn: (request: { photo: string | number; ids: number[] }) => postJSON<{ opinions: Opinions; cached: boolean }>(
      '/api/claude/second-opinion', { photo: request.photo, detection_ids: request.ids },
    ),
    // The tech may have moved to another photo by the time this returns, so the request says which photo it was
    onSuccess: (body, request) => onOpinions(request.photo, body.opinions),
  })

  if (totalUnsure === 0) return <span className="text-[13px] text-ink-3">Nothing left to check.</span>
  const canAsk = status.data?.enabled && toSend.length > 0 && photoRef !== null
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="tnum flex-1 text-[13px] text-ink-2">{totalUnsure} to check</span>
        <button type="button" className="ghost max-[660px]:!h-11" onClick={onReview}>Review</button>
        {canAsk && (
          <button type="button" className="ghost max-[660px]:!h-11" disabled={ask.isPending} onClick={() => { if (photoRef !== null) ask.mutate({ photo: photoRef, ids: toSend.map((d) => d.id) }) }}>
            {ask.isPending && <Spinner />}
            Ask Claude
          </button>
        )}
      </div>
      {canAsk && <span className="tnum text-xs text-ink-4">Sends {toSend.length} small {toSend.length === 1 ? 'crop' : 'crops'} to Claude.</span>}
      {ask.isError && <span role="alert" className="text-xs text-critical-text">{ask.error instanceof Error ? ask.error.message : "Claude didn't answer."}</span>}
    </div>
  )
}

export function OpinionList({ detections, onChange, onSelect }: {
  detections: Detection[]
  onChange: (next: Detection[]) => void
  onSelect: (id: number) => void
}) {
  const pending = pendingOpinions(detections)
  if (pending.length === 0) return null
  const decide = (id: number, decision: 'accepted' | 'kept') =>
    onChange(detections.map((d) => (d.id === id ? decideOpinion(d, decision) : d)))
  const acceptAll = () =>
    onChange(detections.map((d) => (d.claude && !d.claude.decided ? decideOpinion(d, 'accepted') : d)))
  return (
    <div className="flex flex-col rounded-card border border-line">
      <div className="flex items-center justify-between gap-2 px-3 py-2">
        <span className="text-xs font-medium text-ink-2">Claude's second opinion</span>
        <button type="button" className="lnk text-xs font-medium" onClick={acceptAll}>Accept all</button>
      </div>
      {pending.map((d) => {
        const opinion = d.claude as ClaudeOpinion
        return (
          <div key={d.id} className="flex flex-col gap-1.5 border-t border-divider px-3 py-2">
            <button type="button" className="cursor-pointer border-0 bg-transparent p-0 text-left text-[13px] leading-[1.4] hover:underline" onClick={() => onSelect(d.id)}>
              <span className="tnum font-medium">Larva {d.id}</span>
              <span className="text-ink-2"> · Claude: {OPINION_NAME[opinion.cls]} · {opinion.reason}</span>
              {opinion.confidence === 'low' && <span className="text-ink-4"> (low confidence)</span>}
            </button>
            <span className="flex gap-1.5">
              <button type="button" className="solid !h-7 !text-xs max-[660px]:!h-11" onClick={() => decide(d.id, 'accepted')}>Accept</button>
              <button type="button" className="ghost !h-7 !text-xs max-[660px]:!h-11" onClick={() => decide(d.id, 'kept')}>Keep</button>
            </span>
          </div>
        )
      })}
    </div>
  )
}
