import { X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import type { Level } from '../api/types'
import { LEVEL } from '../lib/levels'
import { ToastContext } from './toastContext'

interface ToastMessage {
  id: number
  text: string
  level: Level
}

const AUTO_HIDE_MS = 6000

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastMessage | null>(null)
  const nextId = useRef(1)

  const show = useCallback((text: string, level: Level = 'ok') => {
    setToast({ id: nextId.current++, text, level })
  }, [])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(null), AUTO_HIDE_MS)
    return () => window.clearTimeout(timer)
  }, [toast])

  const value = useMemo(() => show, [show])
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed right-4 bottom-4 z-[70] flex max-w-[calc(100vw-32px)] flex-col items-end">
        {toast && (
          <div key={toast.id} role="status" className="appear pointer-events-auto flex items-center gap-2.5 rounded-card border border-line bg-white py-2.5 pr-2 pl-3 text-[13px] shadow-pop">
            <span className="h-2 w-2 flex-none rounded-full" style={{ background: LEVEL[toast.level].color }} />
            <span>{toast.text}</span>
            <button type="button" className="rowbtn grid h-6 w-6 flex-none place-items-center rounded-small border-0 bg-transparent text-ink-4" aria-label="Close message" onClick={() => setToast(null)}>
              <X size={14} strokeWidth={1.75} />
            </button>
          </div>
        )}
      </div>
    </ToastContext.Provider>
  )
}
