import { useMutation } from '@tanstack/react-query'
import { postJSON } from '../../api/client'
import { useClaudeStatus } from '../review/ClaudeReview'
import { Spinner } from '../ui'

/** "Explain" under the risk forecast. Only asks Claude when clicked; hidden when Claude is off. */
export function ExplainBlock({ tankId, checkId }: { tankId: string; checkId: number | null }) {
  const status = useClaudeStatus()
  const explain = useMutation({
    mutationKey: ['explain', tankId, checkId],
    mutationFn: () => postJSON<{ text: string; cached: boolean; model: string }>('/api/claude/explain', { tank_id: tankId }),
  })
  if (!status.data?.enabled || checkId === null) return null
  return (
    <section aria-label="Explain" className="flex flex-col gap-2 border-t border-divider p-4">
      {explain.data ? (
        <div className="appear flex flex-col gap-1.5">
          <p className="m-0 text-[13px] leading-normal text-ink-2">{explain.data.text}</p>
          <span className="text-xs text-ink-4">Written by Claude from the numbers above</span>
        </div>
      ) : (
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-ink-4">Ask Claude to put these numbers in plain English.</span>
          <button type="button" className="ghost flex-none" disabled={explain.isPending} onClick={() => explain.mutate()}>
            {explain.isPending && <Spinner />}
            Explain
          </button>
        </div>
      )}
      {explain.isError && <span role="alert" className="text-xs text-critical-text">{explain.error instanceof Error ? explain.error.message : "Claude didn't answer."}</span>}
    </section>
  )
}
