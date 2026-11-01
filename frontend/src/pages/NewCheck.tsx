import { useMutation, useQuery } from '@tanstack/react-query'
import { ChevronDown, Plus, UploadCloud, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getJSON, postFile, postJSON } from '../api/client'
import { useFloor, useInvalidateAll, useTank } from '../api/hooks'
import type { AnalysisResult, Detection, Estimate, SampleSlide, SaveResult, Summary } from '../api/types'
import { CheckActions, OpinionList } from '../components/review/ClaudeReview'
import { PhotoViewer, type PhotoViewerHandle } from '../components/review/PhotoViewer'
import { CountsPanel, EstimatePanel, GutPanel, PanelSection, SizePanel, WaterPanel } from '../components/review/Panels'
import { TopBar } from '../components/shell/TopBar'
import { useToast } from '../components/toastContext'
import { ErrorState, LoadingState, Spinner } from '../components/ui'
import { withOpinions } from '../lib/opinions'
import { EMPTY_WATER, type WaterForm } from '../lib/water'

function localDateTimeValue(date = new Date()) {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const toNumberOrNull = (text: string) => (text.trim() === '' || Number.isNaN(Number(text)) ? null : Number(text))

function quickSummary(detections: Detection[]) {
  // Instant counts for the panel; sizes and the estimate come from the server a moment later
  let n_live = 0; let n_abnormal = 0; let n_dead = 0; let n_unsure = 0
  for (const d of detections) {
    if (d.cls === 'ignore') continue
    if (d.unsure) n_unsure += 1
    if (d.cls === 'dead') n_dead += 1
    else if (d.cls === 'live') n_live += d.clump_n
    else n_abnormal += d.clump_n
  }
  const counted = n_live + n_abnormal + n_dead
  return {
    n_live, n_abnormal, n_dead, n_unsure,
    pct_dead: counted ? (100 * n_dead) / counted : 0,
    pct_abnormal: counted ? (100 * n_abnormal) / counted : 0,
  }
}

function SampleMenu({ onPick, disabled }: { onPick: (sample: SampleSlide) => void; disabled?: boolean }) {
  const [open, setOpen] = useState(false)
  const samples = useQuery({ queryKey: ['samples'], queryFn: () => getJSON<{ samples: SampleSlide[] }>('/api/samples') })
  const ref = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (!open) return
    const onDown = (event: MouseEvent) => { if (!ref.current?.contains(event.target as Node)) setOpen(false) }
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false) }
    window.addEventListener('mousedown', onDown)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('mousedown', onDown)
      window.removeEventListener('keydown', onKey)
    }
  }, [open])
  return (
    <div ref={ref} className="relative">
      <button type="button" className="ghost max-[660px]:!h-11" aria-haspopup="menu" aria-expanded={open} disabled={disabled} onClick={() => setOpen((v) => !v)}>
        Use a sample slide
        <ChevronDown size={14} strokeWidth={1.75} aria-hidden="true" />
      </button>
      {open && (
        <div role="menu" className="appear absolute top-[calc(100%+6px)] left-1/2 z-30 box-border flex w-[300px] max-w-[calc(100vw-48px)] -translate-x-1/2 flex-col rounded-card border border-line bg-white p-1 text-left shadow-pop">
          {samples.isPending && <span className="p-2 text-xs text-ink-4">Loading…</span>}
          {samples.data?.samples.map((sample) => (
            <button
              key={sample.name}
              type="button"
              role="menuitem"
              className="rowbtn flex items-center gap-2.5 rounded-small border-0 bg-transparent p-1.5 text-left"
              onClick={() => { setOpen(false); onPick(sample) }}
            >
              <img src={sample.url} alt="" className="h-9 w-[54px] flex-none rounded-[4px] border border-line object-cover" />
              <span className="flex min-w-0 flex-1 flex-col gap-px">
                <span className="truncate text-[13px] font-medium">{sample.label}</span>
                <span className="truncate text-xs text-ink-4">{sample.note}</span>
              </span>
              <span className="tag flex-none">Synthetic</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function DropZone({ onFiles, onSample, error }: { onFiles: (files: File[]) => void; onSample: (sample: SampleSlide) => void; error: string | null }) {
  const [over, setOver] = useState(false)
  const input = useRef<HTMLInputElement | null>(null)
  return (
    <div className="flex flex-col gap-3">
      <div
        onDragOver={(event) => { event.preventDefault(); setOver(true) }}
        onDragLeave={() => setOver(false)}
        onDrop={(event) => {
          event.preventDefault()
          setOver(false)
          onFiles(Array.from(event.dataTransfer.files))
        }}
        className="flex min-h-[420px] flex-col items-center justify-center gap-3 rounded-panel bg-white p-6 text-center transition-colors max-[660px]:min-h-[280px]"
        style={{ border: `1.5px dashed ${over ? '#5F6C74' : '#C7CFD4'}`, background: over ? '#F6F8F9' : '#FFFFFF' }}
      >
        <span className="grid h-10 w-10 place-items-center rounded-card bg-muted-bg text-ink-3">
          <UploadCloud size={18} strokeWidth={1.75} aria-hidden="true" />
        </span>
        <div className="flex flex-col gap-1">
          <span className="text-sm font-medium">
            Drop microscope photos here, or{' '}
            <button type="button" className="lnk font-medium" onClick={() => input.current?.click()}>choose files</button>
          </span>
          <span className="text-xs text-ink-4">JPG or PNG · one photo per field of view</span>
        </div>
        <SampleMenu onPick={onSample} />
        <input
          ref={input} type="file" accept="image/jpeg,image/png" multiple hidden
          onChange={(event) => {
            onFiles(Array.from(event.target.files ?? []))
            event.target.value = ''
          }}
        />
      </div>
      {error && <p role="alert" className="m-0 text-[13px] text-critical-text">{error}</p>}
      <ul className="m-0 flex list-none flex-col gap-1 p-0 text-xs text-ink-4">
        <li>Concentrate the sample so each photo holds about 20–50 larvae.</li>
        <li>Keep the counting-slide grid in view so sizes calibrate automatically.</li>
      </ul>
    </div>
  )
}

export default function NewCheckPage() {
  const floorQuery = useFloor()
  const floor = floorQuery.data
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const toast = useToast()
  const invalidate = useInvalidateAll()

  const [tankId, setTankId] = useState(params.get('tank') ?? '')
  const [sampledAt, setSampledAt] = useState(() => localDateTimeValue())
  const [photos, setPhotos] = useState<AnalysisResult[]>([])
  const [active, setActive] = useState(0)
  const [analysing, setAnalysing] = useState(false)
  const [analyseError, setAnalyseError] = useState<string | null>(null)
  const [bucket, setBucket] = useState<string | null>(null)
  const [concentration, setConcentration] = useState<string | null>(null)
  const [water, setWater] = useState<WaterForm>(EMPTY_WATER)
  const [waterOpen, setWaterOpen] = useState(true)
  const [notes, setNotes] = useState('')
  const [summary, setSummary] = useState<Summary | null>(null)
  const [estimate, setEstimate] = useState<Estimate | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const viewer = useRef<PhotoViewerHandle | null>(null)
  const addInput = useRef<HTMLInputElement | null>(null)

  const activeTanks = useMemo(() => (floor?.tanks ?? []).filter((t) => t.level !== 'empty'), [floor])
  const tank = activeTanks.find((t) => t.id === tankId) ?? null
  const tankQuery = useTank(tank?.id)
  const line = floor?.lines.find((l) => l.id === tank?.line_id) ?? null

  const bucketValue = bucket ?? String(floor?.settings.bucket_l ?? 20)
  const concentrationValue = concentration ?? String(floor?.settings.concentration ?? 50)
  const allDetections = useMemo(() => photos.flatMap((p) => p.detections), [photos])
  const totalVolume = useMemo(() => {
    const volumes = photos.map((p) => p.photo_volume_ml).filter((v): v is number => v !== null)
    return volumes.length ? volumes.reduce((a, b) => a + b, 0) : null
  }, [photos])
  const scale = photos.find((p) => p.um_per_px)?.um_per_px ?? null
  // A photo with no scale has no volume, so it can't count towards the estimate
  const unscaledCount = photos.filter((p) => !p.photo_volume_ml).length
  const mixedScales = unscaledCount > 0 && unscaledCount < photos.length
  const estimateDetections = useMemo(
    () => (mixedScales ? photos.filter((p) => p.photo_volume_ml).flatMap((p) => p.detections) : null),
    [photos, mixedScales],
  )
  const quick = useMemo(() => quickSummary(allDetections), [allDetections])

  // Live summary and estimate while correcting (debounced 100 ms)
  useEffect(() => {
    if (photos.length === 0) return
    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      try {
        const res = await fetch('/api/summarize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            detections: allDetections,
            um_per_px: scale,
            photo_volume_ml: totalVolume,
            estimate_detections: estimateDetections,
            tank_id: tank?.id ?? null,
            sample: { bucket_l: toNumberOrNull(bucketValue) || null, concentration: toNumberOrNull(concentrationValue) || null },
          }),
        })
        if (!res.ok) return
        const body: { summary: Summary; estimate: Estimate } = await res.json()
        setSummary(body.summary)
        setEstimate(body.estimate)
      } catch {
        /* aborted by a newer edit */
      }
    }, 100)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [allDetections, estimateDetections, photos.length, scale, totalVolume, tank?.id, bucketValue, concentrationValue])

  const analyseFiles = async (files: File[]) => {
    const usable = files.filter((f) => /^image\/(jpeg|png)$/.test(f.type) || /\.(jpe?g|png)$/i.test(f.name))
    if (files.length > 0 && usable.length === 0) {
      setAnalyseError("That file isn't a photo Thetis can read. Use a JPG or PNG.")
      return
    }
    if (usable.length === 0) return
    setAnalysing(true)
    setAnalyseError(null)
    try {
      const firstNew = photos.length
      const results: AnalysisResult[] = []
      for (const file of usable) results.push(await postFile<AnalysisResult>('/api/analyze', file))
      setPhotos((current) => [...current, ...results])
      setActive(firstNew)
    } catch (error) {
      setAnalyseError(error instanceof Error ? error.message : "That photo couldn't be analysed.")
    } finally {
      setAnalysing(false)
    }
  }

  const analyseSample = async (sample: SampleSlide) => {
    setAnalysing(true)
    setAnalyseError(null)
    try {
      const firstNew = photos.length
      const result = await postJSON<AnalysisResult>(`/api/samples/${sample.name}/analyze`)
      setPhotos((current) => [...current, result])
      setActive(firstNew)
    } catch (error) {
      setAnalyseError(error instanceof Error ? error.message : "That slide couldn't be analysed.")
    } finally {
      setAnalysing(false)
    }
  }

  // Review walks through every photo: when this one has nothing left to check, move to the next that does
  const wantsReview = useRef(false)
  useEffect(() => {
    if (!wantsReview.current) return
    wantsReview.current = false
    viewer.current?.nextUnsure()
  }, [active])
  const reviewNext = () => {
    if (viewer.current?.nextUnsure()) return
    const next = photos.findIndex((p, i) => i !== active && p.detections.some((d) => d.unsure && d.cls !== 'ignore'))
    if (next >= 0) {
      wantsReview.current = true
      setActive(next)
    }
  }

  const updateActive = useCallback((next: Detection[]) => {
    setPhotos((current) => current.map((p, i) => (i === active ? { ...p, detections: next } : p)))
  }, [active])

  const applyScale = useCallback(async (umPerPx: number) => {
    const photo = photos[active]
    if (!photo) return
    const result = await postJSON<AnalysisResult>(`/api/analyze/${photo.token}/scale`, { um_per_px: umPerPx })
    // Keep everything a person or Claude added: the same objects come back under the same ids
    const old = new Map(photo.detections.map((d) => [d.id, d]))
    const merged = result.detections.map((d) => {
      const before = old.get(d.id)
      if (!before) return d
      const touched = before.source !== 'auto' || before.claude !== null || before.clump_n !== d.clump_n || (!before.unsure && d.unsure)
      return touched ? { ...d, cls: before.cls, source: before.source, unsure: before.unsure, clump_n: before.clump_n, claude: before.claude } : d
    })
    const manual = photo.detections.filter((d) => d.source === 'manual').map((d) => ({ ...d, length_um: d.length_px * umPerPx }))
    setPhotos((current) => current.map((p, i) => (i === active ? { ...result, detections: [...merged, ...manual] } : p)))
  }, [photos, active])

  const save = useMutation({
    mutationFn: () => postJSON<SaveResult>('/api/checks', {
      tank_id: tankId,
      sampled_at: sampledAt ? `${sampledAt}:00` : null,
      photos: photos.map((p) => ({ token: p.token, detections: p.detections })),
      sample: { bucket_l: toNumberOrNull(bucketValue), concentration: toNumberOrNull(concentrationValue) },
      water: {
        temp_c: toNumberOrNull(water.temp_c), salinity_ppt: toNumberOrNull(water.salinity_ppt), ph: toNumberOrNull(water.ph),
        omega_arag: toNumberOrNull(water.omega_arag), do_mgl: toNumberOrNull(water.do_mgl),
      },
      notes,
    }),
    onSuccess: async (result) => {
      await invalidate()
      toast(result.message, result.level)
      navigate(`/?tank=${result.tank_id}`)
    },
    onError: (error) => setSaveError(error instanceof Error ? error.message : "That check didn't save."),
  })

  if (floorQuery.isError) return <><TopBar crumbs={['New check']} hideNewCheck /><ErrorState error={floorQuery.error} onRetry={() => floorQuery.refetch()} /></>
  if (!floor) return <><TopBar crumbs={['New check']} hideNewCheck /><LoadingState /></>

  const current = photos[active] ?? null
  const hasPhoto = photos.length > 0
  const shownSummary = hasPhoto ? summary : null
  const canSave = !!tank && hasPhoto && !analysing && !save.isPending
  const removePhoto = (index: number) => {
    setPhotos((list) => list.filter((_, i) => i !== index))
    setActive((value) => Math.max(0, value >= index ? value - 1 : value))
  }

  const tabs = (
    <div role="tablist" aria-label="Photos in this check" className="flex flex-wrap items-center gap-1">
      {photos.map((photo, index) => (
        <span key={photo.token} className="flex items-center rounded-small" style={{ background: index === active ? '#F1F4F6' : 'transparent' }}>
          <button type="button" role="tab" aria-selected={index === active} className="h-7 cursor-pointer rounded-small border-0 bg-transparent pr-1 pl-2 text-xs font-medium" onClick={() => setActive(index)}>
            Photo {index + 1}
          </button>
          <button type="button" className="grid h-7 w-6 cursor-pointer place-items-center border-0 bg-transparent text-ink-4 hover:text-ink" aria-label={`Remove photo ${index + 1}`} onClick={() => removePhoto(index)}>
            <X size={12} strokeWidth={1.75} />
          </button>
        </span>
      ))}
      <button type="button" className="ghost !h-7 !gap-1 !rounded-small !px-2 !text-xs" onClick={() => addInput.current?.click()} disabled={analysing}>
        {analysing ? <Spinner /> : <Plus size={12} strokeWidth={2} aria-hidden="true" />}
        Add photo
      </button>
      <input ref={addInput} type="file" accept="image/jpeg,image/png" multiple hidden onChange={(event) => { analyseFiles(Array.from(event.target.files ?? [])); event.target.value = '' }} />
    </div>
  )

  const counted = quick.n_live + quick.n_abnormal + quick.n_dead

  return (
    <>
      <TopBar crumbs={['New check']} hideNewCheck />
      <div className="flex min-w-0 flex-1 flex-wrap items-start max-[1099px]:flex-col max-[1099px]:items-stretch">
        <div className="min-w-0 flex-[1_1_480px] p-6 max-[660px]:flex-none max-[660px]:p-4 min-[1100px]:sticky min-[1100px]:top-0">
          {!hasPhoto && !analysing && <DropZone onFiles={analyseFiles} onSample={analyseSample} error={analyseError} />}
          {!hasPhoto && analysing && (
            <div role="status" className="flex min-h-[420px] items-center justify-center gap-2 rounded-panel text-[13px] text-ink-2" style={{ border: '1.5px dashed #C7CFD4' }}>
              <Spinner />
              Finding larvae…
            </div>
          )}
          {current && (
            <div className="flex flex-col gap-2">
              <PhotoViewer
                ref={viewer}
                key={current.url}
                url={current.url} width={current.width} height={current.height}
                detections={current.detections} editable onChange={updateActive} onScale={applyScale} tabs={tabs}
              />
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-4">
                {current.synthetic && <span className="tag">Synthetic sample</span>}
                <span className="tnum">
                  {counted} larvae
                  {current.um_per_px ? ` · ${current.um_per_px.toFixed(2)} µm/px · ${current.calibration === 'grid' ? 'grid calibration' : current.calibration === 'manual' ? 'manual scale' : 'preset scale'}` : ''}
                  {current.photo_volume_ml ? ` · ${current.photo_volume_ml.toFixed(4)} mL in view` : ''}
                </span>
                {!current.um_per_px && (
                  <>
                    <span>·</span>
                    <button type="button" className="lnk" onClick={() => viewer.current?.startScale()}>Add a scale</button>
                  </>
                )}
                {analyseError && <span role="alert" className="text-critical-text">{analyseError}</span>}
              </div>
            </div>
          )}
        </div>

        <aside aria-label="Check details" className="box-border flex w-[380px] flex-none flex-col border-l border-divider max-[1099px]:w-full max-[1099px]:border-t max-[1099px]:border-l-0">
          <PanelSection label="Tank and time">
            <div className="flex flex-col gap-1">
              <label htmlFor="tank" className="text-xs text-ink-4">Tank</label>
              <select id="tank" className="field max-[660px]:!h-11" value={tankId} onChange={(event) => setTankId(event.target.value)}>
                <option value="">Choose a tank</option>
                {activeTanks.map((t) => <option key={t.id} value={t.id}>{t.id} · {t.age_text}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="sampled-at" className="text-xs text-ink-4">Sampled at</label>
              <input id="sampled-at" type="datetime-local" className="field tnum max-[660px]:!h-11" value={sampledAt} onChange={(event) => setSampledAt(event.target.value)} />
            </div>
          </PanelSection>

          {hasPhoto ? (
            <>
              <CountsPanel summary={quick}>
                <CheckActions
                  photoRef={current?.token ?? null} detections={current?.detections ?? []} totalUnsure={quick.n_unsure}
                  onOpinions={(asked, opinions) => setPhotos((list) => list.map((p) => (
                    p.token === asked ? { ...p, detections: withOpinions(p.detections, opinions) } : p
                  )))}
                  onReview={reviewNext}
                />
                <OpinionList detections={current?.detections ?? []} onChange={updateActive} onSelect={(id) => viewer.current?.select(id)} />
              </CountsPanel>
              <SizePanel summary={shownSummary ?? { mean_len_um: null, sd_len_um: null, cv: null, stage: null, hist: null }} previousHist={tankQuery.data?.latest_check?.hist ?? null} calibrated={scale !== null} />
              <GutPanel gut={shownSummary?.gut ?? null} />
              <EstimatePanel
                bucket={bucketValue} concentration={concentrationValue} onBucket={setBucket} onConcentration={setConcentration}
                estimate={hasPhoto ? estimate : null}
                note={mixedScales ? `${unscaledCount === 1 ? '1 photo has' : `${unscaledCount} photos have`} no scale, so the estimate leaves ${unscaledCount === 1 ? 'it' : 'them'} out.` : undefined}
              />
            </>
          ) : (
            <PanelSection label="What comes next">
              <span className="text-[13px] leading-normal text-ink-3">Counts, sizes and the tank estimate appear here once the photo is analysed.</span>
            </PanelSection>
          )}

          <WaterPanel
            value={water} onChange={setWater} lineName={line?.name ?? null} lineWater={line?.water ?? null}
            open={waterOpen} onToggle={() => setWaterOpen((v) => !v)}
          />

          <PanelSection title="Notes" label="Notes">
            <textarea className="field" rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} aria-label="Notes" placeholder="Anything worth remembering about this sample" />
          </PanelSection>

          <div className="flex flex-col gap-2 border-t border-divider p-4">
            {saveError && <p role="alert" className="m-0 text-[13px] text-critical-text">{saveError}</p>}
            <button
              type="button"
              className="solid w-full max-[660px]:!h-11"
              disabled={!canSave}
              onClick={() => { setSaveError(null); save.mutate() }}
            >
              {save.isPending && <Spinner light />}
              Save check
            </button>
            <button type="button" className="ghost w-full max-[660px]:!h-11" onClick={() => { if (window.history.length > 1) navigate(-1); else navigate('/') }}>Cancel</button>
            {!canSave && !save.isPending && (
              <span className="text-center text-xs text-ink-4">
                {!tank && !hasPhoto ? 'Choose a tank and add a photo to save.' : !tank ? 'Choose a tank to save.' : !hasPhoto ? 'Add a photo to save.' : ''}
              </span>
            )}
          </div>
        </aside>
      </div>
    </>
  )
}
