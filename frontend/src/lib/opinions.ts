import type { ClaudeOpinion, Detection, LarvaClass } from '../api/types'

const OPINION_CLASS: Record<ClaudeOpinion['cls'], LarvaClass> = {
  live: 'live', abnormal: 'abnormal', dead: 'dead', not_larva: 'ignore',
}

export const OPINION_NAME: Record<ClaudeOpinion['cls'], string> = {
  live: 'Live', abnormal: 'Abnormal', dead: 'Dead', not_larva: 'Not a larva',
}

/** Accept: take Claude's class. Keep: stay with the current class. Either way a person has looked. */
export function decideOpinion(detection: Detection, decision: 'accepted' | 'kept'): Detection {
  if (!detection.claude) return detection
  const claude = { ...detection.claude, decided: decision }
  if (decision === 'kept') return { ...detection, claude, unsure: false }
  return {
    ...detection,
    claude,
    unsure: false,
    cls: OPINION_CLASS[detection.claude.cls],
    source: detection.source === 'manual' ? 'manual' : 'corrected',
  }
}

export function pendingOpinions(detections: Detection[]): Detection[] {
  return detections.filter((d) => d.claude && !d.claude.decided)
}
