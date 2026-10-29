import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { components, operations } from './generated/schema'
import { assertCurrentConnection, getApiClient } from './client'
import { projectError } from './projects'
import { queryKeys } from './query-client'
import { useConnectionStore } from '@/stores/connection'

export type PromptKind = operations['get_prompt']['parameters']['path']['kind']
export type LibraryKind = operations['get_prompt_library']['parameters']['query']['kind']
export type PromptDocument = components['schemas']['PromptDocument']
export type PromptLibrary = components['schemas']['PromptLibrary']
export type LibraryPrompt = components['schemas']['LibraryPrompt']
export const promptKeys = { all: (revision: number) => [...queryKeys.connection(revision), 'prompts'] as const }

export function usePrompt(kind: PromptKind) {
  const revision = useConnectionStore(s => s.revision)
  const connected = useConnectionStore(s => s.connection !== null)
  return useQuery({
    queryKey: [...promptKeys.all(revision), kind], enabled: connected,
    queryFn: async ({ signal }) => {
      const result = await getApiClient(assertCurrentConnection(revision)).GET('/api/v1/prompts/{kind}', { params: { path: { kind } }, signal })
      if (!result.data) projectError(result.response.status, result.error)
      return result.data
    },
  })
}

export function useSavePrompt(kind: PromptKind) {
  const revision = useConnectionStore(s => s.revision)
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (body: PromptDocument) => {
      const result = await getApiClient(assertCurrentConnection(revision)).PUT('/api/v1/prompts/{kind}', { params: { path: { kind } }, body })
      if (!result.data) projectError(result.response.status, result.error)
      return result.data
    },
    onMutate: async () => { await client.cancelQueries({ queryKey: promptKeys.all(revision) }) },
    onSuccess: async data => {
      await client.cancelQueries({ queryKey: promptKeys.all(revision) })
      if (useConnectionStore.getState().revision !== revision) return
      client.setQueryData([...promptKeys.all(revision), kind], data)
      await client.invalidateQueries({ queryKey: queryKeys.config(revision) })
    },
  })
}

export function usePromptLibrary(kind: LibraryKind) {
  const revision = useConnectionStore(s => s.revision)
  const connected = useConnectionStore(s => s.connection !== null)
  return useQuery({
    queryKey: [...promptKeys.all(revision), 'library', kind], enabled: connected,
    queryFn: async ({ signal }) => {
      const result = await getApiClient(assertCurrentConnection(revision)).GET('/api/v1/prompt-library', { params: { query: { kind } }, signal })
      if (!result.data) projectError(result.response.status, result.error)
      return result.data
    },
  })
}

export function useSaveLibraryPrompt(kind: LibraryKind) {
  const revision = useConnectionStore(s => s.revision)
  const client = useQueryClient()
  return useMutation({ mutationFn: async (body: components['schemas']['PromptUpsertRequest']) => {
    const result = await getApiClient(assertCurrentConnection(revision)).POST('/api/v1/prompt-library', { params: { query: { kind } }, body })
    if (!result.data) projectError(result.response.status, result.error)
    return result.data
  }, onMutate: async () => { await client.cancelQueries({ queryKey: promptKeys.all(revision) }) }, onSuccess: async data => {
    await client.cancelQueries({ queryKey: promptKeys.all(revision) })
    if (useConnectionStore.getState().revision !== revision) return
    client.setQueryData([...promptKeys.all(revision), 'library', kind], data)
    await Promise.allSettled([client.invalidateQueries({ queryKey: [...promptKeys.all(revision), kind] }), client.invalidateQueries({ queryKey: queryKeys.config(revision) })])
  } })
}

export function useDeleteLibraryPrompt(kind: LibraryKind) {
  const revision = useConnectionStore(s => s.revision)
  const client = useQueryClient()
  return useMutation({ mutationFn: async (id: string) => {
    const result = await getApiClient(assertCurrentConnection(revision)).DELETE('/api/v1/prompt-library', { params: { query: { kind, id } } })
    if (!result.data) projectError(result.response.status, result.error)
    return result.data
  }, onMutate: async () => { await client.cancelQueries({ queryKey: promptKeys.all(revision) }) }, onSuccess: async data => {
    await client.cancelQueries({ queryKey: promptKeys.all(revision) })
    if (useConnectionStore.getState().revision !== revision) return
    client.setQueryData([...promptKeys.all(revision), 'library', kind], data)
    await Promise.allSettled([client.invalidateQueries({ queryKey: [...promptKeys.all(revision), kind] }), client.invalidateQueries({ queryKey: queryKeys.config(revision) })])
  } })
}
