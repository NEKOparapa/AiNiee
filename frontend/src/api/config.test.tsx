import type { PropsWithChildren } from 'react'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useConnectionStore } from '@/stores/connection'
import { ApiError } from './client'
import { usePatchConfig } from './config'
import { queryKeys } from './query-client'

let client: QueryClient

beforeEach(() => {
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  useConnectionStore.getState().connect('http://127.0.0.1:8000', 'fixed-test-token')
})

afterEach(() => {
  client.clear()
  vi.unstubAllGlobals()
})

function Wrapper({ children }: PropsWithChildren) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

function response(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
}

it('serializes writes across separate setting hooks and keeps the newest complete config', async () => {
  const pending: Array<(response: Response) => void> = []
  const requests: Request[] = []
  const fetchMock = vi.fn((request: Request) => {
    requests.push(request)
    return new Promise<Response>((resolve) => { pending.push(resolve) })
  })
  vi.stubGlobal('fetch', fetchMock)
  const first = renderHook(() => usePatchConfig(), { wrapper: Wrapper })
  const second = renderHook(() => usePatchConfig(), { wrapper: Wrapper })
  let firstResult: Promise<unknown>
  let secondResult: Promise<unknown>
  act(() => {
    firstResult = first.result.current.mutateAsync({ accent_color: '#112233' })
    secondResult = second.result.current.mutateAsync({ output_filename_suffix: '_new' })
  })
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
  expect(requests[0]?.headers.get('Authorization')).toBe('Bearer fixed-test-token')
  expect(await requests[0]?.clone().json()).toEqual({ accent_color: '#112233' })
  await act(async () => {
    pending[0]?.(response({ accent_color: '#112233', output_filename_suffix: '_old' }))
    await firstResult!
  })
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  await act(async () => {
    pending[1]?.(response({ accent_color: '#112233', output_filename_suffix: '_new' }))
    await secondResult!
  })
  expect(client.getQueryData(queryKeys.config(useConnectionStore.getState().revision))).toEqual({ accent_color: '#112233', output_filename_suffix: '_new' })
})

it('keeps confirmed values on failure and allows an explicit retry', async () => {
  const revision = useConnectionStore.getState().revision
  client.setQueryData(queryKeys.config(revision), { accent_color: '#808b9d' })
  const fetchMock = vi.fn().mockResolvedValueOnce(response({ detail: 'failure' }, 500)).mockResolvedValueOnce(response({ accent_color: '#123456' }))
  vi.stubGlobal('fetch', fetchMock)
  const hook = renderHook(() => usePatchConfig(), { wrapper: Wrapper })
  await act(async () => {
    await expect(hook.result.current.mutateAsync({ accent_color: '#123456' })).rejects.toBeInstanceOf(ApiError)
  })
  await waitFor(() => expect(hook.result.current.isError).toBe(true))
  expect(client.getQueryData(queryKeys.config(revision))).toEqual({ accent_color: '#808b9d' })
  await act(async () => { await hook.result.current.mutateAsync({ accent_color: '#123456' }) })
  await waitFor(() => expect(hook.result.current.isSuccess).toBe(true))
  expect(client.getQueryData(queryKeys.config(revision))).toEqual({ accent_color: '#123456' })
})
