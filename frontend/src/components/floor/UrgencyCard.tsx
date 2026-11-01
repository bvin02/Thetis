import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Chip, YieldChip } from '../../api/types'
import { LEVEL } from '../../lib/levels'

function TankChip({ chip, selected, onPick }: { chip: Chip; selected: boolean; onPick: (id: string) => void }) {
  const lv = LEVEL[chip.level]
  return (
    <button
      type="button"
      className="chip flex min-h-8 items-center gap-2 rounded-control px-3 py-[5px] text-left text-[13px] text-ink max-[660px]:min-h-11"
      onClick={() => onPick(chip.id)}
      aria-pressed={selected}
      aria-label={`${chip.id}, ${chip.level_label}: ${chip.reason}`}
      style={{ border: `1px solid ${lv.chipBorder}`, background: lv.chip, boxShadow: selected ? '0 0 0 1.5px #0F1A20' : 'none' }}
    >
      <span className="h-2 w-2 flex-none rounded-full" style={{ background: lv.color }} />
      <span className="mono font-semibold">{chip.id}</span>
      <span className="font-medium" style={{ color: lv.text }}>{chip.level_label}</span>
      <span className="text-ink-3">{chip.chip}</span>
    </button>
  )
}

function UrgencyRow({ title, label, chips, selected, onPick, divider, emptyText }: {
  title: string; label: string; chips: Chip[]; selected: string | null; onPick: (id: string) => void; divider?: boolean; emptyText: string
}) {
  return (
    <div className={`flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 ${divider ? 'border-t border-divider' : ''}`}>
      <div className="flex w-[136px] flex-none flex-col gap-0.5">
        <span className="text-[13px] font-semibold">{title}</span>
        <span className="text-xs text-ink-4">{label}</span>
      </div>
      <div className="flex min-w-0 flex-[1_1_420px] flex-wrap gap-2">
        {chips.length === 0 && <span className="text-[13px] text-ink-4">{emptyText}</span>}
        {chips.map((chip) => (
          <TankChip key={chip.id} chip={chip} selected={chip.id === selected} onPick={onPick} />
        ))}
      </div>
    </div>
  )
}

function YieldRow({ label, chips, selected, onPick }: { label: string; chips: YieldChip[]; selected: string | null; onPick: (id: string) => void }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-divider px-4 py-3">
      <div className="flex w-[136px] flex-none flex-col gap-0.5">
        <span className="text-[13px] font-semibold">Raise yield</span>
        <span className="text-xs text-ink-4">{label}</span>
      </div>
      <div className="flex min-w-0 flex-[1_1_420px] flex-wrap items-center gap-2">
        {chips.length === 0 && <span className="text-[13px] text-ink-4">No suggestions right now.</span>}
        {chips.map((chip) => (
          <button
            key={`${chip.id}-${chip.chip}`}
            type="button"
            className="chip flex min-h-8 items-center gap-2 rounded-control border border-line bg-white px-3 py-[5px] text-left text-[13px] text-ink max-[660px]:min-h-11"
            onClick={() => onPick(chip.id)}
            aria-pressed={chip.id === selected}
            aria-label={`${chip.id}: ${chip.title}`}
            style={{ boxShadow: chip.id === selected ? '0 0 0 1.5px #0F1A20' : 'none' }}
          >
            <span className="mono font-semibold">{chip.id}</span>
            <span className="text-ink-3">{chip.chip}</span>
          </button>
        ))}
        <Link to="/advisor" className="ghost ml-auto no-underline max-[660px]:!h-11 max-[660px]:ml-0">
          Open Advisor
          <ArrowRight size={14} strokeWidth={2} aria-hidden="true" />
        </Link>
      </div>
    </div>
  )
}

export function UrgencyCard({ actNow, actLabel, monitor, monitorLabel, yieldLabel, yieldChips, selected, onPick }: {
  actNow: Chip[]; actLabel: string; monitor: Chip[]; monitorLabel: string; yieldLabel: string; yieldChips: YieldChip[]
  selected: string | null; onPick: (id: string) => void
}) {
  return (
    <div role="region" aria-label="Tanks by urgency" className="mt-1 rounded-card border border-line">
      <UrgencyRow title="Act now" label={actLabel} chips={actNow} selected={selected} onPick={onPick} emptyText="Nothing needs action right now." />
      <UrgencyRow title="Monitor" label={monitorLabel} chips={monitor} selected={selected} onPick={onPick} divider emptyText="No tanks on watch." />
      <YieldRow label={yieldLabel} chips={yieldChips} selected={selected} onPick={onPick} />
    </div>
  )
}
