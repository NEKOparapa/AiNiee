import { useQuery } from '@tanstack/react-query'
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
