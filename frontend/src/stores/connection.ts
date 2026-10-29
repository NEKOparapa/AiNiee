import { create } from 'zustand'

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting'
export type ConnectionDetails = Readonly<{ api: string; token: string }>

const SESSION_KEY = 'ainiee.connection'

export class ConnectionError extends Error {
  constructor(public readonly code: 'connection.invalidOrigin' | 'connection.invalidToken') {
    super(code)
    this.name = 'ConnectionError'
  }
}

export function validateConnection(api: string, token: string): ConnectionDetails {
  let url: URL
  try {
    url = new URL(api)
  } catch {
    throw new ConnectionError('connection.invalidOrigin')
  }
  if (
    url.protocol !== 'http:' || url.hostname !== '127.0.0.1' ||
    url.username || url.password || url.search || url.hash ||
    (url.pathname !== '' && url.pathname !== '/') ||
    (url.port !== '' && (Number(url.port) < 1 || Number(url.port) > 65535))
  ) {
    throw new ConnectionError('connection.invalidOrigin')
  }
  if (!token || !/^[\x21-\x7e]+$/.test(token)) {
    throw new ConnectionError('connection.invalidToken')
  }
  return { api: url.origin, token }
}

function saveSession(connection: ConnectionDetails | null) {
  try {
    if (connection) sessionStorage.setItem(SESSION_KEY, JSON.stringify(connection))
    else sessionStorage.removeItem(SESSION_KEY)
  } catch {
    // Private browser sessions may disable storage; the in-memory session works.
  }
}

function readSession(): ConnectionDetails | null {
  try {
    const saved: unknown = JSON.parse(sessionStorage.getItem(SESSION_KEY) ?? 'null')
    if (saved && typeof saved === 'object' && 'api' in saved && 'token' in saved &&
        typeof saved.api === 'string' && typeof saved.token === 'string') {
      return validateConnection(saved.api, saved.token)
    }
  } catch {
    saveSession(null)
  }
  return null
}

type ConnectionState = {
  connection: ConnectionDetails | null
  revision: number
  status: ConnectionStatus
  error: string | null
  initialized: boolean
  initialize: () => void
  connect: (api: string, token: string) => void
  disconnect: () => void
  setStatus: (status: ConnectionStatus, error?: string | null) => void
}

export const useConnectionStore = create<ConnectionState>((set, get) => ({
  connection: null,
  revision: 0,
  status: 'disconnected',
  error: null,
  initialized: false,
  initialize: () => {
    if (get().initialized) return
    set({ initialized: true })
    const fragment = new URLSearchParams(window.location.hash.slice(1))
    if (fragment.has('token') || fragment.has('api')) {
      // Consume the launcher handoff immediately. Credentials never remain in
      // the address bar, browser history URL, query keys, or localStorage.
      window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search)
      try {
        get().connect(fragment.get('api') ?? '', fragment.get('token') ?? '')
      } catch (error) {
        saveSession(null)
        set({ connection: null, status: 'disconnected', error: error instanceof ConnectionError ? error.code : 'connection.invalidOrigin' })
      }
      return
    }
    const saved = readSession()
    if (saved) get().connect(saved.api, saved.token)
  },
  connect: (api, token) => {
    const connection = validateConnection(api, token)
    saveSession(connection)
    set((state) => ({ connection, revision: state.revision + 1, status: 'connecting', error: null, initialized: true }))
  },
  disconnect: () => {
    saveSession(null)
    set((state) => ({ connection: null, revision: state.revision + 1, status: 'disconnected', error: null }))
  },
  setStatus: (status, error = null) => set({ status, error }),
}))
