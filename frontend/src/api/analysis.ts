import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { components, operations } from './generated/schema'
import { assertCurrentConnection, getApiClient } from './client'
import { projectError } from './projects'
import { queryKeys } from './query-client'
import { useConnectionStore } from '@/stores/connection'

export type AnalysisDocument = components['schemas']['AnalysisDocument']
export type AnalysisView = operations['export_project_analysis']['parameters']['path']['view']
export const analysisKey = (revision: number) => [...queryKeys.connection(revision), 'analysis'] as const

export function useAnalysis(projectId?: string) {
  const revision = useConnectionStore(state => state.revision)
  const connected = useConnectionStore(state => state.connection !== null)
  return useQuery({
    queryKey: [...analysisKey(revision), projectId], enabled: connected && Boolean(projectId),
    queryFn: async ({ signal }) => {
      const result = await getApiClient(assertCurrentConnection(revision)).GET('/api/v1/projects/current/analysis', { signal })
      if (!result.data) projectError(result.response.status, result.error)
      return result.data
    },
  })
}

export function useSaveAnalysis() {
  const revision = useConnectionStore(state => state.revision)
  const client = useQueryClient()
  return useMutation({ mutationFn: async (body: AnalysisDocument) => {
    const result = await getApiClient(assertCurrentConnection(revision)).PUT('/api/v1/projects/current/analysis', { body })
    if (!result.data) projectError(result.response.status, result.error)
    return result.data
  }, onMutate: async body => {
    await client.cancelQueries({ queryKey: [...analysisKey(revision), body.project_id] })
  }, onSuccess: async data => {
    await client.cancelQueries({ queryKey: [...analysisKey(revision), data.project_id] })
    if (revision === useConnectionStore.getState().revision) client.setQueryData([...analysisKey(revision), data.project_id], data)
  } })
}

export function useAnalysisTables(view: AnalysisView) {
  const revision = useConnectionStore(state => state.revision)
  const connected = useConnectionStore(state => state.connection !== null)
  const name = view === 'non_translate' ? 'exclusion' : 'glossary'
  return useQuery({ queryKey: [...queryKeys.connection(revision), 'tables', name], enabled: connected, queryFn: async ({ signal }) => {
    const result = await getApiClient(assertCurrentConnection(revision)).GET('/api/v1/tables/{name}', { params: { path: { name } }, signal })
    if (!result.data) projectError(result.response.status, result.error)
    return result.data
  } })
}
