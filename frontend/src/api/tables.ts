import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { components, operations } from './generated/schema'
import { assertCurrentConnection, getApiClient } from './client'
import { projectError } from './projects'
import { queryKeys } from './query-client'
import { useConnectionStore } from '@/stores/connection'

export type TableName = operations['get_tables']['parameters']['path']['name']
export type TableCollection = components['schemas']['TableCollection']
export type PublicTable = components['schemas']['PublicTable']
export type TableImportRequest = components['schemas']['TableImportRequest']
export type TableDownload = components['schemas']['TableDownload']
export const tableKeys = { all: (revision: number) => [...queryKeys.connection(revision), 'tables'] as const }

export function useTables(name: TableName) {
  const revision = useConnectionStore(s => s.revision)
  const connected = useConnectionStore(s => s.connection !== null)
  return useQuery({ queryKey: [...tableKeys.all(revision), name], enabled: connected, queryFn: async ({ signal }) => {
    const result = await getApiClient(assertCurrentConnection(revision)).GET('/api/v1/tables/{name}', { params: { path: { name } }, signal })
    if (!result.data) projectError(result.response.status, result.error)
    return result.data
  } })
}

export function useSaveTables(name: TableName) {
  const revision = useConnectionStore(s => s.revision)
  const client = useQueryClient()
  return useMutation({ mutationFn: async (body: TableCollection) => {
    const result = await getApiClient(assertCurrentConnection(revision)).PUT('/api/v1/tables/{name}', { params: { path: { name } }, body })
    if (!result.data) projectError(result.response.status, result.error)
    return result.data
  }, onMutate: async () => { await client.cancelQueries({ queryKey: [...tableKeys.all(revision), name] }) }, onSuccess: async data => {
    await client.cancelQueries({ queryKey: [...tableKeys.all(revision), name] })
    if (useConnectionStore.getState().revision !== revision) return
    client.setQueryData([...tableKeys.all(revision), name], data)
    await client.invalidateQueries({ queryKey: queryKeys.config(revision) })
  } })
}

export function useImportTables(name: TableName) {
  const revision = useConnectionStore(s => s.revision)
  const client = useQueryClient()
  return useMutation({ mutationFn: async (body: TableImportRequest) => {
    const result = await getApiClient(assertCurrentConnection(revision)).POST('/api/v1/tables/{name}/import', { params: { path: { name } }, body })
    if (!result.data) projectError(result.response.status, result.error)
    return result.data
  }, onMutate: async variables => { if (!variables.preview) await client.cancelQueries({ queryKey: [...tableKeys.all(revision), name] }) }, onSuccess: async (data, variables) => {
    if (variables.preview || useConnectionStore.getState().revision !== revision) return
    await client.cancelQueries({ queryKey: [...tableKeys.all(revision), name] })
    client.setQueryData([...tableKeys.all(revision), name], data)
    await client.invalidateQueries({ queryKey: queryKeys.config(revision) })
  } })
}

export function useExportTables(name: TableName) {
  const revision = useConnectionStore(s => s.revision)
  return useMutation({ mutationFn: async (query: operations['export_tables']['parameters']['query']) => {
    const result = await getApiClient(assertCurrentConnection(revision)).GET('/api/v1/tables/{name}/export', { params: { path: { name }, query } })
    if (!result.data) projectError(result.response.status, result.error)
    return result.data
  } })
}

export function downloadTable(file: TableDownload) {
  const bytes = Uint8Array.from(atob(file.content_base64), char => char.charCodeAt(0))
  const url = URL.createObjectURL(new Blob([bytes], { type: file.media_type }))
  const link = document.createElement('a')
  link.href = url; link.download = file.filename; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
