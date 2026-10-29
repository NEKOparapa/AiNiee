import type { components } from './generated/schema'

// Every wire contract comes from the backend's OpenAPI document.
export type ApiConfig = components['schemas']['ConfigDocument']
export type ConfigPatch = components['schemas']['ConfigPatch']
export type TaskCurrent = components['schemas']['TaskCurrentResponse']
export type TaskProgress = components['schemas']['TaskProgress']
export type LogEntry = components['schemas']['LogEntry']
export type LogMessage = components['schemas']['LogMessage']
export type TaskUpdateMessage = components['schemas']['TaskUpdateMessage']
export type WsMessage = components['schemas']['WebSocketMessage']
export type VersionInfo = components['schemas']['VersionResponse']
