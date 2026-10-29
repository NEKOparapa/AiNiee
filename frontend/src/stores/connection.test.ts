import { beforeEach, describe, expect, it } from 'vitest'
import { ConnectionError, useConnectionStore, validateConnection } from './connection'
import { useLayoutStore } from './layout'
import { useUiContextStore } from './ui-context'

beforeEach(() => {
  sessionStorage.clear()
  localStorage.clear()
  window.history.replaceState(null, '', '/')
  useConnectionStore.setState({ connection: null, revision: 0, status: 'disconnected', error: null, initialized: false, shutdownRequested: false })
})

describe('connection credentials', () => {
  it('consumes the launcher fragment and stores credentials only in session storage', () => {
    window.history.replaceState(null, '', '/settings/task#api=http%3A%2F%2F127.0.0.1%3A8123&token=fixed-secret')
    useConnectionStore.getState().initialize()
    expect(window.location.hash).toBe('')
    expect(window.location.pathname).toBe('/settings/task')
    expect(useConnectionStore.getState().connection).toEqual({ api: 'http://127.0.0.1:8123', token: 'fixed-secret' })
    expect(sessionStorage.getItem('ainiee.connection')).toContain('fixed-secret')
    expect(localStorage.length).toBe(0)
    const revision = useConnectionStore.getState().revision
    useConnectionStore.getState().initialize()
    expect(useConnectionStore.getState().revision).toBe(revision)
  })

  it('restores a tab session and clears it on disconnect', () => {
    sessionStorage.setItem('ainiee.connection', JSON.stringify({ api: 'http://127.0.0.1:8000', token: 'fixed' }))
    useConnectionStore.getState().initialize()
    expect(useConnectionStore.getState().status).toBe('connecting')
    useConnectionStore.getState().disconnect()
    expect(useConnectionStore.getState().connection).toBeNull()
    expect(sessionStorage.getItem('ainiee.connection')).toBeNull()
  })

  it('marks an accepted shutdown for only its original connection and clears its credentials', () => {
    useConnectionStore.getState().connect('http://127.0.0.1:8000', 'first')
    const first = useConnectionStore.getState().revision
    useConnectionStore.getState().connect('http://127.0.0.1:8001', 'second')
    expect(useConnectionStore.getState().markShutdownRequested(first)).toBe(false)
    expect(useConnectionStore.getState().connection?.token).toBe('second')
    expect(useConnectionStore.getState().shutdownRequested).toBe(false)
    expect(useConnectionStore.getState().markShutdownRequested(useConnectionStore.getState().revision)).toBe(true)
    expect(useConnectionStore.getState()).toMatchObject({ connection: null, status: 'disconnected', shutdownRequested: true })
    expect(sessionStorage.getItem('ainiee.connection')).toBeNull()
    useConnectionStore.getState().connect('http://127.0.0.1:8002', 'third')
    expect(useConnectionStore.getState().shutdownRequested).toBe(false)
  })

  it.each(['https://evil.example', 'http://localhost:8000', 'http://127.0.0.1:8000/path', 'http://user@127.0.0.1:8000', 'http://127.0.0.1:0', 'http://127.0.0.1:8000?token=other'])('rejects an unsafe API origin %s', (origin) => {
    expect(() => validateConnection(origin, 'fixed')).toThrow(ConnectionError)
    expect(useConnectionStore.getState().connection).toBeNull()
  })

  it('removes invalid fragment credentials rather than falling back to a stale session', () => {
    sessionStorage.setItem('ainiee.connection', JSON.stringify({ api: 'http://127.0.0.1:8000', token: 'old' }))
    window.history.replaceState(null, '', '/#api=https%3A%2F%2Fevil.example&token=secret')
    useConnectionStore.getState().initialize()
    expect(useConnectionStore.getState().error).toBe('connection.invalidOrigin')
    expect(useConnectionStore.getState().connection).toBeNull()
    expect(window.location.hash).toBe('')
    expect(sessionStorage.length).toBe(0)
  })

  it.each(['', 'space token', 'line\nbreak', '中文'])('rejects invalid header token %s', (token) => {
    expect(() => validateConnection('http://127.0.0.1:8000', token)).toThrow('connection.invalidToken')
  })
})

it('persists panel state and records selection/filter context without consuming it', () => {
  useLayoutStore.setState({ agentPanelOpen: false, sidebarCollapsed: false })
  useLayoutStore.getState().toggleAgentPanel()
  expect(JSON.parse(localStorage.getItem('ainiee.layout') ?? '{}').agentPanelOpen).toBe(true)
  const context = useUiContextStore.getState()
  context.setProjectId('project-one')
  context.setPage('/items')
  context.setSelectedItemIds(['file:1', 'file:1', 'file:2'])
  context.setFilters({ status: 'translated', q: 'hello' })
  expect(useUiContextStore.getState()).toMatchObject({ projectId: 'project-one', page: '/items', selectedItemIds: ['file:1', 'file:2'], filters: { status: 'translated', q: 'hello' } })
  context.setProjectId('project-two')
  expect(useUiContextStore.getState()).toMatchObject({ selectedItemIds: [], filters: {} })
})
