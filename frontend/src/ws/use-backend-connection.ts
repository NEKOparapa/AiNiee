import { useEffect } from 'react'
import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { ApiError } from '@/api/client'
import { configQueryOptions } from '@/api/config'
import { queryKeys } from '@/api/query-client'
import { taskQueryOptions } from '@/api/tasks'
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

  const refreshTask = () => {
    void client.fetchQuery({ ...taskQueryOptions(revision), staleTime: 0 }).catch(handleFailure)
  }

  const refreshSnapshots = () => {
    void client.fetchQuery({ ...configQueryOptions(revision), staleTime: 0 }).catch(handleFailure)
    refreshTask()
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
