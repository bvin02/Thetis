import { useState } from 'react'
import type { Tile as TileData } from '../../api/types'
import { SEVERITY_DOT, severityText } from '../../lib/levels'

const WIDTH = 160
const HEIGHT = 34
const PAD = 5

/** One reading over time: the latest value, its target, and a small line with the target dashed behind it. */
export function Tile({ tile }: { tile: TileData }) {
  const [hover, setHover] = useState<number | null>(null)
  const xs = tile.points.map((p) => p[0])
  const ys = tile.points.map((p) => p[1])
  const allYs = tile.guide === null ? ys : [...ys, tile.guide]
  const minX = Math.min(...xs)
  const spanX = Math.max(...xs) - minX || 1
  const minY = Math.min(...allYs)
  const spanY = Math.max(...allYs) - minY || 1
  const toX = (x: number) => PAD + ((x - minX) / spanX) * (WIDTH - PAD * 2)
  const toY = (y: number) => HEIGHT - PAD - ((y - minY) / spanY) * (HEIGHT - PAD * 2)
  const line = tile.points.map((p) => `${toX(p[0]).toFixed(1)},${toY(p[1]).toFixed(1)}`).join(' ')
  const last = tile.points.length - 1
  const shown = hover ?? last
  const color = tile.severity ? SEVERITY_DOT[tile.severity] : '#0F1A20'

  const onMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    const x = ((event.clientX - box.left) / box.width) * WIDTH
    let best = 0
    tile.points.forEach((p, index) => { if (Math.abs(toX(p[0]) - x) < Math.abs(toX(tile.points[best][0]) - x)) best = index })
    setHover(best)
  }

  return (
    <div className="flex min-w-0 flex-col gap-1.5 rounded-control border border-divider px-3 py-2.5">
      <span className="flex items-baseline justify-between gap-2 text-xs text-ink-4">
        <span className="truncate">{tile.label}</span>
        <span className="mono flex-none text-[11px]">{tile.tank_id}</span>
      </span>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width="100%" role="img" aria-label={tile.summary} className="block touch-none"
        onPointerMove={onMove} onPointerLeave={() => setHover(null)}
      >
        {tile.guide !== null && (
          <line x1="0" x2={WIDTH} y1={toY(tile.guide)} y2={toY(tile.guide)} stroke="#C7CFD4" strokeWidth="1" strokeDasharray="3 3" />
        )}
        {tile.points.length > 1 && <polyline points={line} fill="none" stroke="#0F1A20" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />}
        <circle cx={toX(tile.points[shown][0])} cy={toY(tile.points[shown][1])} r="3.5" fill={shown === last ? color : '#0F1A20'} stroke="#FFFFFF" strokeWidth="2" />
      </svg>
      <span className="flex flex-col gap-0.5">
        <span className="tnum text-sm font-semibold whitespace-nowrap" style={{ color: shown === last ? severityText(tile.severity) : '#0F1A20' }}>{tile.point_texts[shown]}</span>
        <span className="text-[11px] whitespace-nowrap text-ink-4">{hover !== null && hover !== last ? `Check ${hover + 1} of ${last + 1}` : tile.target_text}</span>
      </span>
    </div>
  )
}

export function TileRow({ tiles }: { tiles: TileData[] }) {
  if (tiles.length === 0) return null
  return <div className="grid grid-cols-[repeat(auto-fill,minmax(170px,1fr))] gap-2">{tiles.map((tile) => <Tile key={`${tile.tank_id}-${tile.key}`} tile={tile} />)}</div>
}
