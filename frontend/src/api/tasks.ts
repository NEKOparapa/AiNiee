import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { components } from './generated/schema'
import { projectError } from './projects'
import { useConnectionStore } from '@/stores/connection'
import { useBackendStore } from '@/stores/backend'
import { useUiContextStore } from '@/stores/ui-context'
import { assertCurrentConnection, getApiClient, throwApiError } from './client'
import { queryKeys } from './query-client'

export function taskQueryOptions(revision: number) {
  return queryOptions({
    queryKey: queryKeys.task(revision),
    queryFn: async ({ signal }) => {
      const result = await getApiClient(assertCurrentConnection(revision)).GET('/api/v1/tasks/current', { signal })
      if (!result.data) throwApiError(result.response.status)
      if (!signal.aborted && useConnectionStore.getState().revision === revision) {
        useBackendStore.getState().setCurrentTask(result.data)
        useUiContextStore.getState().setProjectId(result.data.project_id)
      }
      return result.data
    },
  })
}

export function useCurrentTask() {
  const revision = useConnectionStore((state) => state.revision)
  const connected = useConnectionStore((state) => state.connection !== null)
  return useQuery({ ...taskQueryOptions(revision), enabled: connected })
}

export function useTaskAction() {
  const revision = useConnectionStore(state => state.revision)
  const client = useQueryClient()
  return useMutation({
    mutationFn: async ({ mode, resume = false }: { mode: NonNullable<components['schemas']['TaskCurrentResponse']['mode']> | 'stop'; resume?: boolean }) => {
      const api = getApiClient(assertCurrentConnection(revision))
      const result = mode === 'translate' ? await api.POST('/api/v1/tasks/translate', { body: { continue: resume } })
        : mode === 'polish' ? await api.POST('/api/v1/tasks/polish', { body: { continue: resume } })
        : mode === 'analysis' ? await api.POST('/api/v1/tasks/analysis') : await api.POST('/api/v1/tasks/stop')
      if (!result.data) projectError(result.response.status, result.error)
      return result.data
    },
    onSuccess: async () => {
      if (useConnectionStore.getState().revision !== revision) return
      // A fast worker may finish before the POST response arrives. Fetch after
      // the acknowledgement instead of overwriting a newer WS snapshot.
      await client.cancelQueries({ queryKey: queryKeys.task(revision) })
      await client.fetchQuery({ ...taskQueryOptions(revision), staleTime: 0 }).catch(() => {})
    },
  })
}
