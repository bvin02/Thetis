import type { Detection } from '../../api/types'
import { LARVA_COLOR } from '../../lib/levels'

export function contourPoints(detection: Detection): string {
  return detection.contour.map(([x, y]) => `${x},${y}`).join(' ')
}

/** A photo with outlines drawn from detections. Read-only; the review screens use PhotoViewer. */
export function OutlinedPhoto({ url, width, height, detections, alt, view, children }: {
  url: string
  width: number
  height: number
  detections: Detection[]
  alt: string
  /** Optional region of the photo to show: x, y, w, h in image px. */
  view?: [number, number, number, number]
  children?: React.ReactNode
}) {
  const [vx, vy, vw, vh] = view ?? [0, 0, width, height]
  return (
    <div className="relative h-full w-full overflow-hidden">
      <svg viewBox={`${vx} ${vy} ${vw} ${vh}`} preserveAspectRatio="xMidYMid slice" className="absolute inset-0 block h-full w-full" role="img" aria-label={alt}>
        <image href={url} x="0" y="0" width={width} height={height} preserveAspectRatio="none" />
        {detections.filter((d) => d.cls !== 'ignore').map((d) => (
          <polygon
            key={d.id}
            points={contourPoints(d)}
            fill="none"
            stroke={LARVA_COLOR[d.cls]}
            strokeWidth="1.5"
            strokeDasharray={d.unsure ? '4 3' : undefined}
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>
      {children}
    </div>
  )
}
