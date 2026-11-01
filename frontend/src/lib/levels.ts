import type { Level, Severity } from '../api/types'

// Status colours from the design source (Main.dc.html). Colour is only for problems; Normal is grey.
export const LEVEL: Record<Level, {
  label: string; color: string; text: string; pill: string; tint: string; chip: string; chipBorder: string; sw: number; rank: number
}> = {
  critical: { label: 'Critical', color: '#D93A2F', text: '#B42318', pill: '#FEF3F2', tint: '#FEF3F2', chip: '#FEF3F2', chipBorder: '#F2C4BF', sw: 2.75, rank: 4 },
  risk: { label: 'At risk', color: '#E0702A', text: '#B54708', pill: '#FFF6ED', tint: '#FFF6ED', chip: '#FFF6ED', chipBorder: '#F3D0B4', sw: 2.25, rank: 3 },
  watch: { label: 'Watch', color: '#C98A0B', text: '#8E6206', pill: '#FEF9EC', tint: '#FFFFFF', chip: '#FFFFFF', chipBorder: '#E2E8EC', sw: 2, rank: 2 },
  ok: { label: 'Normal', color: '#A7B3BA', text: '#3E4B53', pill: '#F1F4F6', tint: '#FFFFFF', chip: '#FFFFFF', chipBorder: '#E2E8EC', sw: 1.25, rank: 1 },
  empty: { label: 'Empty', color: '#C7CFD4', text: '#66737B', pill: '#F1F4F6', tint: '#FFFFFF', chip: '#FFFFFF', chipBorder: '#E2E8EC', sw: 1.25, rank: 0 },
}

export const SWATCH: Record<Level, { background: string; border: string }> = {
  critical: { background: '#D93A2F', border: '0' },
  risk: { background: '#E0702A', border: '0' },
  watch: { background: '#C98A0B', border: '0' },
  ok: { background: '#DCE3E7', border: '1px solid #A7B3BA' },
  empty: { background: '#FFFFFF', border: '1.5px dashed #AEB9C0' },
}

export const LEGEND: Level[] = ['critical', 'risk', 'watch', 'ok', 'empty']

export function isProblem(level: Level): boolean {
  return level === 'critical' || level === 'risk' || level === 'watch'
}

export const SEVERITY_DOT: Record<string, string> = {
  critical: '#D93A2F',
  risk: '#E0702A',
  watch: '#C98A0B',
  context: '#A7B3BA',
}

export function severityText(severity: Severity | 'context' | null | undefined): string {
  if (severity === 'critical') return '#B42318'
  if (severity === 'risk') return '#B54708'
  if (severity === 'watch') return '#8E6206'
  return '#0F1A20'
}

// Outline colours on photos
export const LARVA_COLOR: Record<string, string> = {
  live: '#2E8B57',
  abnormal: '#C2620E',
  dead: '#C2362B',
  ignore: '#AEB9C0',
}
