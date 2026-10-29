import type { WsMessage } from '@/api/types'
import type { ConnectionDetails, ConnectionStatus } from '@/stores/connection'
import { parseMessage } from './messages'

type SocketCallbacks = {
  onStatus: (status: ConnectionStatus, error?: string | null) => void
  onOpen: () => void
  onMessage: (message: WsMessage) => void
}

export type SocketFactory = (url: string) => WebSocket

export class BackendSocket {
  private socket: WebSocket | null = null
  private timer: ReturnType<typeof setTimeout> | null = null
  private stopped = true
  private attempts = 0
  private lastSeq = 0

  constructor(
    private readonly connection: ConnectionDetails,
    private readonly callbacks: SocketCallbacks,
    private readonly createSocket: SocketFactory = (url) => new WebSocket(url),
  ) {}

  start() {
    if (!this.stopped) return
    this.stopped = false
    this.connect()
  }

  stop() {
    this.stopped = true
    if (this.timer !== null) clearTimeout(this.timer)
    this.timer = null
    const socket = this.socket
    this.socket = null
    if (socket) {
      socket.onopen = socket.onmessage = socket.onclose = socket.onerror = null
      socket.close()
    }
  }

  private connect() {
    if (this.stopped) return
    this.callbacks.onStatus(this.attempts === 0 ? 'connecting' : 'reconnecting')
    const url = new URL('/api/v1/ws', this.connection.api)
    url.protocol = 'ws:'
    url.searchParams.set('token', this.connection.token)
    let socket: WebSocket
    try {
      socket = this.createSocket(url.toString())
    } catch {
      this.reconnect()
      return
    }
    this.socket = socket
    socket.onopen = () => {
      if (this.stopped || this.socket !== socket) return
      this.attempts = 0
      this.lastSeq = 0 // A restarted backend begins a new event sequence.
      this.callbacks.onStatus('connected')
      this.callbacks.onOpen()
    }
    socket.onmessage = (event) => {
      if (this.stopped || this.socket !== socket) return
      const message = parseMessage(event.data)
      if (!message || message.seq <= this.lastSeq) return
      this.lastSeq = message.seq
      this.callbacks.onMessage(message)
    }
    socket.onerror = () => {
      if (this.stopped || this.socket !== socket) return
      // Browsers follow error with close, which owns the reconnect timer.
      socket.close()
    }
    socket.onclose = (event) => {
      if (this.stopped || this.socket !== socket) return
      this.socket = null
      if (event.code === 1008) {
        this.stopped = true
        this.callbacks.onStatus('disconnected', 'connection.unauthorized')
        return
      }
      this.reconnect()
    }
  }

  private reconnect() {
    if (this.stopped || this.timer !== null) return
    this.callbacks.onStatus('reconnecting', 'connection.reconnecting')
    const delay = Math.min(500 * 2 ** this.attempts, 10_000)
    this.attempts += 1
    this.timer = setTimeout(() => {
      this.timer = null
      this.connect()
    }, delay)
  }
}
