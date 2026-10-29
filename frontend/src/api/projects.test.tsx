import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import type { components } from './generated/schema'
import { useConnectionStore } from '@/stores/connection'
import { queryKeys } from './query-client'
import { useOpenProject } from './projects'

afterEach(() => { vi.unstubAllGlobals(); useConnectionStore.getState().disconnect() })

it('keeps a successful project open successful when the follow-up snapshot fails', async () => {
  useConnectionStore.getState().connect('http://127.0.0.1:8000', 'fixed-test-token')
  const revision = useConnectionStore.getState().revision
  const project: components['schemas']['ProjectSummary'] = {
    project_id: 'opened-once', project_name: 'Opened project', project_type: 'Txt',
    input_path: 'D:/source', project_create_time: '2026-01-01T12:00:00', file_count: 1, item_count: 2,
  }
  let opens = 0
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    if (request.method === 'POST' && new URL(request.url).pathname === '/api/v1/projects/open') {
      opens++
      return Response.json(project)
    }
    return Response.json({ detail: 'Snapshot temporarily unavailable' }, { status: 503 })
  }))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  const { result } = renderHook(() => useOpenProject(), { wrapper })
  await act(async () => { expect(await result.current.mutateAsync({ path: 'D:/source' })).toEqual(project) })
  expect(opens).toBe(1)
  await waitFor(() => expect(result.current.isSuccess).toBe(true))
  expect(client.getQueryState(queryKeys.task(revision))?.status).toBe('error')
  client.clear()
})
