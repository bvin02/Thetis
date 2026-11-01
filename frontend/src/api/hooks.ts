import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getJSON, postJSON } from './client'
import type { AdvisorPage, DecisionView, Floor, TankDetail } from './types'

export function useFloor() {
  return useQuery({
    queryKey: ['floor'],
    queryFn: () => getJSON<Floor>('/api/floor'),
    refetchInterval: 60_000,
  })
}

export function useTank(tankId: string | null | undefined) {
  return useQuery({
    queryKey: ['tank', tankId],
    queryFn: () => getJSON<TankDetail>(`/api/tanks/${tankId}`),
    enabled: !!tankId,
    placeholderData: keepPreviousData,
  })
}

/** Everything a saved check, decision or batch change can touch. */
export function useInvalidateAll() {
  const client = useQueryClient()
  return () =>
    Promise.all(
      [['floor'], ['tank'], ['tanks'], ['decisions'], ['checks'], ['check'], ['photos-tree'], ['advisor']].map((queryKey) =>
        client.invalidateQueries({ queryKey }),
      ),
    )
}

export type DecisionVerb = 'approve' | 'dismiss' | 'undo'

export function useDecide() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: ({ action, verb, note }: { action: DecisionView; verb: DecisionVerb; note?: string }) => {
      if (action.id === null) {
        // A suggestion gets its row when someone answers it
        return postJSON<DecisionView>('/api/advisor/answer', {
          action: action.action,
          tank_id: action.tank_id,
          verb,
          text: action.action === 'claude_suggestion' ? action.title : null,
        })
      }
      return postJSON<DecisionView>(`/api/decisions/${action.id}/${verb}`, verb === 'undo' ? undefined : { note: note ?? null })
    },
    onSettled: () => invalidate(),
  })
}

export function useAdvisor() {
  return useQuery({ queryKey: ['advisor'], queryFn: () => getJSON<AdvisorPage>('/api/advisor') })
}

export function useSetPlant() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: (change: { buffer?: string; disinfectant?: string }) => postJSON('/api/advisor/plant', change),
    onSettled: () => invalidate(),
  })
}

export interface ClaudeStatus {
  enabled: boolean
  model: string
  used_today: number
  limit: number
}

export function useClaudeStatus() {
  return useQuery({ queryKey: ['claude-status'], queryFn: () => getJSON<ClaudeStatus>('/api/claude/status'), staleTime: 30_000 })
}
