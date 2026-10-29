import { useMutation, useQuery } from '@tanstack/react-query'
import { useConnectionStore } from '@/stores/connection'
import { assertCurrentConnection, getApiClient, throwApiError } from './client'
import { queryKeys } from './query-client'

export function useVersion() {
  const revision = useConnectionStore((state) => state.revision)
  const connected = useConnectionStore((state) => state.connection !== null)
  return useQuery({
    queryKey: queryKeys.version(revision),
    enabled: connected,
    queryFn: async ({ signal }) => {
      const result = await getApiClient(assertCurrentConnection(revision)).GET('/api/v1/version', { signal })
      if (!result.data) throwApiError(result.response.status)
      return result.data
    },
  })
}

export function useShutdown() {
  return useMutation({
    mutationFn: async () => {
      const revision = useConnectionStore.getState().revision
      const result = await getApiClient(assertCurrentConnection(revision)).POST('/api/v1/shutdown')
      if (!result.data) throwApiError(result.response.status)
      // Carry the originating connection through the async response. Mutation
      // options can change after a new connection is selected.
      return revision
    },
    onSuccess: revision => { useConnectionStore.getState().markShutdownRequested(revision) },
  })
}
