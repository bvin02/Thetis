import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { postJSON } from '../../api/client'
import { useInvalidateAll } from '../../api/hooks'
import { useToast } from '../toastContext'
import { Dialog } from '../Dialog'
import { Spinner } from '../ui'

function today() {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function Field({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs text-ink-4">{label}</label>
      {children}
    </div>
  )
}

export function StartBatchDialog({ tankId, onClose }: { tankId: string; onClose: () => void }) {
  const [code, setCode] = useState('')
  const [spawnDate, setSpawnDate] = useState(today())
  const [stocked, setStocked] = useState('')
  const invalidate = useInvalidateAll()
  const toast = useToast()
  const start = useMutation({
    mutationFn: () => postJSON('/api/batches', { tank_id: tankId, code, spawn_date: spawnDate, stocked: Number(stocked) }),
    onSuccess: async () => {
      await invalidate()
      toast(`Batch ${code} started in ${tankId}.`)
      onClose()
    },
  })
  const valid = code.trim() !== '' && spawnDate !== '' && Number(stocked) > 0
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (valid) start.mutate()
  }
  return (
    <Dialog title={`Start a batch in ${tankId}`} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3 p-4">
        <Field id="batch-code" label="Batch code">
          <input id="batch-code" className="field max-[660px]:!h-11" value={code} onChange={(e) => setCode(e.target.value)} placeholder="NW-1030" />
        </Field>
        <Field id="spawn-date" label="Spawn date">
          <input id="spawn-date" type="date" max={today()} className="field tnum max-[660px]:!h-11" value={spawnDate} onChange={(e) => setSpawnDate(e.target.value)} />
        </Field>
        <Field id="stocked" label="Number stocked">
          <input id="stocked" type="number" min="1" step="1" inputMode="numeric" className="field tnum max-[660px]:!h-11" value={stocked} onChange={(e) => setStocked(e.target.value)} placeholder="10000000" />
        </Field>
        {start.isError && <p role="alert" className="m-0 text-[13px] text-critical-text">{start.error instanceof Error ? start.error.message : "That didn't save."}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" className="ghost max-[660px]:!h-11" onClick={onClose}>Cancel</button>
          <button type="submit" className="solid max-[660px]:!h-11" disabled={!valid || start.isPending}>
            {start.isPending && <Spinner light />}
            Start batch
          </button>
        </div>
      </form>
    </Dialog>
  )
}

const OUTCOMES = [
  { value: 'moved_to_setting', label: 'Moved to setting' },
  { value: 'harvested', label: 'Harvested' },
  { value: 'crashed', label: 'Crashed' },
  { value: 'discarded', label: 'Discarded' },
]

export function CloseBatchDialog({ batchId, code, tankId, spawnDate, onClose }: { batchId: number; code: string; tankId: string; spawnDate: string; onClose: () => void }) {
  const [outcome, setOutcome] = useState('moved_to_setting')
  const [closedOn, setClosedOn] = useState(today())
  const [note, setNote] = useState('')
  const invalidate = useInvalidateAll()
  const toast = useToast()
  const close = useMutation({
    mutationFn: () => postJSON(`/api/batches/${batchId}/close`, { outcome, closed_on: closedOn, note }),
    onSuccess: async () => {
      await invalidate()
      toast(`Batch ${code} closed. ${tankId} is now empty.`)
      onClose()
    },
  })
  const submit = (event: FormEvent) => {
    event.preventDefault()
    close.mutate()
  }
  return (
    <Dialog title={`Close batch ${code}`} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-3 p-4">
        <Field id="outcome" label="Outcome">
          <select id="outcome" className="field max-[660px]:!h-11" value={outcome} onChange={(e) => setOutcome(e.target.value)}>
            {OUTCOMES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </Field>
        <Field id="closed-on" label="Date">
          <input id="closed-on" type="date" min={spawnDate} max={today()} className="field tnum max-[660px]:!h-11" value={closedOn} onChange={(e) => setClosedOn(e.target.value)} />
        </Field>
        <Field id="close-note" label="Note (optional)">
          <textarea id="close-note" className="field" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
        <p className="m-0 text-xs leading-normal text-ink-4">Open decisions for {tankId} are dismissed with the batch. Line decisions stay open for the other tanks.</p>
        {close.isError && <p role="alert" className="m-0 text-[13px] text-critical-text">{close.error instanceof Error ? close.error.message : "That didn't save."}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" className="ghost max-[660px]:!h-11" onClick={onClose}>Cancel</button>
          <button type="submit" className="solid max-[660px]:!h-11" disabled={close.isPending || !closedOn}>
            {close.isPending && <Spinner light />}
            Close batch
          </button>
        </div>
      </form>
    </Dialog>
  )
}
