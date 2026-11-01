import { createContext, useContext } from 'react'
import type { Level } from '../api/types'

export const ToastContext = createContext<(text: string, level?: Level) => void>(() => {})

export function useToast() {
  return useContext(ToastContext)
}
