import { X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'

/** A small modal. Esc and the backdrop close it, and focus moves in on open and back on close. */
export function Dialog({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const panel = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null
    panel.current?.querySelector<HTMLElement>('input, select, textarea, button')?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
      if (event.key !== 'Tab' || !panel.current) return
      const focusable = panel.current.querySelectorAll<HTMLElement>('input, select, textarea, button:not(:disabled)')
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      before?.focus()
    }
    // Runs once on open
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-[rgba(15,26,32,0.28)] p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <div ref={panel} role="dialog" aria-modal="true" aria-label={title} className="appear box-border flex max-h-full w-[420px] max-w-full flex-col overflow-y-auto rounded-panel border border-line bg-white shadow-pop">
        <div className="flex items-center justify-between gap-2 border-b border-divider px-4 py-3">
          <h2 className="text-sm font-semibold">{title}</h2>
          <button type="button" className="rowbtn grid h-7 w-7 flex-none place-items-center rounded-small border-0 bg-transparent text-ink-4 max-[660px]:h-11 max-[660px]:w-11" aria-label="Close" onClick={onClose}>
            <X size={14} strokeWidth={1.75} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
