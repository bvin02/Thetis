import { Check, X } from 'lucide-react'
import { useState } from 'react'
import type { DecisionVerb } from '../../api/hooks'
import { useDecide, useSetPlant } from '../../api/hooks'
import type { DecisionView, Dose } from '../../api/types'
import { Spinner } from '../ui'

/** The buffer dose, calculated from this line's water. Switching product recalculates it everywhere. */
function DoseBox({ dose }: { dose: Dose }) {
  const setPlant = useSetPlant()
  return (
    <div className="flex flex-col gap-1.5 rounded-control border border-line bg-subtle px-3 py-2.5">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5">
        <span className="tnum text-[15px] font-semibold tracking-[-0.01em]">{dose.per_1000l_text}</span>
        <label className="flex min-w-0 items-center gap-2 text-xs text-ink-4">
          <span className="sr-only">Buffer this plant uses</span>
          <select
            className="field !h-7 !w-auto min-w-0 !bg-white !text-xs max-[660px]:!h-11"
            value={dose.buffer}
            disabled={setPlant.isPending}
            onChange={(event) => setPlant.mutate({ buffer: event.target.value })}
          >
            {dose.options.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
          </select>
        </label>
      </div>
      {dose.total_text && <span className="tnum text-[13px] text-ink-2">{dose.total_text}</span>}
      <span className="tnum text-[13px] text-ink-2">{dose.effect_text}</span>
      <span className="text-xs leading-[1.45] text-ink-4">{dose.note}</span>
    </div>
  )
}

export function ActionRow({ action, number, divider, showContext }: {
  action: DecisionView
  number: number
  divider: boolean
  showContext?: boolean
}) {
  const decide = useDecide()
  const [running, setRunning] = useState<DecisionVerb | null>(null)
  const [error, setError] = useState<string | null>(null)

  const run = (verb: DecisionVerb) => {
    setRunning(verb)
    setError(null)
    decide.mutate({ action, verb }, {
      onError: (e) => setError(e instanceof Error ? e.message : 'That did not save.'),
      onSettled: () => setRunning(null),
    })
  }

  const pending = action.status === 'pending'
  const approved = action.status === 'approved'
  const dismissed = action.status === 'dismissed'
  const busy = running !== null

  return (
    <div className="flex gap-3 py-3" style={{ borderTop: divider ? '1px solid #EEF2F4' : '0' }}>
      <span
        aria-hidden="true"
        className="tnum box-border grid h-[22px] w-[22px] flex-none place-items-center rounded-full border text-[11px] font-semibold"
        style={{
          borderColor: approved ? '#A9D3B8' : '#CCD5DB',
          background: approved ? '#EEF7F1' : '#FFFFFF',
          color: approved ? '#2E7D57' : '#3E4B53',
        }}
      >
        {pending && number}
        {approved && <Check size={12} strokeWidth={3} />}
        {dismissed && <X size={12} strokeWidth={3} />}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex flex-col gap-1">
          <span className="text-[13px] leading-[1.45]" style={{ color: pending ? '#0F1A20' : '#66737B' }}>{action.title}</span>
          {pending && action.how && <span className="text-xs leading-[1.5] text-ink-3">{action.how}</span>}
        </div>
        {pending && action.dose && <DoseBox dose={action.dose} />}
        {pending ? (
          <span className="flex flex-wrap gap-2">
            <button type="button" className="solid" disabled={busy} onClick={() => run('approve')} aria-busy={running === 'approve'}>
              {running === 'approve' && <Spinner light />}
              {action.cta}
            </button>
            <button type="button" className="ghost" disabled={busy} onClick={() => run('dismiss')} aria-label={`Dismiss: ${action.title}`}>
              {running === 'dismiss' && <Spinner />}
              Dismiss
            </button>
          </span>
        ) : (
          <span role="status" className="appear flex min-h-8 flex-wrap items-center gap-x-2.5 gap-y-1 text-[13px]">
            <span className="font-medium" style={{ color: approved ? '#2E7D57' : '#3E4B53' }}>{approved ? action.done_text : 'Dismissed'}</span>
            <span className="text-xs text-ink-4">{action.decided_text}</span>
            <button type="button" className="lnk text-xs" disabled={busy} onClick={() => run('undo')} aria-label={`Undo: ${action.title}`}>Undo</button>
          </span>
        )}
        {showContext && action.note && <span className="text-xs leading-[1.45] text-ink-3">{action.note}</span>}
        {error && <span role="alert" className="text-xs text-critical-text">{error}</span>}
      </div>
    </div>
  )
}
