import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useConnectionStore } from '@/stores/connection'
import { assertCurrentConnection, getApiClient, throwApiError } from './client'
import { queryKeys } from './query-client'
import type { ConfigPatch } from './types'

export function configQueryOptions(revision: number) {
  return queryOptions({
    queryKey: queryKeys.config(revision),
    queryFn: async ({ signal }) => {
      const result = await getApiClient(assertCurrentConnection(revision)).GET('/api/v1/config', { signal })
      if (!result.data) throwApiError(result.response.status)
      return result.data
    },
  })
}

export function useConfig() {
  const revision = useConnectionStore((state) => state.revision)
  const connected = useConnectionStore((state) => state.connection !== null)
  return useQuery({ ...configQueryOptions(revision), enabled: connected })
}

export function usePatchConfig() {
  const revision = useConnectionStore((state) => state.revision)
  const client = useQueryClient()
  return useMutation({
    mutationKey: ['config-patch', revision],
    // Every setting uses the same scope so whole-config responses cannot race.
    scope: { id: `config-patch-${revision}` },
    mutationFn: async (patch: ConfigPatch) => {
      const result = await getApiClient(assertCurrentConnection(revision)).PATCH('/api/v1/config', { body: patch })
      if (!result.data) throwApiError(result.response.status)
      return result.data
    },
    onMutate: async () => {
      await client.cancelQueries({ queryKey: queryKeys.config(revision) })
    },
    onSuccess: async (config) => {
      // A reconnect can have started a fresh GET while PATCH was in flight.
      // Cancel that older read before accepting the successful write response.
      await client.cancelQueries({ queryKey: queryKeys.config(revision) })
      if (useConnectionStore.getState().revision === revision) client.setQueryData(queryKeys.config(revision), config)
    },
  })
}
