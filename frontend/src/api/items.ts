import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { components, paths } from './generated/schema'
import { assertCurrentConnection, getApiClient } from './client'
import { projectError, projectKeys } from './projects'
import { queryKeys } from './query-client'
import { useConnectionStore } from '@/stores/connection'

export type Item = components['schemas']['ItemRecord']
export type ItemQuery = NonNullable<paths['/api/v1/projects/current/items']['get']['parameters']['query']>
export type ItemPatch = components['schemas']['ItemPatchRequest']
export const itemKeys = {
  all: (revision: number) => [...queryKeys.connection(revision), 'items'] as const,
  list: (revision: number, projectId: string, query: ItemQuery) => [...itemKeys.all(revision), projectId, query] as const,
}

export function useItems(projectId: string | undefined, query: ItemQuery) {
  const revision = useConnectionStore(s => s.revision)
  const connected = useConnectionStore(s => s.connection !== null)
  return useQuery({
    queryKey: itemKeys.list(revision, projectId ?? '', query), enabled: connected && Boolean(projectId),
    queryFn: async ({ signal }) => {
      const result = await getApiClient(assertCurrentConnection(revision)).GET('/api/v1/projects/current/items', { params: { query }, signal })
      if (!result.data) projectError(result.response.status, result.error)
      return result.data
    },
  })
}

export function usePatchItem() {
  const revision = useConnectionStore(s => s.revision)
  const client = useQueryClient()
  return useMutation({
    mutationFn: async ({ file, index, body }: { file: string; index: number; body: ItemPatch }) => {
      const result = await getApiClient(assertCurrentConnection(revision)).PATCH('/api/v1/projects/current/items/{file}/{index}', { params: { path: { file, index } }, body })
      if (!result.data) projectError(result.response.status, result.error)
      return result.data
    },
    onSuccess: async () => {
      if (useConnectionStore.getState().revision !== revision) return
      await Promise.all([
        client.invalidateQueries({ queryKey: itemKeys.all(revision) }),
        client.invalidateQueries({ queryKey: projectKeys.stats(revision) }),
        client.invalidateQueries({ queryKey: projectKeys.files(revision) }),
      ])
    },
  })
}
