import { useQuery } from '@tanstack/react-query'
import { Folder } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { getJSON } from '../api/client'
import type { CheckDetail, Level, Severity } from '../api/types'
import { OutlinedPhoto } from '../components/photo/OutlinedPhoto'
import { TopBar } from '../components/shell/TopBar'
import { EmptyState, ErrorState, LoadingState, StatusPill } from '../components/ui'
import { LARVA_COLOR, severityText } from '../lib/levels'

interface TreeCheck { id: number; when_text: string; summary: string; level: Level; thumb_url: string | null; n_photos: number; batch_code: string | null }
interface TreeTank { id: string; level: Level; note: string; n_photos: number; n_checks: number; footer: string | null; checks: TreeCheck[] }
interface TreeRoom { id: string; name: string; n_photos: number; tanks: TreeTank[] }

const RING: Record<Level, string> = {
  ok: '1.5px solid #9AA6AE', watch: '2px solid #C98A0B', risk: '2px solid #E0702A', critical: '2px solid #D93A2F', empty: '1.5px dashed #C7CFD4',
}
const SELECTED = '#F1F4F6'

function Ring({ level }: { level: Level }) {
  return <span aria-hidden="true" className="box-border h-2.5 w-2.5 flex-none rounded-full" style={{ border: RING[level] }} />
}

function ColumnTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="px-2.5 pt-1.5 pb-2 text-xs font-medium text-ink-4">{children}</h2>
}

function FactCell({ label, value, note, noteColor, index }: { label: string; value: string; note?: string; noteColor?: string; index: number }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5 px-3.5 py-3 max-[520px]:px-2" style={{ borderLeft: index % 3 === 0 ? '0' : '1px solid #EEF2F4', borderTop: index < 3 ? '0' : '1px solid #EEF2F4' }}>
      <dt className="text-xs text-ink-4">{label}</dt>
      <dd className="tnum text-base font-semibold">{value}</dd>
      <dd className="text-xs" style={{ color: noteColor ?? '#66737B' }}>{note || ' '}</dd>
    </div>
  )
}

const CALIBRATION_TEXT: Record<string, string> = {
  grid: 'read from the counting-slide grid', manual: 'from a scale drawn by hand', preset: 'from a microscope preset',
}

function Preview({ checkId }: { checkId: number }) {
  const query = useQuery({ queryKey: ['check', String(checkId)], queryFn: () => getJSON<CheckDetail & { previous: { pct_dead: number | null; pct_abnormal: number | null; mean_len_um: number | null; cv: number | null; gut: number | null; days_ago: number } | null }>(`/api/checks/${checkId}`) })
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />
  const check = query.data
  if (!check) return <LoadingState />
  const photo = check.photos[0]
  const prev = check.previous
  const s = check.severities
  const counted = check.n_counted
  const pct = (n: number) => (counted ? `${Math.round((100 * n) / counted)}% of counted` : '')
  const color = (severity?: Severity) => (severity ? severityText(severity) : undefined)
  const dead = check.pct_dead ?? 0
  const deadNote = prev?.pct_dead !== null && prev?.pct_dead !== undefined && Math.round(dead) !== Math.round(prev.pct_dead)
    ? `${Math.round(dead)}%, ${dead > prev.pct_dead ? 'up' : 'down'} from ${Math.round(prev.pct_dead)}%`
    : `${Math.round(dead)}% of counted`
  const lengthNote = prev?.mean_len_um !== null && prev?.mean_len_um !== undefined && check.mean_len_um !== null
    ? `${check.mean_len_um >= prev.mean_len_um ? '+' : '−'}${Math.abs(Math.round(check.mean_len_um - prev.mean_len_um))} µm in ${Math.max(1, Math.round(prev.days_ago))} ${Math.max(1, Math.round(prev.days_ago)) === 1 ? 'day' : 'days'}`
    : 'First check'
  const change = (now: number | null, before: number | null | undefined) => {
    if (now === null || before === null || before === undefined) return ''
    if (now.toFixed(2) === before.toFixed(2)) return `same as last check`
    return `${now > before ? 'up' : 'down'} from ${before.toFixed(2)}`
  }
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-x-3.5 gap-y-2.5">
        <div className="flex min-w-0 flex-[1_1_240px] flex-col gap-[3px]">
          <span className="text-lg font-semibold tracking-[-0.015em]">{counted} larvae counted</span>
          <span className="text-[12.5px] leading-[1.35] text-ink-4">
            {photo ? `Photo 1 of ${check.photos.length}${photo.um_per_px ? ` · ${photo.um_per_px.toFixed(2)} µm per pixel, ${CALIBRATION_TEXT[photo.calibration] ?? ''}` : ' · no scale'}` : 'No photo'}
          </span>
        </div>
        <StatusPill level={check.level} large />
        <Link to={`/checks/${check.id}`} className="ghost no-underline">Review outlines</Link>
      </div>
      {photo && (
        <div className="relative box-border aspect-[3/2] w-full overflow-hidden rounded-card border border-line bg-muted-bg">
          <OutlinedPhoto
            url={photo.url} width={photo.width} height={photo.height} detections={photo.detections}
            alt={`Microscope photo from the check of ${check.tank_id} on ${check.when_text}, with each larva outlined: green live, orange abnormal, red dead`}
          >
            {photo.synthetic && <span className="absolute top-2 left-2 rounded-small bg-white/95 px-1.5 py-0.5 text-[11px] font-medium text-ink-3 shadow-[0_1px_2px_rgba(15,26,32,0.08)]">Synthetic sample</span>}
          </OutlinedPhoto>
        </div>
      )}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-ink-2">
        {[['live', 'Live'], ['abnormal', 'Abnormal'], ['dead', 'Dead (empty shell)']].map(([cls, label]) => (
          <span key={cls} className="flex items-center gap-1.5">
            <span className="box-border h-2 w-2 rounded-full" style={{ border: `2px solid ${LARVA_COLOR[cls]}` }} />
            {label}
          </span>
        ))}
      </div>
      <dl className="grid grid-cols-3 rounded-card border border-line">
        <FactCell index={0} label="Live" value={String(check.n_live)} note={pct(check.n_live)} />
        <FactCell index={1} label="Abnormal" value={String(check.n_abnormal)} note={pct(check.n_abnormal)} noteColor={color(s.abnormal)} />
        <FactCell index={2} label="Dead" value={String(check.n_dead)} note={deadNote} noteColor={color(s.dead)} />
        <FactCell index={3} label="Mean shell length" value={check.length_text} note={lengthNote} noteColor={color(s.growth)} />
        <FactCell index={4} label="Size spread (CV)" value={check.summary.cv === null ? '—' : check.summary.cv.toFixed(2)} note={change(check.summary.cv, prev?.cv)} noteColor={color(s.spread)} />
        <FactCell index={5} label="Gut fullness" value={check.gut_text} note={change(check.gut, prev?.gut)} noteColor={color(s.gut)} />
      </dl>
    </div>
  )
}

export default function PhotoLibraryPage() {
  const query = useQuery({ queryKey: ['photos-tree'], queryFn: () => getJSON<{ rooms: TreeRoom[] }>('/api/photos/tree') })
  const [params, setParams] = useSearchParams()

  if (query.isError) return <><TopBar crumbs={['Photo library']} /><ErrorState error={query.error} onRetry={() => query.refetch()} /></>
  if (!query.data) return <><TopBar crumbs={['Photo library']} /><LoadingState /></>
  const rooms = query.data.rooms
  if (rooms.length === 0) return <><TopBar crumbs={['Photo library']} /><EmptyState title="No photos yet">Photos from saved checks appear here.</EmptyState></>

  // Default to the most recent photo of the worst tank, walking the same order the design shows
  const room = rooms.find((r) => r.id === params.get('room')) ?? rooms[0]
  const worstRank: Record<Level, number> = { critical: 4, risk: 3, watch: 2, ok: 1, empty: 0 }
  const withChecks = room.tanks.filter((t) => t.n_checks > 0)
  const defaultTank = [...withChecks].sort((a, b) => worstRank[b.level] - worstRank[a.level])[0] ?? room.tanks[0]
  const tank = room.tanks.find((t) => t.id === params.get('tank')) ?? defaultTank
  const checks = tank?.checks ?? []
  const requested = Number(params.get('check'))
  const check = checks.find((c) => c.id === requested) ?? checks[0] ?? null

  const go = (next: { room?: string; tank?: string | null; check?: number | null }) => {
    const p = new URLSearchParams()
    p.set('room', next.room ?? room.id)
    const nextTank = next.tank === undefined ? tank?.id : next.tank
    if (nextTank) p.set('tank', nextTank)
    const nextCheck = next.check === undefined ? check?.id : next.check
    if (nextCheck) p.set('check', String(nextCheck))
    setParams(p, { replace: true })
  }

  const crumbs = ['Photo library', room.name, ...(tank ? [tank.id] : []), ...(check ? [check.when_text] : [])]

  return (
    <>
      <TopBar crumbs={crumbs} newCheckHref={tank && tank.level !== 'empty' ? `/checks/new?tank=${tank.id}` : '/checks/new'} />
      <div className="flex flex-1 max-[1099px]:flex-col">
        <section aria-label="Rooms" className="flex w-[196px] flex-none flex-col gap-px border-r border-divider px-2 py-2.5 max-[1099px]:w-full max-[1099px]:border-r-0 max-[1099px]:border-b">
          <ColumnTitle>Rooms</ColumnTitle>
          {rooms.map((r) => (
            <button
              key={r.id}
              type="button"
              aria-current={r.id === room.id}
              className="rowbtn flex items-center gap-2.5 rounded-[7px] border-0 px-2.5 py-2 text-left max-[660px]:min-h-11"
              style={{ background: r.id === room.id ? SELECTED : undefined }}
              onClick={() => go({ room: r.id, tank: null, check: null })}
            >
              <Folder size={15} strokeWidth={1.7} className="flex-none text-ink-4" aria-hidden="true" />
              <span className="flex-1 text-[13px]" style={{ fontWeight: r.id === room.id ? 500 : 400 }}>{r.name}</span>
              <span className="tnum text-xs text-ink-4">{r.n_photos}</span>
            </button>
          ))}
        </section>

        <section aria-label={`Tanks in ${room.name}`} className="flex w-[232px] flex-none flex-col gap-px border-r border-divider px-2 py-2.5 max-[1099px]:w-full max-[1099px]:border-r-0 max-[1099px]:border-b">
          <ColumnTitle>{room.name}</ColumnTitle>
          {room.tanks.map((t) => (
            <button
              key={t.id}
              type="button"
              aria-current={t.id === tank?.id}
              className="rowbtn flex items-center gap-2.5 rounded-[7px] border-0 px-2.5 py-2 text-left max-[660px]:min-h-11"
              style={{ background: t.id === tank?.id ? SELECTED : undefined }}
              onClick={() => go({ tank: t.id, check: null })}
            >
              <Ring level={t.level} />
              <span className="mono w-[38px] flex-none text-[12.5px] font-medium">{t.id}</span>
              <span className="min-w-0 flex-1 truncate text-xs text-ink-4">{t.note}</span>
              <span className="tnum text-xs text-[#8A969D]">{t.n_photos}</span>
            </button>
          ))}
        </section>

        <section aria-label={tank ? `Checks for ${tank.id}` : 'Checks'} className="flex w-[268px] flex-none flex-col gap-px border-r border-divider px-2 py-2.5 max-[1099px]:w-full max-[1099px]:border-r-0 max-[1099px]:border-b">
          <ColumnTitle>{tank ? `${tank.id} · ${tank.n_checks} ${tank.n_checks === 1 ? 'check' : 'checks'}` : 'Checks'}</ColumnTitle>
          {checks.length === 0 && <span className="px-2.5 py-2 text-xs text-ink-4">No checks for this tank yet.</span>}
          {checks.map((c) => (
            <button
              key={c.id}
              type="button"
              aria-current={c.id === check?.id}
              className="rowbtn flex items-center gap-2.5 rounded-[7px] border-0 px-2.5 py-[7px] text-left"
              style={{ background: c.id === check?.id ? SELECTED : undefined }}
              onClick={() => go({ check: c.id })}
            >
              {c.thumb_url
                ? <img src={c.thumb_url} alt="" loading="lazy" className="box-border h-9 w-[54px] flex-none rounded-[4px] border border-line object-cover" />
                : <span className="box-border h-9 w-[54px] flex-none rounded-[4px] border border-line bg-muted-bg" />}
              <span className="flex min-w-0 flex-1 flex-col gap-px">
                <span className="truncate text-[13px]" style={{ fontWeight: c.id === check?.id ? 500 : 400 }}>{c.when_text}</span>
                <span className="truncate text-xs text-ink-4">{c.summary}</span>
              </span>
              <Ring level={c.level} />
            </button>
          ))}
          {tank?.footer && <p className="m-0 mt-auto border-t border-divider p-2.5 text-xs text-ink-4 max-[1099px]:mt-2">{tank.footer}</p>}
        </section>

        <section aria-label="Preview" className="min-w-0 flex-1 px-[22px] pt-5 pb-6 max-[660px]:px-4">
          {check ? <Preview checkId={check.id} /> : <EmptyState title="Nothing to preview">Choose a tank with saved checks.</EmptyState>}
        </section>
      </div>
    </>
  )
}
