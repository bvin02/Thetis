import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

const ICON = { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.75, 'aria-hidden': true } as const

const NAV: { to: string; label: string; end?: boolean; icon: ReactNode }[] = [
  {
    to: '/', label: 'Floor', end: true,
    icon: <svg {...ICON}><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="9" cy="9" r="2.5" /><circle cx="15.5" cy="9" r="2.5" /><path d="M3 14h18" /></svg>,
  },
  {
    to: '/tanks', label: 'Tanks',
    icon: <svg {...ICON}><ellipse cx="12" cy="6" rx="8" ry="3" /><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6" /></svg>,
  },
  {
    to: '/checks', label: 'Checks',
    icon: <svg {...ICON}><path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3" /></svg>,
  },
  {
    to: '/decisions', label: 'Decisions',
    icon: <svg {...ICON}><path d="M4 13h4l2 3h4l2-3h4" /><path d="M5 13l2-8h10l2 8v6H5z" /></svg>,
  },
  {
    to: '/photos', label: 'Photo library',
    icon: <svg {...ICON}><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="9" cy="11" r="2" /><path d="M21 17l-5-5-8 7" /></svg>,
  },
]

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-5 px-3 py-4">
      <div className="flex items-center gap-2.5 rounded-control px-2 py-1.5">
        <span className="grid h-7 w-7 flex-none place-items-center rounded-control bg-brand">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" aria-hidden="true">
            <circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3" />
          </svg>
        </span>
        <span className="flex min-w-0 flex-1 flex-col leading-[1.25]">
          <span className="truncate text-[13px] font-semibold">Northwind Shellfish</span>
          <span className="truncate text-xs text-ink-4">Thetis</span>
        </span>
      </div>

      <nav aria-label="Main" className="flex flex-col gap-0.5">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              `nav group flex h-8 items-center gap-2.5 rounded-control px-2.5 text-sm no-underline ${isActive ? 'font-medium text-ink' : 'text-ink-2'}`
            }
          >
            {({ isActive }) => (
              <>
                <span className={isActive ? 'text-brand' : ''}>{item.icon}</span>
                <span className="flex-1">{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto flex items-center gap-2.5 px-2.5 py-2">
        <span className="grid h-7 w-7 flex-none place-items-center rounded-full bg-[#D9E1E6] text-[11px] font-semibold text-ink-2">DO</span>
        <span className="flex flex-col leading-[1.25]">
          <span className="text-[13px] font-medium">Dana Ortiz</span>
          <span className="text-xs text-ink-4">Hatchery manager</span>
        </span>
      </div>
    </div>
  )
}
