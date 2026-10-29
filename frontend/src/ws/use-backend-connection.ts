import { useEffect } from 'react'
import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { ApiError } from '@/api/client'
import { configQueryOptions } from '@/api/config'
import { queryKeys } from '@/api/query-client'
import { taskQueryOptions } from '@/api/tasks'
import { projectKeys } from '@/api/projects'
import { platformQueryKey } from '@/api/platforms'
import { useBackendStore } from '@/stores/backend'
import { useConnectionStore, type ConnectionDetails } from '@/stores/connection'
import { useUiContextStore } from '@/stores/ui-context'
import { BackendSocket, type SocketFactory } from './client'
import { applyMessage, needsTaskRefresh } from './messages'

export function startBackendConnection(
  client: QueryClient,
  connection: ConnectionDetails,
  revision: number,
  socketFactory?: SocketFactory,
) {
  let active = true
  const current = () => active && useConnectionStore.getState().revision === revision

  const handleFailure = (error: unknown) => {
    if (!current()) return
    if (error instanceof ApiError && [401, 403].includes(error.status)) {
      socket.stop()
      useConnectionStore.getState().setStatus('disconnected', 'connection.unauthorized')
    }
  }

  let taskRefreshing = false
  let taskDirty = false
  const refreshTask = () => {
    taskDirty = true
    if (taskRefreshing) return
    taskRefreshing = true
    void (async () => {
      try {
        while (taskDirty && current()) {
          taskDirty = false
          await client.fetchQuery({ ...taskQueryOptions(revision), staleTime: 0 }).catch(handleFailure)
        }
      } finally { taskRefreshing = false }
    })()
  }

  const refreshSnapshots = () => {
    void client.fetchQuery({ ...configQueryOptions(revision), staleTime: 0 }).catch(handleFailure)
    refreshTask()
    void client.invalidateQueries({ queryKey: projectKeys.all(revision) })
    void client.invalidateQueries({ queryKey: platformQueryKey(revision) })
    for (const name of ['items', 'analysis', 'tables', 'prompts', 'prompt-library']) {
      void client.invalidateQueries({ queryKey: [...queryKeys.connection(revision), name] })
    }
  }

  const socket = new BackendSocket(connection, {
    onStatus: (status, error) => {
      if (current()) useConnectionStore.getState().setStatus(status, error)
    },
    onOpen: () => {
      if (!current()) return
      useBackendStore.getState().setLatestSeq(0)
      refreshSnapshots()
    },
    onMessage: (message) => {
      if (!current()) return
      applyMessage(message)
      if (needsTaskRefresh(message)) refreshTask()
      if (message.type === 'project.changed' || message.type === 'project.history.changed') {
        void client.invalidateQueries({ queryKey: projectKeys.all(revision) })
        void client.invalidateQueries({ queryKey: queryKeys.config(revision) })
        if (message.type === 'project.changed') refreshTask()
      }
      if (message.type === 'platforms.changed') {
        void client.invalidateQueries({ queryKey: platformQueryKey(revision) })
        void client.invalidateQueries({ queryKey: queryKeys.config(revision) })
      }
      if (['table.update', 'task.state.changed', 'project.changed', 'analysis.task.done', 'analysis.data.changed'].includes(message.type)) {
        for (const name of ['items', 'analysis']) void client.invalidateQueries({ queryKey: [...queryKeys.connection(revision), name] })
        void client.invalidateQueries({ queryKey: projectKeys.all(revision) })
      }
      if (message.type === 'tables.changed' || message.type === 'prompts.changed') {
        for (const name of ['tables', 'prompts', 'prompt-library']) void client.invalidateQueries({ queryKey: [...queryKeys.connection(revision), name] })
        void client.invalidateQueries({ queryKey: queryKeys.config(revision) })
      }
    },
  }, socketFactory)

  socket.start()
  // An HTTP check also detects invalid credentials when the browser hides the
  // rejected WebSocket handshake status behind close code 1006.
  refreshSnapshots()
  return () => {
    active = false
    socket.stop()
    void client.cancelQueries({ queryKey: queryKeys.connection(revision) })
    client.removeQueries({ queryKey: queryKeys.connection(revision) })
  }
}

export function useBackendConnection() {
  const client = useQueryClient()
  const connection = useConnectionStore((state) => state.connection)
  const revision = useConnectionStore((state) => state.revision)

  useEffect(() => { useConnectionStore.getState().initialize() }, [])

  useEffect(() => {
    useBackendStore.getState().reset()
    useUiContextStore.getState().setProjectId(null)
    if (!connection) return
    return startBackendConnection(client, connection, revision)
  }, [client, connection, revision])
}
