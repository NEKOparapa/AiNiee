import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { components } from './generated/schema'
import { ApiError, assertCurrentConnection, getApiClient, throwApiError } from './client'
import { queryKeys } from './query-client'
import { taskQueryOptions } from './tasks'
import { useConnectionStore } from '@/stores/connection'

export type ProjectFile = components['schemas']['ProjectFile']
export type ProjectHistory = components['schemas']['ProjectHistoryEntry']
export type DirectoryListing = components['schemas']['FileSystemListResponse']

export const projectKeys = {
  all: (revision: number) => [...queryKeys.connection(revision), 'projects'] as const,
  current: (revision: number) => [...projectKeys.all(revision), 'current'] as const,
  history: (revision: number) => [...projectKeys.all(revision), 'history'] as const,
  files: (revision: number) => [...projectKeys.all(revision), 'files'] as const,
  stats: (revision: number) => [...projectKeys.all(revision), 'stats'] as const,
}

export function projectError(status: number, error: unknown): never {
  if (error && typeof error === 'object' && 'detail' in error && typeof error.detail === 'string') {
    throw new ApiError(status, error.detail)
  }
  throwApiError(status)
}

export function currentProjectOptions(revision: number) {
  return queryOptions({
    queryKey: projectKeys.current(revision),
    queryFn: async ({ signal }) => {
      const result = await getApiClient(assertCurrentConnection(revision)).GET('/api/v1/projects/current', { signal })
      if (!result.data) projectError(result.response.status, result.error)
      return result.data
    },
  })
}

export function useCurrentProject() {
  const revision = useConnectionStore(s => s.revision)
  const connected = useConnectionStore(s => s.connection !== null)
  return useQuery({ ...currentProjectOptions(revision), enabled: connected })
}

export function useProjectHistory() {
  const revision = useConnectionStore(s => s.revision)
  const connected = useConnectionStore(s => s.connection !== null)
  return useQuery({
    queryKey: projectKeys.history(revision), enabled: connected,
    queryFn: async ({ signal }) => {
      const result = await getApiClient(assertCurrentConnection(revision)).GET('/api/v1/projects/history', { signal })
      if (!result.data) projectError(result.response.status, result.error)
      return result.data
    },
  })
}

export function useProjectFiles(enabled: boolean) {
  const revision = useConnectionStore(s => s.revision)
  return useQuery({
    queryKey: projectKeys.files(revision), enabled,
    queryFn: async ({ signal }) => {
      const result = await getApiClient(assertCurrentConnection(revision)).GET('/api/v1/projects/current/files', { signal })
      if (!result.data) projectError(result.response.status, result.error)
      return result.data
    },
  })
}

export function useProjectStats(enabled: boolean) {
  const revision = useConnectionStore(s => s.revision)
  return useQuery({
    queryKey: projectKeys.stats(revision), enabled,
    queryFn: async ({ signal }) => {
      const result = await getApiClient(assertCurrentConnection(revision)).GET('/api/v1/projects/current/stats', { signal })
      if (!result.data) projectError(result.response.status, result.error)
      return result.data
    },
  })
}

export function useOpenProject() {
  const revision = useConnectionStore(s => s.revision)
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (body: components['schemas']['ProjectOpenRequest']) => {
      const result = await getApiClient(assertCurrentConnection(revision)).POST('/api/v1/projects/open', { body })
      if (!result.data) projectError(result.response.status, result.error)
      return result.data
    },
    onSuccess: async () => {
      if (useConnectionStore.getState().revision !== revision) return
      await client.cancelQueries({ queryKey: projectKeys.all(revision) })
      // Files and statistics belong to a project, so never display the prior
      // project's cached values while its replacement snapshot is loading.
      client.removeQueries({ queryKey: projectKeys.files(revision) })
      client.removeQueries({ queryKey: projectKeys.stats(revision) })
      // The POST has succeeded. A later snapshot failure must remain a query
      // error, not turn the completed open into a failed mutation and retry.
      await Promise.allSettled([
        client.invalidateQueries({ queryKey: projectKeys.all(revision) }),
        client.invalidateQueries({ queryKey: queryKeys.config(revision) }),
        client.fetchQuery({ ...taskQueryOptions(revision), staleTime: 0 }),
      ])
    },
  })
}

export function useDeleteHistory() {
  const revision = useConnectionStore(s => s.revision)
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const result = await getApiClient(assertCurrentConnection(revision)).DELETE('/api/v1/projects/history/{project_id}', { params: { path: { project_id: id } } })
      if (!result.data) projectError(result.response.status, result.error)
      return result.data
    },
    onSuccess: async () => {
      if (useConnectionStore.getState().revision === revision) await client.invalidateQueries({ queryKey: projectKeys.history(revision) })
    },
  })
}

export function useDirectoryListing(path: string, enabled: boolean) {
  const revision = useConnectionStore(s => s.revision)
  return useQuery({
    queryKey: [...queryKeys.connection(revision), 'directory', path], enabled, retry: false,
    queryFn: async ({ signal }) => {
      const result = await getApiClient(assertCurrentConnection(revision)).POST('/api/v1/fs/list', { body: { path }, signal })
      if (!result.data) projectError(result.response.status, result.error)
      return result.data
    },
  })
}
