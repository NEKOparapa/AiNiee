import { QueryClient } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useBackendStore } from '@/stores/backend'
import { useConnectionStore } from '@/stores/connection'
import { useUiContextStore } from '@/stores/ui-context'
import { BackendSocket, type SocketFactory } from './client'
import { applyMessage, needsTaskRefresh, parseMessage } from './messages'
import { startBackendConnection } from './use-backend-connection'

class FakeSocket {
  onopen: (() => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  close = vi.fn()
  constructor(readonly url: string) {}
  open() { this.onopen?.() }
  disconnect(code = 1006) { this.onclose?.({ code }) }
  message(value: unknown) { this.onmessage?.({ data: JSON.stringify(value) }) }
}

const connection = { api: 'http://127.0.0.1:8000', token: 'fixed-test-token' }
let sockets: FakeSocket[]
let factory: SocketFactory

beforeEach(() => {
  vi.useFakeTimers()
  sockets = []
  factory = (url) => {
    const socket = new FakeSocket(url)
    sockets.push(socket)
    return socket as unknown as WebSocket
  }
  useBackendStore.getState().reset()
  useConnectionStore.getState().connect(connection.api, connection.token)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('WebSocket lifecycle', () => {
  it('reconnects with bounded backoff, refires open and resets server sequence after restart', async () => {
    const onOpen = vi.fn()
    const onMessage = vi.fn()
    const socket = new BackendSocket(connection, { onStatus: vi.fn(), onOpen, onMessage }, factory)
    socket.start()
    expect(sockets[0]?.url).toBe('ws://127.0.0.1:8000/api/v1/ws?token=fixed-test-token')
    sockets[0]?.open()
    sockets[0]?.message({ seq: 5, type: 'task.completed', ts: 1, data: {} })
    sockets[0]?.message({ seq: 5, type: 'task.completed', ts: 1, data: {} })
    expect(onMessage).toHaveBeenCalledTimes(1)
    sockets[0]?.disconnect()
    await vi.advanceTimersByTimeAsync(499)
    expect(sockets).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(1)
    sockets[1]?.open()
    sockets[1]?.message({ seq: 1, type: 'task.completed', ts: 2, data: {} })
    expect(onOpen).toHaveBeenCalledTimes(2)
    expect(onMessage).toHaveBeenCalledTimes(2)
    socket.stop()
    await vi.advanceTimersByTimeAsync(20_000)
    expect(sockets).toHaveLength(2)
  })

  it('stops reconnecting after an explicit authentication rejection', async () => {
    const onStatus = vi.fn()
    const socket = new BackendSocket(connection, { onStatus, onOpen: vi.fn(), onMessage: vi.fn() }, factory)
    socket.start()
    sockets[0]?.disconnect(1008)
    await vi.advanceTimersByTimeAsync(20_000)
    expect(sockets).toHaveLength(1)
    expect(onStatus).toHaveBeenLastCalledWith('disconnected', 'connection.unauthorized')
    socket.stop()
  })
})

it('refreshes config and task snapshots on reconnect and synchronizes the project context', async () => {
  const requests: string[] = []
  let line = 4
  const fetchMock = vi.fn(async (request: Request) => {
    requests.push(request.url)
    expect(request.headers.get('Authorization')).toBe('Bearer fixed-test-token')
    const value = request.url.endsWith('/config') ? { accent_color: '#808b9d' } : { status: 'running', project_id: 'project-one', project_name: 'Novel', progress: { line } }
    return new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fetchMock)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const stop = startBackendConnection(client, connection, useConnectionStore.getState().revision, factory)
  sockets[0]?.open()
  await vi.advanceTimersByTimeAsync(0)
  expect(useBackendStore.getState().progress?.line).toBe(4)
  expect(useUiContextStore.getState().projectId).toBe('project-one')
  const firstCount = requests.length
  line = 9
  sockets[0]?.disconnect()
  await vi.advanceTimersByTimeAsync(500)
  sockets[1]?.open()
  await vi.advanceTimersByTimeAsync(0)
  expect(requests.length).toBe(firstCount + 2)
  expect(useBackendStore.getState().progress?.line).toBe(9)
  expect(useConnectionStore.getState().status).toBe('connected')
  stop()
  client.clear()
})

it('late throttled progress does not change terminal task status and logs stay bounded', () => {
  useBackendStore.getState().setCurrentTask({ status: 'idle', project_id: null, project_name: null, progress: { line: 10 } })
  const progress = parseMessage(JSON.stringify({ seq: 3, type: 'task.update', ts: 1, data: { line: 12 } }))
  expect(progress).not.toBeNull()
  applyMessage(progress!)
  expect(useBackendStore.getState().currentTask?.status).toBe('idle')
  expect(useBackendStore.getState().progress?.line).toBe(12)
  useBackendStore.getState().appendLogs(Array.from({ length: 700 }, (_, index) => ({ ts: index, level: 'INFO', logger: 'test', message: String(index) })))
  expect(useBackendStore.getState().logs).toHaveLength(500)
  expect(useBackendStore.getState().logs[0]?.message).toBe('200')
  expect(parseMessage('{"seq":1,"type":"log","ts":1,"data":{"entries":[{"message":42}]}}')).toBeNull()
  expect(parseMessage('not json')).toBeNull()
  expect(needsTaskRefresh({ seq: 4, type: 'table.basic.update', ts: 1, data: {} })).toBe(false)
  expect(needsTaskRefresh({ seq: 5, type: 'task.completed', ts: 1, data: {} })).toBe(true)
})
