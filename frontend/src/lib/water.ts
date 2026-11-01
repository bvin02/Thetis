import type { WaterReadings } from '../api/types'

export type WaterForm = Record<keyof WaterReadings, string>
export const EMPTY_WATER: WaterForm = { temp_c: '', salinity_ppt: '', ph: '', omega_arag: '', do_mgl: '' }
