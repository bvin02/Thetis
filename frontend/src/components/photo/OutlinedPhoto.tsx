import type { Detection } from '../../api/types'
import { LARVA_COLOR } from '../../lib/levels'

function contourPoints(detection: Detection): string {
  return detection.contour.map(([x, y]) => `${x},${y}`).join(' ')
}

/** The design shows a close crop of the photo so outlines read at small sizes. Review shows all of it. */
function closeCrop(width: number, height: number): [number, number, number, number] {
  const w = width * 0.52
  const h = Math.min(height, (w * 2) / 3)
  return [(width - w) / 2, (height - h) / 2, w, h]
}

/** A photo with outlines drawn from detections, as a close crop. Read-only; the review screens use PhotoViewer. */
export function OutlinedPhoto({ url, width, height, detections, alt, children }: {
  url: string
  width: number
  height: number
  detections: Detection[]
  alt: string
  children?: React.ReactNode
}) {
  const [vx, vy, vw, vh] = closeCrop(width, height)
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
