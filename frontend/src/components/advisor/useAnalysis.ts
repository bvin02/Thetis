import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, postStream } from '../../api/client'
import type { AdvisorPage, AnalysisProgress } from '../../api/types'

/**
 * Runs Claude's analysis and follows its progress. Opening the page starts one if the stored one is out of date, and
 * rejoins one already running. The server keeps going if the page is closed, so nothing is lost or paid for twice.
 */
export function useAnalysis(page: AdvisorPage | undefined) {
  const client = useQueryClient()
  const [progress, setProgress] = useState<AnalysisProgress | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const opened = useRef(false)
  const abort = useRef<AbortController | null>(null)

  const start = useCallback((force = false) => {
    abort.current?.abort()
    const controller = new AbortController()
    abort.current = controller
    setRunning(true)
    setError(null)
    setProgress(null)
    postStream<AnalysisProgress>('/api/advisor/analyze', { force }, (event) => {
      setProgress(event)
      if (event.error) setError(event.error)
    }, controller.signal)
      .catch((failure: unknown) => {
        if (controller.signal.aborted) return
        setError(failure instanceof ApiError ? failure.message : "Claude didn't answer. Try again.")
      })
      .finally(async () => {
        if (controller.signal.aborted) return
        // Keep showing what was written until the stored version has arrived, so nothing flickers
        await Promise.all([
          client.invalidateQueries({ queryKey: ['advisor'] }),
          client.invalidateQueries({ queryKey: ['claude-status'] }),
        ])
        setRunning(false)
        setProgress(null)
      })
  }, [client])

  // Decided once, when the page opens. A change made while it's open (a new chemical, say) marks the brief out of
  // date and offers "Run again", rather than spending credits and replacing the brief under someone's eyes.
  useEffect(() => {
    if (!page || opened.current) return
    const timer = window.setTimeout(() => {
      opened.current = true
      if (page.claude.enabled && page.seeded && (page.analysis_running || !page.analysis_fresh)) start(false)
    }, 0)
    return () => window.clearTimeout(timer)
  }, [page, start])

  useEffect(() => () => abort.current?.abort(), [])

  return { progress, running, error, start }
}
