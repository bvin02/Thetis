import { useSetPlant } from '../../api/hooks'
import type { PlantView } from '../../api/types'

/** The chemicals this plant uses. Every dose and step on every page reads these. */
export function PlantCard({ plant }: { plant: PlantView }) {
  const setPlant = useSetPlant()
  return (
    <section aria-label="Your plant" className="flex flex-col gap-3 rounded-card border border-line p-4">
      <div className="flex flex-col gap-1">
        <h2 className="text-sm font-semibold">Your plant</h2>
        <span className="text-xs leading-[1.45] text-ink-4">Doses and steps use what you actually keep on site.</span>
      </div>
      <label className="flex flex-col gap-1.5 text-xs font-medium text-ink-3">
        pH buffer
        <select className="field font-normal max-[660px]:!h-11" value={plant.buffer} disabled={setPlant.isPending} onChange={(event) => setPlant.mutate({ buffer: event.target.value })}>
          {plant.buffers.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
        </select>
      </label>
      <label className="flex flex-col gap-1.5 text-xs font-medium text-ink-3">
        Disinfectant
        <select className="field font-normal max-[660px]:!h-11" value={plant.disinfectant} disabled={setPlant.isPending} onChange={(event) => setPlant.mutate({ disinfectant: event.target.value })}>
          {plant.disinfectants.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
        </select>
      </label>
    </section>
  )
}
