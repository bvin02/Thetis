import { useId } from 'react'
import type { LineView, RoomNav, TankSummary } from '../../api/types'
import { LEGEND, LEVEL, isProblem } from '../../lib/levels'
import { LevelSwatch, Segmented, StatusPill } from '../ui'

export type PlanView = 'plan' | 'table'

const INK = '#0F1A20'

function pct(value: number, total: number) {
  return `${Math.round((value / total) * 1000) / 10}%`
}

function CircleTank({ tank, selected }: { tank: TankSummary; selected: boolean }) {
  const { cx, cy, r } = tank.geom
  const lv = LEVEL[tank.level]
  const problem = isProblem(tank.level)
  const big = r > 32
  const dotOffset = big ? 26 : 22
  return (
    <g opacity={1}>
      <circle className="tk-sel" cx={cx} cy={cy} r={r + 7} fill="none" stroke={selected ? INK : 'transparent'} strokeWidth="1.75" />
      <circle
        className="tk-body" cx={cx} cy={cy} r={r}
        fill={selected && !problem ? '#F6F8F9' : lv.tint}
        stroke={lv.color} strokeWidth={lv.sw} strokeDasharray={tank.level === 'empty' ? '3 3' : 'none'}
      />
      <circle cx={cx} cy={cy} r={r - 8} fill="none" stroke="#E8EDF0" />
      <text x={cx} y={cy - 1} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="13" fontWeight="600" fill={INK}>{tank.id}</text>
      <text x={cx} y={cy + (big ? 13 : 12)} textAnchor="middle" fontSize="10.5" fill="#5F6C74">{tank.sub_text}</text>
      {problem && <circle cx={cx + dotOffset} cy={cy - dotOffset} r="5" fill={lv.color} stroke="#FFFFFF" strokeWidth="2" />}
      <text x={cx} y={cy + (big ? 51 : 45)} textAnchor="middle" fontSize="10.5">
        <tspan fill="#5F6C74">{tank.level === 'empty' ? '' : tank.live_text}</tspan>
        {problem && <tspan fill={lv.text} fontWeight="600">{` · ${lv.label}`}</tspan>}
      </text>
    </g>
  )
}

function RectTank({ tank, selected }: { tank: TankSummary; selected: boolean }) {
  const { x, y, w, h } = tank.geom
  const lv = LEVEL[tank.level]
  const problem = isProblem(tank.level)
  const cx = x + w / 2
  return (
    <g>
      <rect className="tk-sel" x={x - 7} y={y - 7} width={w + 14} height={h + 14} rx="13" fill="none" stroke={selected ? INK : 'transparent'} strokeWidth="1.75" />
      <rect
        className="tk-body" x={x} y={y} width={w} height={h} rx="8"
        fill={selected && !problem ? '#F6F8F9' : lv.tint}
        stroke={lv.color} strokeWidth={lv.sw} strokeDasharray={tank.level === 'empty' ? '3 3' : 'none'}
      />
      <text x={cx} y={y + 26} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="13" fontWeight="600" fill={INK}>{tank.id}</text>
      <text x={cx} y={y + 41} textAnchor="middle" fontSize="10.5" fill="#5F6C74">{tank.sub_text}</text>
      {problem && <circle cx={x + w - 2} cy={y + 2} r="5" fill={lv.color} stroke="#FFFFFF" strokeWidth="2" />}
      <text x={cx} y={y + 76} textAnchor="middle" fontSize="10.5">
        <tspan fill="#5F6C74">{tank.level === 'empty' ? '' : tank.live_text}</tspan>
        {problem && <tspan fill={lv.text} fontWeight="600">{` · ${lv.label}`}</tspan>}
      </text>
    </g>
  )
}

function LineCard({ line }: { line: LineView }) {
  const [x, y] = line.card_xy ?? [12, 40]
  return (
    <g>
      <rect x={x} y={y} width="80" height="44" rx="6" fill={line.alert ? '#FFF6ED' : '#FFFFFF'} stroke={line.alert ? '#E0702A' : '#CCD5DB'} />
      <text x={x + 10} y={y + 18} fontSize="11.5" fontWeight="600" fill={INK}>{line.name}</text>
      <text x={x + 10} y={y + 34} fontSize="10" fontWeight={line.alert ? 500 : 400} fill={line.alert ? '#B54708' : '#5F6C74'}>{line.reading_text}</text>
    </g>
  )
}

function planDescription(tanks: TankSummary[], lines: LineView[]) {
  const parts = lines.map((line) => {
    const on = tanks.filter((t) => t.line_id === line.id).map((t) => t.id).join(', ')
    return `Seawater ${line.name.toLowerCase()} is ${line.alert ? 'corrosive' : 'normal'} and feeds ${on}.`
  })
  return `Floor plan of the hatchery. Each tank is outlined by status. ${parts.join(' ')}`
}

function PlanSvg({ tanks, lines, selected, dimmedRoom }: { tanks: TankSummary[]; lines: LineView[]; selected: TankSummary | null; dimmedRoom: string | null }) {
  const patternId = useId()
  const line1 = lines.find((l) => l.id === 'L1')
  const line2 = lines.find((l) => l.id === 'L2')
  const selLine1 = selected?.line_id === 'L1' && selected.level !== 'empty'
  const selLine2 = selected?.line_id === 'L2'
  const p1 = line1?.alert ? '#E0702A' : selLine1 ? '#7D8A92' : '#AEB9C0'
  const p1w = selLine1 ? 2.5 : 2
  const p2 = line2?.alert ? '#E0702A' : selLine2 ? '#7D8A92' : '#AEB9C0'
  const p2w = selLine2 ? (line2?.alert ? 3 : 2.5) : 2
  return (
    <svg
      viewBox="0 0 800 470" width="100%" height="100%" role="img" aria-label={planDescription(tanks, lines)}
      className="absolute inset-0 block" style={{ fontFamily: 'var(--font-sans)' }}
    >
      <defs>
        <pattern id={patternId} width="14" height="14" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="0.9" fill="#DCE3E7" />
        </pattern>
      </defs>
      <rect x="0" y="0" width="800" height="470" fill={`url(#${patternId})`} />

      <text x="12" y="30" fontSize="10" fontWeight="600" letterSpacing="0.8" fill="#5F6C74">SEAWATER</text>
      {lines.map((line) => <LineCard key={line.id} line={line} />)}

      <rect x="120" y="16" width="668" height="442" rx="4" fill="#FFFFFF" stroke="#B9C4CA" strokeWidth="1.5" />
      <g stroke="#B9C4CA" strokeWidth="1.5">
        <line x1="470" y1="16" x2="470" y2="252" /><line x1="470" y1="284" x2="470" y2="300" />
        <line x1="120" y1="300" x2="290" y2="300" /><line x1="318" y1="300" x2="600" y2="300" /><line x1="628" y1="300" x2="788" y2="300" />
        <line x1="330" y1="300" x2="330" y2="458" /><line x1="560" y1="300" x2="560" y2="458" />
      </g>
      <g fontSize="10" fontWeight="600" letterSpacing="0.8" fill="#5F6C74">
        <text x="134" y="36">LARVAL ROOM A</text><text x="484" y="36">LARVAL ROOM B</text>
        <text x="134" y="322">ALGAE ROOM</text><text x="344" y="322">LAB</text><text x="574" y="322">SETTING ROOM</text>
      </g>
      <g fontSize="10" fill="#66737B">
        <text x="250" y="36">6 × 2,000 L</text><text x="600" y="36">4 × 1,000 L</text>
        <text x="134" y="446">18 feed cultures</text><text x="680" y="322">2 downwellers</text>
      </g>

      <g fill="none" strokeLinecap="round" strokeLinejoin="round">
        <path className="pipe1" d="M92 62 H760 V178 H560" stroke={p1} strokeWidth={p1w} />
        <path className="pipe1" d="M185 62 V76 M295 62 V76 M405 62 V76 M560 62 V82 M690 62 V82 M560 178 V198 M690 178 V198" stroke={p1} strokeWidth={p1w} />
        <path className="pipe2" d="M92 176 H405 M185 176 V192 M295 176 V192 M405 176 V192" stroke={p2} strokeWidth={p2w} />
      </g>
      <path d="M100 57 L112 67 L112 57 L100 67 Z" fill="#FFFFFF" stroke={line1?.alert ? '#E0702A' : '#AEB9C0'} strokeWidth="1.5" />
      <path d="M100 171 L112 181 L112 171 L100 181 Z" fill="#FFFFFF" stroke={line2?.alert ? '#E0702A' : '#AEB9C0'} strokeWidth="1.5" />
      <text x="128" y="56" fontSize="9.5" fontWeight="600" letterSpacing="0.6" fill={line1?.alert ? '#B54708' : '#5F6C74'}>LINE 1</text>
      <text x="128" y="170" fontSize="9.5" fontWeight="600" letterSpacing="0.6" fill={line2?.alert ? '#B54708' : '#5F6C74'}>LINE 2</text>

      <g fill="#EEF4EF" stroke="#C9D6CD" strokeWidth="1">
        {[352, 382, 412].map((cy) => [152, 182, 212, 242, 272, 302].map((cx) => <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="8" />))}
      </g>
      <rect x="350" y="396" width="190" height="34" rx="4" fill="#F6F8F9" stroke="#CCD5DB" />
      <text x="445" y="417" textAnchor="middle" fontSize="10" fill="#5F6C74">Microscope bench</text>

      {tanks.map((tank) => (
        <g key={tank.id} opacity={dimmedRoom && tank.room_id !== dimmedRoom ? 0.32 : 1}>
          {tank.shape === 'rect'
            ? <RectTank tank={tank} selected={selected?.id === tank.id} />
            : <CircleTank tank={tank} selected={selected?.id === tank.id} />}
        </g>
      ))}
    </svg>
  )
}

function TankTooltip({ tank, tipClass }: { tank: TankSummary; tipClass: string }) {
  return (
    <span
      className={`tip ${tipClass} box-border flex w-[248px] flex-col gap-2 rounded-card border border-line bg-white p-3 text-left text-ink shadow-pop`}
      style={{ whiteSpace: 'normal' }}
    >
      <span className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-semibold">
          <span className="mono">{tank.id}</span> <span className="font-normal text-ink-4">· {tank.batch_code ?? 'No batch'}</span>
        </span>
        <StatusPill level={tank.level} />
      </span>
      <span className="text-xs leading-[1.45] text-ink-2">{tank.reason}</span>
      <span className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 border-t border-divider pt-2 text-xs">
        <span className="text-ink-4">Survival</span><span className="tnum text-right font-medium">{tank.survival_text}</span>
        <span className="text-ink-4">Last check</span><span className="text-right font-medium">{tank.last_check_text}</span>
        <span className="text-ink-4">Water</span>
        <span className="text-right font-medium" style={{ color: tank.line_alert ? '#B54708' : '#0F1A20' }}>{tank.line_text}</span>
      </span>
    </span>
  )
}

function tankBox(tank: TankSummary) {
  const g = tank.geom
  if (tank.shape === 'rect') return { box: [g.x - 7, g.y - 7, g.w + 14, g.h + 14], cx: g.x + g.w / 2, cy: g.y }
  return { box: [g.cx - g.r - 8, g.cy - g.r - 8, 2 * g.r + 16, 2 * g.r + 16], cx: g.cx, cy: g.cy }
}

function PlanOverlays({ tanks, lines, selectedId, onPick }: { tanks: TankSummary[]; lines: LineView[]; selectedId: string | null; onPick: (id: string) => void }) {
  return (
    <>
      {tanks.map((tank) => {
        const { box, cx, cy } = tankBox(tank)
        const tipClass = `${cy < 200 ? 'below' : 'above'} ${cx < 260 ? 'l' : cx > 600 ? 'r' : 'c'}`
        return (
          <button
            key={tank.id}
            type="button"
            className={`ov ${tank.line_id === 'L2' ? 'l2' : 'l1'}`}
            onClick={() => onPick(tank.id)}
            aria-label={`${tank.id}, ${tank.level_label}. ${tank.reason}`}
            aria-pressed={selectedId === tank.id}
            style={{
              left: pct(box[0], 800), top: pct(box[1], 470), width: pct(box[2], 800), height: pct(box[3], 470),
              borderRadius: tank.shape === 'rect' ? 14 : 999,
            }}
          >
            <TankTooltip tank={tank} tipClass={tipClass} />
          </button>
        )
      })}
      {lines.map((line) => {
        const [x, y] = line.card_xy ?? [12, 40]
        return (
          <span
            key={line.id}
            aria-hidden="true"
            className={`ov ${line.id === 'L2' ? 'l2' : 'l1'}`}
            style={{ left: pct(x, 800), top: pct(y, 470), width: pct(80, 800), height: pct(44, 470), borderRadius: 6, cursor: 'default' }}
          >
            <span className="tip below l box-border flex w-[220px] flex-col gap-1 rounded-control border border-line bg-white px-2.5 py-2 text-left text-xs text-ink-2 shadow-pop" style={{ whiteSpace: 'normal' }}>
              <span className="font-semibold text-ink">{line.name}</span>
              <span>{line.reading_text}{line.water ? ` · ${line.water.when_text}` : ''}</span>
              {line.alert && <span className="font-medium text-risk-text">Corrosive since {line.since_text}</span>}
            </span>
          </span>
        )
      })}
    </>
  )
}

function PlanList({ tanks, selectedId, onPick }: { tanks: TankSummary[]; selectedId: string | null; onPick: (id: string) => void }) {
  return (
    <div className="planlist flex-col">
      {tanks.map((tank, index) => {
        const isSelected = tank.id === selectedId
        return (
          <button
            key={tank.id}
            type="button"
            className="rowbtn flex min-h-12 items-center gap-3 border-0 px-4 py-2 text-left"
            onClick={() => onPick(tank.id)}
            aria-pressed={isSelected}
            style={{ borderTop: index === 0 ? '0' : '1px solid #EEF2F4', background: isSelected ? '#F6F8F9' : undefined }}
          >
            <LevelSwatch level={tank.level} />
            <span className="mono w-11 flex-none text-[13px] font-semibold">{tank.id}</span>
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className="text-[13px] font-medium" style={{ color: LEVEL[tank.level].text }}>{tank.level_label}</span>
              <span className="text-xs text-ink-3">{tank.reason}</span>
            </span>
          </button>
        )
      })}
    </div>
  )
}

const TABLE_COLUMNS = '132px minmax(0, 1.2fr) minmax(0, 1fr) 84px 80px minmax(0, 1fr)'

export function TankTable({ tanks, selectedId, onPick }: { tanks: TankSummary[]; selectedId: string | null; onPick: (id: string) => void }) {
  return (
    <div className="overflow-x-auto">
      <div aria-label="Tanks" className="flex min-w-[640px] flex-col text-[13px]">
        <div aria-hidden="true" className="grid gap-3 border-b border-divider px-4 py-2.5 text-xs text-ink-4" style={{ gridTemplateColumns: TABLE_COLUMNS }}>
          <span>Tank</span><span>Room</span><span>Age</span><span className="text-right">Live (est.)</span><span className="text-right">Survival</span><span>Last check</span>
        </div>
        {tanks.map((tank, index) => {
          const isSelected = tank.id === selectedId
          return (
            <button
              key={tank.id}
              type="button"
              className="rowbtn grid min-h-10 items-center gap-3 border-0 px-4 py-1.5 text-left text-[13px]"
              onClick={() => onPick(tank.id)}
              aria-pressed={isSelected}
              aria-label={`${tank.id}, ${tank.level_label}, ${tank.room_name}, ${tank.age_text}, survival ${tank.survival_text}, last check ${tank.last_check_text}`}
              style={{ gridTemplateColumns: TABLE_COLUMNS, borderTop: index === 0 ? '0' : '1px solid #EEF2F4', background: isSelected ? '#F6F8F9' : undefined }}
            >
              <span className="flex items-center gap-2">
                <LevelSwatch level={tank.level} />
                <span className="mono font-semibold">{tank.id}</span>
                <span className="text-xs" style={{ color: LEVEL[tank.level].text }}>{tank.level_label}</span>
              </span>
              <span className="text-ink-2">{tank.room_name}</span>
              <span className="text-ink-2">{tank.age_text}</span>
              <span className="tnum text-right">{tank.live_text}</span>
              <span className="tnum text-right">{tank.survival_text}</span>
              <span className="text-ink-2">{tank.last_check_text}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function FloorPlanCard({ tanks, visibleTanks, lines, room, selectedId, view, onViewChange, onPick }: {
  tanks: TankSummary[]
  visibleTanks: TankSummary[]
  lines: LineView[]
  room: RoomNav | null
  selectedId: string | null
  view: PlanView
  onViewChange: (view: PlanView) => void
  onPick: (id: string) => void
}) {
  const selected = tanks.find((t) => t.id === selectedId) ?? null
  const anyCorrosive = lines.some((l) => l.alert)
  return (
    <section className="plancard rounded-card border border-line" aria-label="Floor plan">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-divider px-4 py-3">
        <h2 className="flex-auto text-sm font-semibold">Floor plan</h2>
        <div className="flex flex-wrap items-center gap-x-3.5 gap-y-2 text-xs text-ink-3">
          {LEGEND.map((level) => (
            <span key={level} className="flex items-center gap-1.5">
              <LevelSwatch level={level} />
              {LEVEL[level].label}
            </span>
          ))}
          {anyCorrosive && (
            <span className="flex items-center gap-1.5">
              <span className="h-0.5 w-4 rounded-[1px] bg-risk" />
              Corrosive water
            </span>
          )}
        </div>
        <Segmented label="View" value={view} onChange={onViewChange} options={[{ value: 'plan', label: 'Plan' }, { value: 'table', label: 'Table' }]} />
      </div>
      {view === 'plan' ? (
        <>
          <div className="planwrap p-3">
            <div className="planbox relative w-full" style={{ aspectRatio: '800 / 470' }}>
              <PlanSvg tanks={tanks} lines={lines} selected={selected} dimmedRoom={room?.id ?? null} />
              <PlanOverlays tanks={tanks} lines={lines} selectedId={selectedId} onPick={onPick} />
            </div>
          </div>
          <PlanList tanks={visibleTanks} selectedId={selectedId} onPick={onPick} />
        </>
      ) : (
        <TankTable tanks={visibleTanks} selectedId={selectedId} onPick={onPick} />
      )}
    </section>
  )
}
