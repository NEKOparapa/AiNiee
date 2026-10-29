import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { components } from './generated/schema'
import { ApiError, assertCurrentConnection, getApiClient } from './client'
import { queryKeys } from './query-client'
import { useConnectionStore } from '@/stores/connection'

export type Platform = components['schemas']['PlatformResponse']
export type PlatformCreate = components['schemas']['PlatformCreate']
export type PlatformUpdate = components['schemas']['PlatformUpdate']
export type PlatformBindings = components['schemas']['PlatformBindings']
export type PlatformList = components['schemas']['PlatformListResponse']

export const platformQueryKey = (revision: number) => ['connection', revision, 'platforms'] as const

function failed(status: number, error: unknown): never {
  if (status === 401 || status === 403) throw new ApiError(status, 'unauthorized')
  const code = typeof error === 'object' && error !== null && 'detail' in error ? error.detail : undefined
  const allowed = ['operation_busy', 'platform_not_found', 'platform_preset_not_found', 'platform_url_required',
    'platform_credentials_required', 'invalid_platform', 'invalid_headers', 'invalid_platform_binding',
    'model_fetch_failed', 'model_fetch_unsupported']
  if (typeof code === 'string' && allowed.includes(code)) throw new ApiError(status, code)
  if (status === 409) throw new ApiError(status, 'operation_busy')
  if (status === 422) throw new ApiError(status, 'invalid_platform')
  throw new ApiError(status, 'request_failed')
}

export function platformErrorCode(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'connection.changed') return 'connection_changed'
    return error.code
  }
  return 'request_failed'
}

export function platformQueryOptions(revision: number) {
  return queryOptions({
    queryKey: platformQueryKey(revision),
    queryFn: async ({ signal }) => {
      const result = await getApiClient(assertCurrentConnection(revision)).GET('/api/v1/platforms', { signal })
      if (!result.data) failed(result.response.status, result.error)
      return result.data
    },
  })
}

export function usePlatforms() {
  const revision = useConnectionStore(state => state.revision)
  const connected = useConnectionStore(state => state.connection !== null)
  return useQuery({ ...platformQueryOptions(revision), enabled: connected })
}

function usePlatformWriteOptions() {
  const revision = useConnectionStore(state => state.revision)
  const client = useQueryClient()
  return {
    revision,
    scope: { id: `config-patch-${revision}` },
    onSuccess: async () => {
      if (useConnectionStore.getState().revision !== revision) return
      await Promise.all([
        client.invalidateQueries({ queryKey: platformQueryKey(revision) }),
        client.invalidateQueries({ queryKey: queryKeys.config(revision) }),
      ])
    },
  }
}

export function useCreatePlatform() {
  const { revision, ...options } = usePlatformWriteOptions()
  return useMutation({ ...options, mutationFn: async (body: PlatformCreate) => {
    const result = await getApiClient(assertCurrentConnection(revision)).POST('/api/v1/platforms', { body })
    if (!result.data) failed(result.response.status, result.error)
    return result.data
  } })
}

export function useUpdatePlatform() {
  const { revision, ...options } = usePlatformWriteOptions()
  return useMutation({ ...options, mutationFn: async ({ id, changes }: { id: string; changes: PlatformUpdate }) => {
    const result = await getApiClient(assertCurrentConnection(revision)).PUT('/api/v1/platforms/{platform_id}', {
      params: { path: { platform_id: id } }, body: changes,
    })
    if (!result.data) failed(result.response.status, result.error)
    return result.data
  } })
}

export function useDeletePlatform() {
  const { revision, ...options } = usePlatformWriteOptions()
  return useMutation({ ...options, mutationFn: async (id: string) => {
    const result = await getApiClient(assertCurrentConnection(revision)).DELETE('/api/v1/platforms/{platform_id}', {
      params: { path: { platform_id: id } },
    })
    if (!result.data) failed(result.response.status, result.error)
    return result.data
  } })
}

export function useSaveBindings() {
  const { revision, ...options } = usePlatformWriteOptions()
  return useMutation({ ...options, mutationFn: async (body: PlatformBindings) => {
    const result = await getApiClient(assertCurrentConnection(revision)).PUT('/api/v1/platforms/bindings', { body })
    if (!result.data) failed(result.response.status, result.error)
    return result.data
  } })
}

export function useTestPlatform() {
  const revision = useConnectionStore(state => state.revision)
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const result = await getApiClient(assertCurrentConnection(revision)).POST('/api/v1/platforms/{platform_id}/test', {
        params: { path: { platform_id: id } },
      })
      if (!result.data) failed(result.response.status, result.error)
      return result.data
    },
    onSettled: () => client.invalidateQueries({ queryKey: queryKeys.task(revision) }),
  })
}

export function usePlatformModels() {
  const revision = useConnectionStore(state => state.revision)
  return useMutation({ mutationFn: async (id: string) => {
    const result = await getApiClient(assertCurrentConnection(revision)).GET('/api/v1/platforms/{platform_id}/models', {
      params: { path: { platform_id: id } },
    })
    if (!result.data) failed(result.response.status, result.error)
    return result.data
  } })
}
