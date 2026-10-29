import { create } from 'zustand'
import type { LogEntry, TaskCurrent, TaskProgress } from '@/api/types'

const LOG_LIMIT = 500
type BackendState = {
  currentTask: TaskCurrent | null
  progress: TaskProgress | null
  logs: LogEntry[]
  latestSeq: number
  setCurrentTask: (task: TaskCurrent) => void
  updateProgress: (progress: TaskProgress) => void
  appendLogs: (logs: LogEntry[]) => void
  setLatestSeq: (seq: number) => void
  clearLogs: () => void
  reset: () => void
}

export const useBackendStore = create<BackendState>((set) => ({
  currentTask: null,
  progress: null,
  logs: [],
  latestSeq: 0,
  setCurrentTask: (task) => set({ currentTask: task, progress: task.progress }),
  updateProgress: (progress) => set((state) => ({ progress: { ...state.progress, ...progress } })),
  appendLogs: (logs) => set((state) => ({ logs: [...state.logs, ...logs].slice(-LOG_LIMIT) })),
  setLatestSeq: (latestSeq) => set({ latestSeq }),
  clearLogs: () => set({ logs: [] }),
  reset: () => set({ currentTask: null, progress: null, logs: [], latestSeq: 0 }),
}))
