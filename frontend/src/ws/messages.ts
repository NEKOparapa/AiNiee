import type { LogMessage, TaskUpdateMessage, WsMessage } from '@/api/types'
import { useBackendStore } from '@/stores/backend'

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function finite(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

export function parseMessage(raw: unknown): WsMessage | null {
  if (typeof raw !== 'string') return null
  try {
    const value: unknown = JSON.parse(raw)
    if (!record(value) || !finite(value.seq) || !Number.isInteger(value.seq) || value.seq < 1 ||
        !finite(value.ts) || typeof value.type !== 'string' || !record(value.data)) return null
    if (value.type === 'log') {
      const entries = value.data.entries
      if (!Array.isArray(entries) || !entries.every((entry: unknown) => record(entry) && finite(entry.ts) &&
        typeof entry.level === 'string' && typeof entry.logger === 'string' && typeof entry.message === 'string')) return null
    }
    if (value.type === 'task.update') {
      for (const name of ['line', 'total_line', 'token', 'time', 'start_time', 'total_requests', 'error_requests', 'total_completion_tokens']) {
        if (value.data[name] !== undefined && value.data[name] !== null && !finite(value.data[name])) return null
      }
    }
    // The exported backend schema remains the source of the wire type. The
    // envelope checks above keep malformed frames out of UI state.
    return value as WsMessage
  } catch {
    return null
  }
}

export function applyMessage(message: WsMessage) {
  const state = useBackendStore.getState()
  state.setLatestSeq(message.seq)
  if (message.type === 'task.update') {
    state.updateProgress((message as TaskUpdateMessage).data)
  } else if (message.type === 'log') {
    state.appendLogs((message as LogMessage).data.entries)
  }
  // Lifecycle messages trigger a REST snapshot in the connection hook. A late
  // throttled progress frame never switches an idle/completed task to running.
}

export function needsTaskRefresh(message: WsMessage): boolean {
  if (typeof message.type !== 'string') return false
  return /^(task\.(start|stop|stop\.done|completed|state\.changed)|analysis\.task\.(start|update|done)|(?:gloss\.task|api\.test)\.(start|done)|table\..*\.(start|done))$/.test(message.type)
}
