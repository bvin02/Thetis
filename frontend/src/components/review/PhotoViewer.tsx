import { Maximize, Minus, Plus, X } from 'lucide-react'
import { forwardRef, useCallback, useEffect, useImperativeHandle, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent, ReactNode } from 'react'
import type { Detection, LarvaClass } from '../../api/types'
import { LARVA_COLOR } from '../../lib/levels'
import { OPINION_NAME, decideOpinion } from '../../lib/opinions'
import { Segmented } from '../ui'

export type FilterKey = 'live' | 'abnormal' | 'dead' | 'unsure' | 'ignore'
type Mode = 'select' | 'add' | 'scale'

interface View { x: number; y: number; w: number; h: number }

const CLASS_OPTIONS: { cls: LarvaClass; label: string; key: string }[] = [
  { cls: 'live', label: 'Live', key: '1' },
  { cls: 'abnormal', label: 'Abnormal', key: '2' },
  { cls: 'dead', label: 'Dead', key: '3' },
  { cls: 'ignore', label: 'Not a larva', key: '0' },
]

const CLASS_NAME: Record<LarvaClass, string> = { live: 'Live', abnormal: 'Abnormal', dead: 'Dead', ignore: 'Not a larva' }

export interface PhotoViewerHandle {
  /** Select the next unsure object and zoom to it. Returns false when there are none. */
  nextUnsure: () => boolean
  /** Start drawing a line to set the scale by hand. */
  startScale: () => void
  /** Select one object and zoom to it. */
  select: (id: number) => void
}

function contourString(d: Detection) {
  return d.contour.map(([x, y]) => `${x},${y}`).join(' ')
}

function bounds(d: Detection) {
  const xs = d.contour.map((p) => p[0])
  const ys = d.contour.map((p) => p[1])
  return { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) }
}

function circleContour(cx: number, cy: number, radius: number): [number, number][] {
  const points: [number, number][] = []
  for (let i = 0; i < 24; i++) {
    const t = (i / 24) * Math.PI * 2
    points.push([Math.round((cx + radius * Math.cos(t)) * 10) / 10, Math.round((cy + radius * Math.sin(t)) * 10) / 10])
  }
  return points
}

function median(values: number[]): number | null {
  if (values.length === 0) return null
  const sorted = [...values].sort((a, b) => a - b)
  return sorted[Math.floor(sorted.length / 2)]
}

function clampView(view: View, width: number, height: number): View {
  const w = Math.min(view.w, width)
  const h = Math.min(view.h, height)
  return { w, h, x: Math.min(Math.max(view.x, 0), width - w), y: Math.min(Math.max(view.y, 0), height - h) }
}

function FilterChip({ on, onClick, color, dashed, label, count }: {
  on: boolean; onClick: () => void; color: string; dashed?: boolean; label: string; count: number
}) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className="chip tnum flex h-7 items-center gap-1.5 rounded-small border px-2 text-xs max-[660px]:h-9"
      style={{ borderColor: on ? '#CCD5DB' : '#E2E8EC', background: on ? '#FFFFFF' : '#F6F8F9', color: on ? '#0F1A20' : '#66737B' }}
    >
      <span
        className="box-border h-2 w-2 rounded-full"
        style={{ border: `2px ${dashed ? 'dotted' : 'solid'} ${on ? color : '#AEB9C0'}` }}
      />
      {label} <span className="font-medium">{count}</span>
    </button>
  )
}

function ZoomButton({ label, onClick, children, disabled }: { label: string; onClick: () => void; children: ReactNode; disabled?: boolean }) {
  return (
    <button type="button" className="ghost !h-7 !w-7 !rounded-small !p-0 max-[660px]:!h-9 max-[660px]:!w-9" aria-label={label} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  )
}

export interface PhotoViewerProps {
  url: string
  width: number
  height: number
  detections: Detection[]
  editable: boolean
  onChange?: (next: Detection[]) => void
  /** Called with µm/px after the user draws a scale line. */
  onScale?: (umPerPx: number) => void
  tabs?: ReactNode
}

export const PhotoViewer = forwardRef<PhotoViewerHandle, PhotoViewerProps>(function PhotoViewer(
  { url, width, height, detections, editable, onChange, onScale, tabs },
  ref,
) {
  const [view, setView] = useState<View>({ x: 0, y: 0, w: width, h: height })
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [hoverId, setHoverId] = useState<number | null>(null)
  const [mode, setMode] = useState<Mode>('select')
  const [filters, setFilters] = useState<Record<FilterKey, boolean>>({ live: true, abnormal: true, dead: true, unsure: true, ignore: false })
  const [scaleLine, setScaleLine] = useState<[number, number, number, number] | null>(null)
  const [scaleUm, setScaleUm] = useState('')
  const [panning, setPanning] = useState(false)
  const [drawingScale, setDrawingScale] = useState(false)
  const svgRef = useRef<SVGSVGElement | null>(null)
  const boxRef = useRef<HTMLDivElement | null>(null)
  const [boxWidth, setBoxWidth] = useState(800)
  const drag = useRef<{ startX: number; startY: number; view: View; moved: boolean; pointerId: number } | null>(null)
  const justDragged = useRef(false)

  useLayoutEffect(() => {
    const box = boxRef.current
    if (!box) return
    const observer = new ResizeObserver(() => setBoxWidth(box.clientWidth || 800))
    observer.observe(box)
    setBoxWidth(box.clientWidth || 800)
    return () => observer.disconnect()
  }, [])

  const unitsPerPixel = view.w / Math.max(boxWidth, 1)
  const selected = detections.find((d) => d.id === selectedId) ?? null

  const counts = useMemo(() => {
    const c = { live: 0, abnormal: 0, dead: 0, unsure: 0, ignore: 0 }
    for (const d of detections) {
      if (d.cls === 'ignore') { c.ignore += 1; continue }
      c[d.cls] += d.cls === 'live' || d.cls === 'abnormal' ? d.clump_n : 1
      if (d.unsure) c.unsure += 1
    }
    return c
  }, [detections])

  const isVisible = useCallback((d: Detection) => {
    if (d.cls === 'ignore') return filters.ignore
    if (d.unsure && !filters.unsure) return false
    return filters[d.cls]
  }, [filters])

  const toImage = useCallback((clientX: number, clientY: number) => {
    const svg = svgRef.current
    if (!svg) return { x: 0, y: 0 }
    const matrix = svg.getScreenCTM()
    if (!matrix) return { x: 0, y: 0 }
    const point = new DOMPoint(clientX, clientY).matrixTransform(matrix.inverse())
    return { x: point.x, y: point.y }
  }, [])

  const zoomAround = useCallback((factor: number, cx: number, cy: number) => {
    setView((current) => {
      const w = Math.min(Math.max(current.w * factor, width / 16), width)
      const h = (w * height) / width
      const real = w / current.w
      return clampView({ w, h, x: cx - (cx - current.x) * real, y: cy - (cy - current.y) * real }, width, height)
    })
  }, [width, height])

  const zoomCenter = (factor: number) => zoomAround(factor, view.x + view.w / 2, view.y + view.h / 2)
  const fit = () => setView({ x: 0, y: 0, w: width, h: height })

  // Mouse wheel zooms. Registered by hand: React's wheel listener can't stop the page from scrolling.
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const onWheel = (event: WheelEvent) => {
      event.preventDefault()
      const { x, y } = toImage(event.clientX, event.clientY)
      zoomAround(event.deltaY > 0 ? 1.15 : 1 / 1.15, x, y)
    }
    svg.addEventListener('wheel', onWheel, { passive: false })
    return () => svg.removeEventListener('wheel', onWheel)
  }, [toImage, zoomAround])

  const focusOn = useCallback((d: Detection) => {
    const b = bounds(d)
    const size = Math.max(b.x1 - b.x0, b.y1 - b.y0, 60)
    const w = Math.max(Math.min(size * 5, width), width / 16)
    const h = (w * height) / width
    setView(clampView({ w, h, x: d.cx - w / 2, y: d.cy - h / 2 }, width, height))
  }, [width, height])

  const update = useCallback((id: number, patch: (d: Detection) => Detection) => {
    onChange?.(detections.map((d) => (d.id === id ? patch(d) : d)))
  }, [detections, onChange])

  const setClass = useCallback((id: number, cls: LarvaClass) => {
    update(id, (d) => ({
      ...d,
      cls,
      unsure: false,
      source: d.source === 'manual' ? 'manual' : cls === d.auto_cls ? 'auto' : 'corrected',
    }))
  }, [update])

  const nextUnsure = useCallback(() => {
    const pool = detections.filter((d) => d.unsure && d.cls !== 'ignore')
    if (pool.length === 0) return false
    const index = pool.findIndex((d) => d.id === selectedId)
    const next = pool[(index + 1) % pool.length]
    setFilters((f) => ({ ...f, unsure: true, [next.cls]: true }))
    setSelectedId(next.id)
    focusOn(next)
    return true
  }, [detections, selectedId, focusOn])

  useImperativeHandle(ref, () => ({
    nextUnsure,
    startScale: () => {
      setMode('scale')
      setScaleLine(null)
      setSelectedId(null)
    },
    select: (id: number) => {
      const target = detections.find((d) => d.id === id)
      if (!target) return
      setSelectedId(id)
      focusOn(target)
    },
  }), [nextUnsure, detections, focusOn])

  // Keyboard: 1/2/3/0 set the class, Tab moves to the next unsure object, Esc clears
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return
      if (event.key === 'Escape') {
        setSelectedId(null)
        if (mode !== 'select') setMode('select')
        setScaleLine(null)
        return
      }
      if (!editable) return
      if (event.key === 'Tab' && detections.some((d) => d.unsure && d.cls !== 'ignore') && selectedId !== null) {
        event.preventDefault()
        nextUnsure()
        return
      }
      if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
        const pool = detections.filter(isVisible)
        const focusedHere = document.activeElement === svgRef.current
        if (pool.length > 0 && (selected || focusedHere)) {
          event.preventDefault()
          const index = pool.findIndex((d) => d.id === selectedId)
          const step = event.key === 'ArrowRight' ? 1 : -1
          const next = pool[index < 0 ? 0 : (index + step + pool.length) % pool.length]
          setSelectedId(next.id)
        }
        return
      }
      if (!selected) return
      const option = CLASS_OPTIONS.find((o) => o.key === event.key)
      if (option) {
        event.preventDefault()
        setClass(selected.id, option.cls)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [editable, selected, selectedId, detections, mode, nextUnsure, setClass, isVisible])

  const addLarva = (x: number, y: number) => {
    if (!onChange) return
    const lengths = detections.filter((d) => d.cls !== 'ignore' && d.clump_n === 1)
    const lengthPx = median(lengths.map((d) => d.length_px)) ?? Math.max(width, height) / 20
    const lengthUm = median(lengths.filter((d) => d.length_um !== null).map((d) => d.length_um as number))
    const id = detections.reduce((max, d) => Math.max(max, d.id), 0) + 1
    const radius = lengthPx / 2
    const larva: Detection = {
      id, cx: Math.round(x * 10) / 10, cy: Math.round(y * 10) / 10, contour: circleContour(x, y, radius),
      length_px: lengthPx, length_um: lengthUm, area_px: Math.PI * radius * radius, solidity: 1, defect: 0, hollowness: 1.5,
      gut: null, interior: 0, cls: 'live', auto_cls: 'live', unsure: false, unsure_reason: null, clump_n: 1,
      touches_edge: false, source: 'manual', claude: null,
    }
    onChange([...detections, larva])
    setSelectedId(id)
    setMode('select')
  }

  const onPointerDown = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (event.button !== 0) return
    if (mode === 'scale') {
      const { x, y } = toImage(event.clientX, event.clientY)
      setScaleLine([x, y, x, y])
      setScaleUm('')
      setDrawingScale(true)
      drag.current = { startX: event.clientX, startY: event.clientY, view, moved: false, pointerId: event.pointerId }
      svgRef.current?.setPointerCapture(event.pointerId)
      return
    }
    drag.current = { startX: event.clientX, startY: event.clientY, view, moved: false, pointerId: event.pointerId }
  }

  const onPointerMove = (event: ReactPointerEvent<SVGSVGElement>) => {
    const current = drag.current
    if (!current) return
    if (mode === 'scale') {
      const { x, y } = toImage(event.clientX, event.clientY)
      setScaleLine((line) => (line ? [line[0], line[1], x, y] : line))
      return
    }
    const dx = event.clientX - current.startX
    const dy = event.clientY - current.startY
    if (!current.moved && Math.hypot(dx, dy) < 4) return
    if (!current.moved && current.view.w >= width) return // nothing to pan at full view
    if (!current.moved) {
      current.moved = true
      setPanning(true)
      svgRef.current?.setPointerCapture(current.pointerId)
    }
    const k = current.view.w / Math.max(boxWidth, 1)
    setView(clampView({ ...current.view, x: current.view.x - dx * k, y: current.view.y - dy * k }, width, height))
  }

  const onPointerUp = () => {
    if (drag.current?.moved) {
      justDragged.current = true
      window.setTimeout(() => { justDragged.current = false }, 0)
    }
    drag.current = null
    setPanning(false)
    setDrawingScale(false)
  }

  const onBackgroundClick = (event: React.MouseEvent<SVGElement>) => {
    if (justDragged.current || mode === 'scale') return
    if (mode === 'add') {
      const { x, y } = toImage(event.clientX, event.clientY)
      addLarva(x, y)
      return
    }
    setSelectedId(null)
  }

  const onObjectClick = (event: React.MouseEvent, d: Detection) => {
    event.stopPropagation()
    if (justDragged.current || mode === 'scale') return
    if (mode === 'add') {
      const { x, y } = toImage(event.clientX, event.clientY)
      addLarva(x, y)
      return
    }
    setSelectedId(d.id)
  }

  const applyScale = () => {
    if (!scaleLine) return
    const lengthPx = Math.hypot(scaleLine[2] - scaleLine[0], scaleLine[3] - scaleLine[1])
    const um = Number(scaleUm)
    if (lengthPx > 2 && um > 0) {
      onScale?.(um / lengthPx)
      setMode('select')
      setScaleLine(null)
    }
  }

  // Popover position, in px inside the viewer box
  const popover = useMemo(() => {
    if (!selected) return null
    const k = boxWidth / view.w
    const boxHeight = (boxWidth * height) / width
    const b = bounds(selected)
    const popoverWidth = 214
    const right = (b.x1 - view.x) * k + 10
    const left = (b.x0 - view.x) * k - popoverWidth - 10
    const x = right + popoverWidth <= boxWidth ? right : left >= 0 ? left : Math.max(8, boxWidth - popoverWidth - 8)
    const y = Math.max(8, Math.min((selected.cy - view.y) * k - 70, boxHeight - 240))
    return { x, y, width: popoverWidth }
  }, [selected, view, boxWidth, width, height])

  const ordered = useMemo(() => {
    // The selected object draws last, so its outline stays on top
    const visible = detections.filter((d) => isVisible(d) || d.id === selectedId)
    return [...visible].sort((a, b) => Number(a.id === selectedId) - Number(b.id === selectedId))
  }, [detections, isVisible, selectedId])

  const scaleLengthPx = scaleLine ? Math.hypot(scaleLine[2] - scaleLine[0], scaleLine[3] - scaleLine[1]) : 0
  const cursor = mode === 'add' || mode === 'scale' ? 'crosshair' : panning ? 'grabbing' : view.w < width ? 'grab' : 'default'

  const docked = boxWidth < 520
  const popoverCard = selected ? (
          <div
            className={`appear box-border flex flex-col gap-2 rounded-card border border-line bg-white p-2.5 shadow-pop ${docked ? '' : 'absolute z-20'}`}
            style={docked ? undefined : { left: popover?.x, top: popover?.y, width: popover?.width }}
            onPointerDown={(event) => event.stopPropagation()}
            role="dialog"
            aria-label={`Larva ${selected.id}`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="tnum text-[13px] font-semibold">
                Larva {selected.id}
                {selected.length_um !== null && <span className="font-normal text-ink-3"> · {Math.round(selected.length_um)} µm</span>}
              </span>
              <button type="button" className="rowbtn grid h-6 w-6 flex-none place-items-center rounded-small border-0 bg-transparent text-ink-4" aria-label="Close" onClick={() => setSelectedId(null)}>
                <X size={14} strokeWidth={1.75} />
              </button>
            </div>
            {selected.unsure && selected.unsure_reason && (
              <span className="text-xs text-ink-3">Unsure: {selected.unsure_reason}</span>
            )}
            {selected.claude && !selected.claude.decided && (
              <div className="flex flex-col gap-1.5 rounded-small bg-subtle p-2 text-xs">
                <span className="leading-[1.4] text-ink-2">
                  <span className="font-medium text-ink">Claude: {OPINION_NAME[selected.claude.cls]}</span> · {selected.claude.reason}
                </span>
                {editable && (
                  <span className="flex gap-1">
                    <button type="button" className="solid !h-6 !px-2 !text-xs" onClick={() => update(selected.id, (d) => decideOpinion(d, 'accepted'))}>Accept</button>
                    <button type="button" className="ghost !h-6 !px-2 !text-xs" onClick={() => update(selected.id, (d) => decideOpinion(d, 'kept'))}>Keep</button>
                  </span>
                )}
              </div>
            )}
            {editable ? (
              <div className="flex flex-col gap-0.5">
                {CLASS_OPTIONS.map((option) => {
                  const current = selected.cls === option.cls
                  return (
                    <button
                      key={option.cls}
                      type="button"
                      aria-pressed={current}
                      className="rowbtn flex h-7 items-center gap-2 rounded-small border-0 px-1.5 text-left text-[13px] max-[660px]:h-11"
                      style={{ background: current ? '#F1F4F6' : 'transparent', fontWeight: current ? 500 : 400 }}
                      onClick={() => setClass(selected.id, option.cls)}
                    >
                      <span className="box-border h-2 w-2 flex-none rounded-full" style={{ border: `2px ${option.cls === 'ignore' ? 'dotted' : 'solid'} ${LARVA_COLOR[option.cls]}` }} />
                      <span className="flex-1">{option.label}</span>
                      <span className="mono text-[11px] text-ink-4">{option.key}</span>
                    </button>
                  )
                })}
              </div>
            ) : (
              <div className="flex items-center gap-2 text-[13px]">
                <span className="box-border h-2 w-2 rounded-full" style={{ border: `2px solid ${LARVA_COLOR[selected.cls]}` }} />
                {CLASS_NAME[selected.cls]}
                {selected.source !== 'auto' && <span className="text-xs text-ink-4">{selected.source === 'manual' ? 'added by hand' : `was ${CLASS_NAME[selected.auto_cls].toLowerCase()}`}</span>}
              </div>
            )}
            {editable && selected.clump_n > 1 && (
              <div className="flex items-center justify-between gap-2 border-t border-divider pt-2 text-xs text-ink-2">
                <span>Larvae in this clump</span>
                <span className="flex items-center gap-1">
                  <ZoomButton label="One fewer" onClick={() => update(selected.id, (d) => ({ ...d, clump_n: Math.max(2, d.clump_n - 1), unsure: false }))}><Minus size={12} strokeWidth={1.75} /></ZoomButton>
                  <span className="tnum w-5 text-center font-medium">{selected.clump_n}</span>
                  <ZoomButton label="One more" onClick={() => update(selected.id, (d) => ({ ...d, clump_n: d.clump_n + 1, unsure: false }))}><Plus size={12} strokeWidth={1.75} /></ZoomButton>
                </span>
              </div>
            )}
            {editable && selected.source === 'manual' && (
              <button
                type="button"
                className="ghost !h-7 !text-xs"
                onClick={() => {
                  onChange?.(detections.filter((d) => d.id !== selected.id))
                  setSelectedId(null)
                }}
              >
                Delete
              </button>
            )}
          </div>
  ) : null

  return (
    <div className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-2">
        {editable && (
          <Segmented
            label="Tool"
            value={mode === 'add' ? 'add' : 'select'}
            onChange={(value) => setMode(value)}
            options={[{ value: 'select', label: 'Select' }, { value: 'add', label: 'Add larva' }]}
          />
        )}
        <div role="group" aria-label="Show on photo" className="flex flex-wrap items-center gap-1">
          <FilterChip label="Live" count={counts.live} color={LARVA_COLOR.live} on={filters.live} onClick={() => setFilters((f) => ({ ...f, live: !f.live }))} />
          <FilterChip label="Abnormal" count={counts.abnormal} color={LARVA_COLOR.abnormal} on={filters.abnormal} onClick={() => setFilters((f) => ({ ...f, abnormal: !f.abnormal }))} />
          <FilterChip label="Dead" count={counts.dead} color={LARVA_COLOR.dead} on={filters.dead} onClick={() => setFilters((f) => ({ ...f, dead: !f.dead }))} />
          <FilterChip label="Unsure" count={counts.unsure} color="#5F6C74" dashed on={filters.unsure} onClick={() => setFilters((f) => ({ ...f, unsure: !f.unsure }))} />
          <FilterChip label="Ignored" count={counts.ignore} color={LARVA_COLOR.ignore} dashed on={filters.ignore} onClick={() => setFilters((f) => ({ ...f, ignore: !f.ignore }))} />
        </div>
        <div className="ml-auto flex items-center gap-1">
          <ZoomButton label="Zoom out" onClick={() => zoomCenter(1.4)} disabled={view.w >= width}><Minus size={14} strokeWidth={1.75} /></ZoomButton>
          <ZoomButton label="Zoom in" onClick={() => zoomCenter(1 / 1.4)}><Plus size={14} strokeWidth={1.75} /></ZoomButton>
          <button type="button" className="ghost !h-7 !gap-1 !rounded-small !px-2 !text-xs max-[660px]:!h-9" onClick={fit} disabled={view.w >= width}>
            <Maximize size={12} strokeWidth={1.75} aria-hidden="true" />
            Fit
          </button>
        </div>
      </div>
      {tabs}

      <div ref={boxRef} className="relative box-border w-full overflow-hidden rounded-card border border-line bg-muted-bg" style={{ aspectRatio: `${width} / ${height}` }}>
        <svg
          ref={svgRef}
          viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
          preserveAspectRatio="xMidYMid meet"
          className="absolute inset-0 block h-full w-full select-none focus-visible:outline-offset-[-2px]"
          style={{ cursor, touchAction: 'none' }}
          role="application"
          tabIndex={0}
          aria-label="Photo with an outline around each object. Select an outline to change its class. Left and right arrow keys move between objects, keys 1, 2, 3 and 0 set the class of the selected object, and Tab moves to the next unsure object."
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onPointerLeave={() => setHoverId(null)}
        >
          <image href={url} x="0" y="0" width={width} height={height} preserveAspectRatio="none" onClick={onBackgroundClick} />
          {ordered.map((d) => {
            const color = LARVA_COLOR[d.cls]
            const isSelected = d.id === selectedId
            const isHover = d.id === hoverId
            const dash = d.cls === 'ignore' ? '2 3' : d.unsure ? '6 4' : undefined
            const points = contourString(d)
            return (
              <g key={d.id}>
                {isSelected && <polygon points={points} fill="none" stroke="#FFFFFF" strokeWidth="6" vectorEffect="non-scaling-stroke" pointerEvents="none" />}
                <polygon
                  points={points}
                  fill={color}
                  fillOpacity={isHover || isSelected ? 0.08 : 0}
                  stroke={color}
                  strokeWidth={isSelected ? 3 : 2}
                  strokeDasharray={dash}
                  vectorEffect="non-scaling-stroke"
                  pointerEvents="all"
                  style={{ cursor: mode === 'select' ? 'pointer' : cursor }}
                  onClick={(event) => onObjectClick(event, d)}
                  onPointerEnter={() => setHoverId(d.id)}
                  onPointerLeave={() => setHoverId((h) => (h === d.id ? null : h))}
                />
              </g>
            )
          })}
          {ordered.filter((d) => d.unsure && d.cls !== 'ignore').map((d) => {
            const b = bounds(d)
            const r = 7.5 * unitsPerPixel
            return (
              <g key={`q-${d.id}`} pointerEvents="none">
                <circle cx={b.x1 - r * 0.2} cy={b.y0 + r * 0.2} r={r} fill="#FFFFFF" stroke="#3E4B53" strokeWidth={1 * unitsPerPixel} />
                <text x={b.x1 - r * 0.2} y={b.y0 + r * 0.2 + 3.6 * unitsPerPixel} textAnchor="middle" fontSize={10.5 * unitsPerPixel} fontWeight="600" fill="#0F1A20">?</text>
              </g>
            )
          })}
          {ordered.filter((d) => d.clump_n > 1 && d.cls !== 'ignore').map((d) => {
            const w = 26 * unitsPerPixel
            const h = 16 * unitsPerPixel
            return (
              <g key={`c-${d.id}`} pointerEvents="none">
                <rect x={d.cx - w / 2} y={d.cy - h / 2} width={w} height={h} rx={h / 2} fill="#0F1A20" />
                <text x={d.cx} y={d.cy + 3.8 * unitsPerPixel} textAnchor="middle" fontSize={10.5 * unitsPerPixel} fontWeight="600" fill="#FFFFFF">×{d.clump_n}</text>
              </g>
            )
          })}
          {scaleLine && (
            <g pointerEvents="none">
              <line x1={scaleLine[0]} y1={scaleLine[1]} x2={scaleLine[2]} y2={scaleLine[3]} stroke="#FFFFFF" strokeWidth="5" vectorEffect="non-scaling-stroke" />
              <line x1={scaleLine[0]} y1={scaleLine[1]} x2={scaleLine[2]} y2={scaleLine[3]} stroke="#13557A" strokeWidth="2" vectorEffect="non-scaling-stroke" />
            </g>
          )}
        </svg>

        {mode === 'add' && (
          <span className="pointer-events-none absolute top-2 left-1/2 -translate-x-1/2 rounded-small bg-white/95 px-2 py-1 text-xs text-ink shadow-pop">
            Click where a larva was missed
          </span>
        )}
        {mode === 'scale' && (
          <div className="absolute top-2 left-1/2 flex -translate-x-1/2 flex-wrap items-center gap-2 rounded-control border border-line bg-white px-3 py-2 text-xs shadow-pop">
            {scaleLengthPx > 2 && !drawingScale ? (
              <>
                <label htmlFor="scale-um" className="text-ink-2">This line is</label>
                <input
                  id="scale-um" autoFocus type="number" min="0" step="any" value={scaleUm}
                  onChange={(event) => setScaleUm(event.target.value)}
                  onKeyDown={(event) => { if (event.key === 'Enter') applyScale() }}
                  className="field !h-7 !w-20"
                />
                <span className="text-ink-2">µm</span>
                <button type="button" className="solid !h-7 !text-xs" disabled={!(Number(scaleUm) > 0)} onClick={applyScale}>Apply</button>
                <button type="button" className="ghost !h-7 !text-xs" onClick={() => { setMode('select'); setScaleLine(null) }}>Cancel</button>
              </>
            ) : (
              <>
                <span className="text-ink-2">Drag along something of known length, such as a grid square.</span>
                <button type="button" className="ghost !h-7 !text-xs" onClick={() => { setMode('select'); setScaleLine(null) }}>Cancel</button>
              </>
            )}
          </div>
        )}

        {selected && !docked && popoverCard}
      </div>
      {selected && docked && popoverCard}
    </div>
  )
})
