// Shapes the backend returns. Keep in step with backend/app/services/views.py.

export type Level = 'critical' | 'risk' | 'watch' | 'ok' | 'empty'
export type Severity = 'critical' | 'risk' | 'watch'

export interface RoomNav {
  id: string
  name: string
  kind: string
  caption: string | null
  label_xy: number[] | null
  tank_count: number
  worst_level: Level
}

export interface Shell {
  seeded: boolean
  hatchery: { name: string; species: string | null }
  user: { name: string; initials: string; role: string }
  is_example: boolean
  rooms: RoomNav[]
  decisions_waiting: number
  settings: { bucket_l: number; concentration: number }
}

export interface TankSummary {
  id: string
  shape: 'circle' | 'rect'
  geom: { cx: number; cy: number; r: number; x: number; y: number; w: number; h: number }
  room_id: string
  room_name: string
  room_kind: string
  line_id: string | null
  line_name: string | null
  line_text: string
  line_alert: boolean
  status: string
  volume_l: number
  level: Level
  level_label: string
  pattern: string | null
  title: string
  chip: string
  reason: string
  batch_id: number | null
  batch_code: string | null
  day: number | null
  stage: string | null
  sub_text: string
  age_text: string
  live_est: number | null
  live_text: string
  survival: number | null
  survival_text: string
  last_check_at: string | null
  last_check_text: string
  latest_check_id: number | null
  forecast: string
}

export interface Chip {
  id: string
  level: Level
  level_label: string
  chip: string
  reason: string
}

export interface LineWater {
  temp_c: number | null
  salinity_ppt: number | null
  ph: number | null
  omega_arag: number | null
  do_mgl: number | null
  at: string
  when_text: string
}

export interface LineView {
  id: string
  name: string
  number: string
  card_xy: number[] | null
  omega: number | null
  ph: number | null
  reading_text: string
  water: LineWater | null
  alert: boolean
  since_text: string | null
  tank_ids: string[]
}

export interface HistoryCell {
  date: string
  date_text: string
  level: Level | null
  label: string
  change: string
}

export interface HistoryRow {
  tank_id: string
  level: Level
  cells: HistoryCell[]
}

export interface HistoryDay {
  date: string
  num: string
  sub: string
  is_today: boolean
}

export interface Floor extends Shell {
  now: string
  headline: string
  summary: string
  act_now: Chip[]
  act_label: string
  monitor: Chip[]
  monitor_label: string
  metrics: {
    larvae_total: number
    larvae_value: string
    larvae_unit: string
    tanks_running: number
    tanks_total: number
    avg_survival: number | null
    decisions_waiting: number
    next_check: { tank_id: string; text: string; overdue: boolean } | null
  }
  tanks: TankSummary[]
  lines: LineView[]
  history: { days: HistoryDay[]; rows: HistoryRow[] }
  default_tank: string | null
}

export type LarvaClass = 'live' | 'abnormal' | 'dead' | 'ignore'

export interface ClaudeOpinion {
  cls: 'live' | 'abnormal' | 'dead' | 'not_larva'
  confidence: 'low' | 'medium' | 'high'
  reason: string
  decided?: 'accepted' | 'kept'
}

export interface Detection {
  id: number
  cx: number
  cy: number
  contour: [number, number][]
  length_px: number
  length_um: number | null
  area_px: number
  solidity: number
  defect: number
  hollowness: number
  gut: number | null
  interior: number
  cls: LarvaClass
  auto_cls: LarvaClass
  unsure: boolean
  unsure_reason: string | null
  clump_n: number
  touches_edge: boolean
  source: 'auto' | 'corrected' | 'manual'
  claude: ClaudeOpinion | null
}

export interface PhotoView {
  id: number
  check_id: number
  url: string
  width: number
  height: number
  um_per_px: number | null
  calibration: 'grid' | 'preset' | 'manual' | 'none'
  grid_spacing_px: number | null
  volume_ml: number | null
  engine_version: string | null
  synthetic: boolean
  source_name: string | null
  detections: Detection[]
}

export interface ConditionRow {
  key: string
  label: string
  now: string
  cmp: string
  severity: Severity | 'context' | null
}

export interface DecisionView {
  id: number
  scope: 'tank' | 'line'
  tank_id: string | null
  line_id: string | null
  check_id: number | null
  action: string
  title: string
  cta: string
  done_text: string
  status: 'pending' | 'approved' | 'dismissed'
  created_at: string
  decided_at: string | null
  decided_by: string | null
  decided_text: string | null
  note: string | null
  is_example: boolean
}

export interface CheckRow {
  id: number
  tank_id: string
  batch_id: number
  batch_code: string | null
  sampled_at: string
  when_text: string
  day: number
  source: string
  n_live: number
  n_abnormal: number
  n_dead: number
  n_counted: number
  live_est: number | null
  live_text: string
  survival: number | null
  survival_text: string
  mean_len_um: number | null
  length_text: string
  growth_um_day: number | null
  growth_text: string
  pct_dead: number | null
  dead_text: string
  pct_abnormal: number | null
  abnormal_text: string
  gut: number | null
  gut_text: string
  omega_arag: number | null
  omega_text: string
  ph: number | null
  ph_text: string
  temp_c: number | null
  temp_text: string
  level: Level
  level_label: string
  pattern: string | null
  severities: Record<string, Severity>
  n_photos: number
  is_example: boolean
  room_id?: string
  room_name?: string
}

export interface SeriesPoint {
  day: number
  day_label: string
  check_id: number | null
  survival: number | null
  length_um: number | null
  pct_dead: number | null
  pct_abnormal: number | null
  omega: number | null
  ph: number | null
  temp_c: number | null
  level: Level
}

export interface TankDetail extends TankSummary {
  batch: { id: number; code: string; spawn_date: string; stocked: number; stocked_text: string; status: string } | null
  latest_check: {
    id: number
    sampled_at: string
    when_text: string
    n_live: number
    n_abnormal: number
    n_dead: number
    n_counted: number
    photo: PhotoView | null
    n_photos: number
    hist: number[] | null
  } | null
  condition: ConditionRow[]
  signals: { key: string; severity: Severity; value: number; prev: number | null; kind: string }[]
  growth_um_day: number | null
  loss_per_day: number | null
  rules_version: string | null
  series: { points: SeriesPoint[] }
  expected_growth_um_day: number
  chart_guides: { dead_watch: number; dead_critical: number; omega_target: number }
  actions: DecisionView[]
  actions_left: number
  checks: CheckRow[]
  decision_history: DecisionView[]
  past_batches: { id: number; code: string; spawn_date: string; stocked: number; status: string; outcome: string | null; closed_on: string | null; closed_text: string | null }[]
  line_water: LineWater | null
}

export interface Summary {
  n_live: number
  n_abnormal: number
  n_dead: number
  n_unsure: number
  n_ignored: number
  pct_dead: number
  pct_abnormal: number
  mean_len_um: number | null
  sd_len_um: number | null
  cv: number | null
  hist: number[] | null
  stage: string | null
  gut: number | null
  count_for_estimate: number
}

export interface Estimate {
  live_est: number | null
  survival: number | null
  stocked: number | null
  over_stocked: boolean
}

export interface AnalysisResult {
  token: string
  url: string
  filename: string | null
  synthetic: boolean
  source_name: string | null
  width: number
  height: number
  um_per_px: number | null
  calibration: PhotoView['calibration']
  grid_spacing_px: number | null
  photo_volume_ml: number | null
  detections: Detection[]
  engine_version: string
  ms: number
}

export interface SampleSlide {
  name: string
  label: string
  note: string
  url: string
}

export interface SaveResult {
  check_id: number
  tank_id: string
  level: Level
  pattern: string | null
  new_decisions: { id: number; action: string; scope: string; tank_id: string | null; line_id: string | null }[]
  message: string
  duplicate: boolean
}

export interface WaterReadings {
  temp_c: number | null
  salinity_ppt: number | null
  ph: number | null
  omega_arag: number | null
  do_mgl: number | null
}

export interface CheckDetail extends CheckRow {
  room_name: string
  line_id: string | null
  line_name: string | null
  stocked: number
  stocked_text: string
  bucket_l: number | null
  concentration: number | null
  photo_volume_ml: number | null
  water: WaterReadings
  notes: string | null
  created_by: string | null
  engine_version: string | null
  rules_version: string | null
  summary: Summary
  previous_hist: number[] | null
  snapshot: {
    level: Level
    level_label: string
    pattern: string | null
    title: string
    forecast: string
    condition: ConditionRow[]
    growth_um_day: number | null
    loss_per_day: number | null
    survival: number | null
  }
  photos: PhotoView[]
  created_text: string
}
