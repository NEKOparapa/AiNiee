import { queryOptions, useQuery } from '@tanstack/react-query'
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
