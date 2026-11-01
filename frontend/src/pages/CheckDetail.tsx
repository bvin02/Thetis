import { useMutation, useQuery } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getJSON, postJSON } from '../api/client'
import { useInvalidateAll } from '../api/hooks'
import type { CheckDetail, Detection } from '../api/types'
import { CheckActions, OpinionList } from '../components/review/ClaudeReview'
import { PhotoViewer, type PhotoViewerHandle } from '../components/review/PhotoViewer'
import { CountsPanel, EstimateText, GutPanel, PanelSection, SizePanel, WaterReadOnly } from '../components/review/Panels'
import { TopBar } from '../components/shell/TopBar'
import { useToast } from '../components/toastContext'
import { ErrorState, LoadingState, Spinner, StatusPill } from '../components/ui'
import { SEVERITY_DOT, severityText } from '../lib/levels'
import { withOpinions } from '../lib/opinions'

export default function CheckDetailPage() {
  const { id } = useParams()
  return <CheckDetailView key={id} id={id} />
}

function CheckDetailView({ id }: { id: string | undefined }) {
  const query = useQuery({ queryKey: ['check', id], queryFn: () => getJSON<CheckDetail>(`/api/checks/${id}`) })
  const check = query.data
  const [active, setActive] = useState(0)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<Record<number, Detection[]>>({})
  const viewer = useRef<PhotoViewerHandle | null>(null)
  const invalidate = useInvalidateAll()
  const toast = useToast()

  const save = useMutation({
    mutationFn: async () => {
      let latest: CheckDetail | null = null
      for (const [photoId, detections] of Object.entries(draft)) {
        latest = await postJSON<CheckDetail>(`/api/checks/${id}/photos/${photoId}/detections`, { detections }, 'PATCH')
      }
      return latest
    },
    onSuccess: async (latest) => {
      await invalidate()
      setEditing(false)
      setDraft({})
      if (latest) toast(`Changes saved. ${latest.tank_id} at this check: ${latest.level_label}.`, latest.level)
    },
  })

  if (query.isError) return <><TopBar crumbs={['Checks']} /><ErrorState error={query.error} onRetry={() => query.refetch()} /></>
  if (!check) return <><TopBar crumbs={['Checks']} /><LoadingState /></>

  const photo = check.photos[active] ?? null
  const detections = photo ? draft[photo.id] ?? photo.detections : []
  const dirty = Object.keys(draft).length > 0

  return (
    <>
      <TopBar crumbs={['Checks', `${check.tank_id} · ${check.when_text}`]} newCheckHref={`/checks/new?tank=${check.tank_id}`} />
      <div className="flex min-w-0 flex-1 flex-wrap items-start max-[1099px]:flex-col max-[1099px]:items-stretch">
        <div className="min-w-0 flex-[1_1_480px] p-6 max-[660px]:flex-none max-[660px]:p-4 min-[1100px]:sticky min-[1100px]:top-0">
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <h1 className="mono text-xl font-semibold tracking-[-0.01em]">
                <Link to={`/tanks/${check.tank_id}`} className="no-underline hover:underline">{check.tank_id}</Link>
              </h1>
              <StatusPill level={check.level} large />
              <span className="text-[13px] text-ink-2">{check.when_text} · Day {check.day}{check.batch_code ? ` · Batch ${check.batch_code}` : ''}</span>
              <span className="flex-1" />
              {photo && (editing ? (
                <span className="flex gap-2">
                  <button type="button" className="ghost" disabled={save.isPending} onClick={() => { setEditing(false); setDraft({}) }}>Cancel</button>
                  <button type="button" className="solid" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
                    {save.isPending && <Spinner light />}
                    Save changes
                  </button>
                </span>
              ) : (
                <button type="button" className="ghost" onClick={() => setEditing(true)}>Edit outlines</button>
              ))}
            </div>
            {save.isError && <p role="alert" className="m-0 text-[13px] text-critical-text">{save.error instanceof Error ? save.error.message : "That didn't save."}</p>}
            {photo ? (
              <>
                <PhotoViewer
                  key={photo.url}
                  ref={viewer}
                  url={photo.url} width={photo.width} height={photo.height} detections={detections} editable={editing}
                  onChange={(next) => setDraft((current) => ({ ...current, [photo.id]: next }))}
                  tabs={check.photos.length > 1 ? (
                    <div role="tablist" aria-label="Photos in this check" className="flex flex-wrap gap-1">
                      {check.photos.map((p, index) => (
                        <button key={p.id} type="button" role="tab" aria-selected={index === active} className="h-7 cursor-pointer rounded-small border-0 px-2 text-xs font-medium" style={{ background: index === active ? '#F1F4F6' : 'transparent' }} onClick={() => setActive(index)}>
                          Photo {index + 1}
                        </button>
                      ))}
                    </div>
                  ) : undefined}
                />
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-4">
                  {photo.synthetic && <span className="tag">Synthetic sample</span>}
                  <span className="tnum">
                    {check.n_counted} larvae
                    {photo.um_per_px ? ` · ${photo.um_per_px.toFixed(2)} µm/px · ${photo.calibration === 'grid' ? 'grid calibration' : photo.calibration === 'manual' ? 'manual scale' : 'preset scale'}` : ' · no scale'}
                    {photo.volume_ml ? ` · ${photo.volume_ml.toFixed(4)} mL in view` : ''}
                  </span>
                </div>
              </>
            ) : (
              <div className="grid min-h-[280px] place-items-center rounded-card border border-line bg-subtle text-[13px] text-ink-4">This check has no photo.</div>
            )}
          </div>
        </div>

        <aside aria-label="Check details" className="box-border flex w-[380px] flex-none flex-col border-l border-divider max-[1099px]:w-full max-[1099px]:border-t max-[1099px]:border-l-0">
          <CountsPanel summary={check.summary}>
            {editing && photo && (
              <>
                <CheckActions
                  photoRef={photo.id} detections={detections}
                  totalUnsure={detections.filter((d) => d.unsure && d.cls !== 'ignore').length}
                  onOpinions={(asked, opinions) => setDraft((current) => {
                    const base = current[asked as number] ?? check.photos.find((p) => p.id === asked)?.detections ?? []
                    return { ...current, [asked as number]: withOpinions(base, opinions) }
                  })}
                  onReview={() => viewer.current?.nextUnsure()}
                />
                <OpinionList
                  detections={detections}
                  onChange={(next) => setDraft((current) => ({ ...current, [photo.id]: next }))}
                  onSelect={(id) => viewer.current?.select(id)}
                />
              </>
            )}
          </CountsPanel>
          <SizePanel summary={check.summary} previousHist={check.previous_hist} calibrated={!!photo?.um_per_px} />
          <GutPanel gut={check.summary.gut} />
          <PanelSection title="Estimate for the tank" label="Estimate for the tank">
            <EstimateText estimate={{ live_est: check.live_est, survival: check.survival, stocked: check.stocked, over_stocked: false }} />
            {check.bucket_l !== null && check.concentration !== null && (
              <span className="tnum text-xs text-ink-4">{check.bucket_l} L bucket · sample concentrated ×{check.concentration}</span>
            )}
          </PanelSection>
          <WaterReadOnly water={check.water} severities={check.severities} />
          {check.notes && (
            <PanelSection title="Notes" label="Notes">
              <p className="m-0 text-[13px] leading-normal whitespace-pre-wrap text-ink-2">{check.notes}</p>
            </PanelSection>
          )}
          <PanelSection title="Risk at save time" aside={<span className="tag">Rules-based</span>} label="Risk at save time">
            <div className="flex flex-col gap-1">
              <span className="text-sm font-semibold">{check.snapshot.title}</span>
              <span className="text-[13px] leading-normal text-ink-2">{check.snapshot.forecast}</span>
            </div>
            <div className="flex flex-col">
              {check.snapshot.condition.map((row) => (
                <div key={`${row.key}-${row.severity}`} className="flex min-h-8 items-center gap-3 border-t border-divider text-[13px]">
                  <span className="flex min-w-0 flex-1 items-center gap-2 text-ink-2">
                    <span className="h-1.5 w-1.5 flex-none rounded-full" style={{ background: row.severity ? SEVERITY_DOT[row.severity] : 'transparent' }} />
                    {row.label}
                  </span>
                  <span className="tnum w-[76px] text-right font-semibold" style={{ color: severityText(row.severity) }}>{row.now}</span>
                  <span className="w-[108px] text-right text-xs leading-[1.35] text-ink-4">{row.cmp}</span>
                </div>
              ))}
            </div>
          </PanelSection>
        </aside>
      </div>
    </>
  )
}
