import type { ReactNode } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { useFloor } from '../../api/hooks'
import { LevelSwatch } from '../ui'

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
  const { data } = useFloor()
  const location = useLocation()
  const activeRoom = location.pathname === '/' ? new URLSearchParams(location.search).get('room') : null
  const waiting = data?.decisions_waiting ?? 0
  const user = data?.user
  return (
    <div className="flex h-full flex-col gap-5 px-3 py-4">
      <div className="flex items-center gap-2.5 rounded-control px-2 py-1.5">
        <span className="grid h-7 w-7 flex-none place-items-center rounded-control bg-brand">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" aria-hidden="true">
            <circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3" />
          </svg>
        </span>
        <span className="flex min-w-0 flex-1 flex-col leading-[1.25]">
          <span className="truncate text-[13px] font-semibold">{data?.hatchery.name ?? 'Thetis'}</span>
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
              `nav flex h-8 items-center gap-2.5 rounded-control px-2.5 text-sm no-underline max-[899px]:h-11 ${isActive ? 'font-medium text-ink' : 'text-ink-2'}`
            }
          >
            {({ isActive }) => (
              <>
                <span className={isActive ? 'text-brand' : ''}>{item.icon}</span>
                <span className="flex-1">{item.label}</span>
                {item.to === '/decisions' && waiting > 0 && (
                  <span
                    aria-label={`${waiting} ${waiting === 1 ? 'decision' : 'decisions'} waiting`}
                    className="tnum box-border grid h-5 min-w-5 place-items-center rounded-full bg-ink px-1.5 text-[11px] font-semibold text-white"
                  >
                    {waiting}
                  </span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {data && data.rooms.length > 0 && (
        <div className="flex flex-col gap-0.5">
          <span className="px-2.5 pb-2 text-xs font-medium text-ink-4">Rooms</span>
          {data.rooms.map((room) => {
            const isActive = activeRoom === room.id
            return (
              <Link
                key={room.id}
                to={isActive ? '/' : `/?room=${room.id}`}
                onClick={onNavigate}
                aria-current={isActive ? 'page' : undefined}
                className={`nav flex h-8 items-center gap-2.5 rounded-control px-2.5 text-[13px] no-underline max-[899px]:h-11 ${isActive ? 'font-medium text-ink' : 'text-ink-2'}`}
              >
                <LevelSwatch level={room.worst_level} size={8} />
                <span className="flex-1">{room.name}</span>
                <span className="tnum text-xs text-ink-4">{room.tank_count}</span>
              </Link>
            )
          })}
        </div>
      )}

      {user && user.name && (
        <div className="mt-auto flex items-center gap-2.5 px-2.5 py-2">
          <span className="grid h-7 w-7 flex-none place-items-center rounded-full bg-[#D9E1E6] text-[11px] font-semibold text-ink-2">{user.initials}</span>
          <span className="flex flex-col leading-[1.25]">
            <span className="text-[13px] font-medium">{user.name}</span>
            <span className="text-xs text-ink-4">{user.role}</span>
          </span>
        </div>
      )}
    </div>
  )
}
