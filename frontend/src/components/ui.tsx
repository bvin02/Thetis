import { CircleAlert } from 'lucide-react'
import type { CSSProperties, ReactNode } from 'react'
import { ApiError } from '../api/client'
import type { Level } from '../api/types'
import { LEVEL, SWATCH } from '../lib/levels'

export function Spinner({ light = false }: { light?: boolean }) {
  return (
    <span
      className="spin"
      aria-hidden="true"
      style={light ? { borderColor: 'rgba(255,255,255,0.35)', borderTopColor: '#FFFFFF' } : undefined}
    />
  )
}

export function StatusPill({ level, large = false }: { level: Level; large?: boolean }) {
  const lv = LEVEL[level]
  return (
    <span
      className="inline-flex flex-none items-center gap-1.5 rounded-full font-medium whitespace-nowrap"
      style={{ height: large ? 24 : 22, padding: large ? '0 10px' : '0 8px', background: lv.pill, color: lv.text, fontSize: 12 }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: lv.color }} />
      {lv.label}
    </span>
  )
}

export function LevelSwatch({ level, size = 10, square = false }: { level: Level; size?: number; square?: boolean }) {
  const swatch = SWATCH[level]
  return (
    <span
      aria-hidden="true"
      className="box-border inline-block flex-none"
      style={{ width: size, height: size, borderRadius: square ? 3 : 999, background: swatch.background, border: swatch.border }}
    />
  )
}

export interface SegmentOption<T extends string> {
  value: T
  label: ReactNode
}

export function Segmented<T extends string>({ value, options, onChange, label, style }: {
  value: T
  options: SegmentOption<T>[]
  onChange: (value: T) => void
  label: string
  style?: CSSProperties
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex max-w-full rounded-control bg-muted-bg p-0.5" style={style}>
      {options.map((option) => {
        const active = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            className="seg h-7 cursor-pointer rounded-small border-0 px-3 text-xs font-medium whitespace-nowrap max-[660px]:h-11 max-[660px]:px-2"
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            style={{
              background: active ? '#FFFFFF' : 'transparent',
              boxShadow: active ? 'var(--shadow-seg-active)' : 'none',
              color: active ? '#0F1A20' : '#5F6C74',
            }}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof ApiError || error instanceof Error ? error.message : 'Something went wrong.'
  return (
    <div role="alert" className="flex flex-col items-start gap-3 px-7 py-10 max-[660px]:px-4">
      <div className="flex items-center gap-2 text-[15px] font-semibold">
        <CircleAlert size={16} strokeWidth={1.75} className="text-critical-text" aria-hidden="true" />
        Couldn't load this page
      </div>
      <p className="m-0 max-w-[60ch] text-[13px] leading-normal text-ink-2">{message}</p>
      {onRetry && <button type="button" className="ghost" onClick={onRetry}>Try again</button>}
    </div>
  )
}

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 px-7 py-10 text-[13px] text-ink-3 max-[660px]:px-4">
      <Spinner />
      {label}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-1 px-6 py-12 text-center">
      <span className="text-sm font-semibold">{title}</span>
      {children && <span className="max-w-[46ch] text-[13px] leading-normal text-ink-3">{children}</span>}
    </div>
  )
}
