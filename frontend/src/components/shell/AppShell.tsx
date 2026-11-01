import { Menu, X } from 'lucide-react'
import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { ToastProvider } from '../Toast'
import { Sidebar } from './Sidebar'

export default function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false)
  return (
    <ToastProvider>
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
          <Outlet />
        </main>
      </div>
    </div>
    </ToastProvider>
  )
}
