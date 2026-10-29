import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import i18n from '@/i18n'
import { useConnectionStore } from '@/stores/connection'
import { useBackendConnection } from '@/ws/use-backend-connection'
import { AboutPage } from './AboutPage'

let client: QueryClient
beforeEach(async () => {
  await i18n.changeLanguage('zh-CN')
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  sessionStorage.clear()
  useConnectionStore.getState().connect('http://127.0.0.1:8000', 'fixed-exit-token')
})
afterEach(() => {
  client.clear()
  useConnectionStore.getState().disconnect()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function ConnectedAbout() {
  useBackendConnection()
  return <AboutPage/>
}
const show = (connected = false) => render(<QueryClientProvider client={client}>{connected ? <ConnectedAbout/> : <AboutPage/>}</QueryClientProvider>)
const version = () => Response.json({ version: 'fixed-version' })

it('requires confirmation, and closing the page does not send an exit request', async () => {
  const fetcher = vi.fn(async (_request: Request) => version())
  vi.stubGlobal('fetch', fetcher)
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
  const view = show()
  await screen.findByText('fixed-version')
  expect(screen.getByText('关闭浏览器标签页不会停止后台服务。需要退出时，请使用下方按钮。')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '退出应用' }))
  expect(confirm).toHaveBeenCalledWith(expect.stringContaining('保存进度后退出'))
  view.unmount()
  expect(fetcher.mock.calls.every(([request]) => request.method === 'GET')).toBe(true)
  expect(useConnectionStore.getState().connection).not.toBeNull()
})

it('blocks duplicate requests and reports acceptance without claiming process exit', async () => {
  let complete: ((value: Response) => void) | undefined
  let posts = 0
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    if (request.method === 'GET') return version()
    posts++
    expect(request.url).toBe('http://127.0.0.1:8000/api/v1/shutdown')
    expect(request.headers.get('Authorization')).toBe('Bearer fixed-exit-token')
    return new Promise<Response>(resolve => { complete = resolve })
  }))
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  show()
  fireEvent.click(screen.getByRole('button', { name: '退出应用' }))
  await waitFor(() => expect(complete).toBeDefined())
  expect(screen.getByRole('button', { name: '正在请求退出…' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: '正在请求退出…' }))
  expect(posts).toBe(1)
  await act(async () => complete!(Response.json({ status: 'shutting_down' }, { status: 202 })))
  expect(await screen.findByRole('status')).toHaveTextContent('退出请求已接受')
  expect(screen.getByRole('status')).toHaveTextContent('缓存保存后退出')
  expect(screen.queryByText('已退出')).not.toBeInTheDocument()
  expect(useConnectionStore.getState().connection).toBeNull()
  expect(sessionStorage.getItem('ainiee.connection')).toBeNull()
  expect(screen.getByRole('button', { name: '退出应用' })).toBeDisabled()
  await act(async () => { await i18n.changeLanguage('en') })
  expect(screen.getByRole('status')).toHaveTextContent('Exit request accepted')
})

it('keeps the connection after a failed exit request and allows retry', async () => {
  let posts = 0
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    if (request.method === 'GET') return version()
    return ++posts === 1 ? Response.json({ detail: 'unavailable' }, { status: 503 }) : Response.json({ status: 'shutting_down' }, { status: 202 })
  }))
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  show()
  fireEvent.click(screen.getByRole('button', { name: '退出应用' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('退出请求未确认')
  expect(useConnectionStore.getState().connection?.token).toBe('fixed-exit-token')
  fireEvent.click(screen.getByRole('button', { name: '退出应用' }))
  expect(await screen.findByRole('status')).toHaveTextContent('退出请求已接受')
  expect(posts).toBe(2)
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

it('ignores a late acknowledgement when the user has selected a different service', async () => {
  let complete: ((value: Response) => void) | undefined
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => request.method === 'GET' ? version() : new Promise<Response>(resolve => { complete = resolve })))
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  show()
  fireEvent.click(screen.getByRole('button', { name: '退出应用' }))
  await waitFor(() => expect(complete).toBeDefined())
  act(() => useConnectionStore.getState().connect('http://127.0.0.1:8001', 'new-service-token'))
  await act(async () => complete!(Response.json({ status: 'shutting_down' }, { status: 202 })))
  expect(useConnectionStore.getState().connection?.token).toBe('new-service-token')
  expect(sessionStorage.getItem('ainiee.connection')).toContain('new-service-token')
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
  expect(await screen.findByRole('button', { name: '退出应用' })).toBeEnabled()
})

it.each([false, true])('stops the WebSocket after accepting exit (already reconnecting: %s)', async (reconnecting) => {
  vi.useFakeTimers()
  const sockets: { onclose: ((event: { code: number }) => void) | null; close: ReturnType<typeof vi.fn> }[] = []
  class FakeSocket {
    onopen = null
    onmessage = null
    onerror = null
    onclose: ((event: { code: number }) => void) | null = null
    close = vi.fn()
    constructor() { sockets.push(this) }
  }
  vi.stubGlobal('WebSocket', FakeSocket)
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    if (request.method === 'POST') return Response.json({ status: 'shutting_down' }, { status: 202 })
    if (request.url.endsWith('/config')) return Response.json({})
    if (request.url.endsWith('/tasks/current')) return Response.json({ status: 'idle', project_id: null, project_name: null, progress: {} })
    return version()
  }))
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const view = show(true)
  await act(async () => { await vi.advanceTimersByTimeAsync(0) })
  expect(sockets).toHaveLength(1)
  if (reconnecting) act(() => sockets[0].onclose?.({ code: 1006 }))
  fireEvent.click(screen.getByRole('button', { name: '退出应用' }))
  await act(async () => { await vi.advanceTimersByTimeAsync(100) })
  expect(useConnectionStore.getState().shutdownRequested).toBe(true)
  if (!reconnecting) expect(sockets[0].close).toHaveBeenCalledOnce()
  await act(async () => { await vi.advanceTimersByTimeAsync(20_000) })
  expect(sockets).toHaveLength(1)
  view.unmount()
})
