import { Menu, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { ToastProvider } from '../Toast'
import { CommandPalette } from './CommandPalette'
import { ErrorBoundary } from './ErrorBoundary'
import { PaletteContext } from './paletteContext'
import { Sidebar } from './Sidebar'

export default function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const { pathname } = useLocation()

  // A new page starts at its top, wherever the last one was scrolled to
  useEffect(() => { window.scrollTo(0, 0) }, [pathname])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setPaletteOpen((open) => !open)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <ToastProvider>
    <PaletteContext.Provider value={() => setPaletteOpen(true)}>
    <div className="flex min-h-full bg-canvas">
      <aside className="sticky top-0 hidden h-screen w-[216px] flex-none min-[900px]:block">
        <Sidebar />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="sticky top-0 z-40 flex h-12 items-center gap-2 border-b border-line bg-canvas px-3 min-[900px]:hidden">
          <button
            type="button"
            className="ghost !h-11 !w-11 !p-0 !border-0 !bg-transparent"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
          >
            {menuOpen ? <X size={18} strokeWidth={1.75} /> : <Menu size={18} strokeWidth={1.75} />}
          </button>
          <span className="grid h-6 w-6 flex-none place-items-center rounded-small bg-brand">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" aria-hidden="true">
              <circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3" />
            </svg>
          </span>
          <span className="text-[13px] font-semibold">Thetis</span>
        </div>

        {menuOpen && (
          <div className="fixed inset-x-0 bottom-0 top-12 z-40 bg-canvas min-[900px]:hidden">
            <Sidebar onNavigate={() => setMenuOpen(false)} />
          </div>
        )}

        <main className="my-2 mr-2 ml-2 flex min-w-0 flex-1 flex-col rounded-panel border border-line bg-panel shadow-panel min-[900px]:ml-0">
          <ErrorBoundary resetKey={pathname}>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
    {paletteOpen && <CommandPalette onClose={() => setPaletteOpen(false)} />}
    </PaletteContext.Provider>
    </ToastProvider>
  )
}
