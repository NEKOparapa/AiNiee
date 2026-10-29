import type { PropsWithChildren } from 'react'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useConnectionStore } from '@/stores/connection'
import { ApiError } from './client'
import { analysisKey, useAnalysis, useSaveAnalysis, useAnalysisTables, type AnalysisDocument } from './analysis'

const document: AnalysisDocument = { project_id: 'analysis-test', characters: [{ source: 'Alice', recommended_translation: '爱丽丝', gender: '女', occurrence_count: 2, note: '', custom: { confidence: 0.95 } }], terms: [], non_translate: [], metadata: { extension: { keep: true } } }
let client: QueryClient
beforeEach(() => { client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); useConnectionStore.getState().connect('http://127.0.0.1:8000', 'analysis-fixed-token') })
afterEach(() => { client.clear(); vi.unstubAllGlobals(); useConnectionStore.getState().disconnect() })
function Wrapper({ children }: PropsWithChildren) { return <QueryClientProvider client={client}>{children}</QueryClientProvider> }

it('retains metadata and cancels older snapshots before storing a successful save', async () => {
  const revision = useConnectionStore.getState().revision
  let resolveSnapshot!: (value: Response) => void
  const captured: unknown[] = []
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    if (request.method === 'GET') return new Promise<Response>(resolve => { resolveSnapshot = resolve })
    captured.push(await request.json())
    return Response.json(document)
  }))
  renderHook(() => useAnalysis(document.project_id), { wrapper: Wrapper })
  await waitFor(() => expect(resolveSnapshot).toBeDefined())
  const save = renderHook(() => useSaveAnalysis(), { wrapper: Wrapper })
  await act(async () => { await save.result.current.mutateAsync(document) })
  await act(async () => { resolveSnapshot(Response.json({ ...document, characters: [] })) })
  expect(captured).toEqual([document])
  expect(client.getQueryData([...analysisKey(revision), document.project_id])).toEqual(document)
})

it('keeps the confirmed document on a project conflict', async () => {
  const key = [...analysisKey(useConnectionStore.getState().revision), document.project_id]
  client.setQueryData(key, document)
  vi.stubGlobal('fetch', vi.fn(async () => Response.json({ detail: 'project_changed' }, { status: 409 })))
  const save = renderHook(() => useSaveAnalysis(), { wrapper: Wrapper })
  await act(async () => { await expect(save.result.current.mutateAsync({ ...document, characters: [] })).rejects.toEqual(new ApiError(409, 'project_changed')) })
  expect(client.getQueryData(key)).toEqual(document)
})

it('does not read when disconnected and maps publication targets to shared table kinds', async () => {
  const paths: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => { paths.push(new URL(request.url).pathname); return Response.json({ tables: [], active_table_id: null }) }))
  const glossary = renderHook(() => useAnalysisTables('characters'), { wrapper: Wrapper })
  await waitFor(() => expect(glossary.result.current.isSuccess).toBe(true))
  const exclusions = renderHook(() => useAnalysisTables('non_translate'), { wrapper: Wrapper })
  await waitFor(() => expect(exclusions.result.current.isSuccess).toBe(true))
  expect(paths).toEqual(['/api/v1/tables/glossary', '/api/v1/tables/exclusion'])
  act(() => useConnectionStore.getState().disconnect())
  const snapshot = renderHook(() => useAnalysis('retained-id'), { wrapper: Wrapper })
  expect(snapshot.result.current.fetchStatus).toBe('idle')
})
