import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getJSON, postJSON } from './client'
import type { DecisionView, Floor, TankDetail } from './types'

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
      [['floor'], ['tank'], ['tanks'], ['decisions'], ['checks'], ['check'], ['photos-tree']].map((queryKey) =>
        client.invalidateQueries({ queryKey }),
      ),
    )
}

export type DecisionVerb = 'approve' | 'dismiss' | 'undo'

export function useDecide() {
  const invalidate = useInvalidateAll()
  return useMutation({
    mutationFn: ({ id, verb, note }: { id: number; verb: DecisionVerb; note?: string }) =>
      postJSON<DecisionView>(`/api/decisions/${id}/${verb}`, verb === 'undo' ? undefined : { note: note ?? null }),
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
