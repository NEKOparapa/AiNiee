import createClient from 'openapi-fetch'
import type { paths } from './generated/schema'
import { useConnectionStore, type ConnectionDetails } from '@/stores/connection'

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly code: string) {
    super(code)
    this.name = 'ApiError'
  }
}

export function getApiClient(connection: ConnectionDetails) {
  return createClient<paths>({
    baseUrl: connection.api,
    headers: { Authorization: `Bearer ${connection.token}` },
  })
}

export function assertCurrentConnection(revision: number): ConnectionDetails {
  const state = useConnectionStore.getState()
  if (!state.connection || state.revision !== revision) throw new ApiError(0, 'connection.changed')
  return state.connection
}

export function throwApiError(status: number): never {
  if (status === 401 || status === 403) throw new ApiError(status, 'connection.unauthorized')
  if (status === 422) throw new ApiError(status, 'settings.invalidValue')
  throw new ApiError(status, 'connection.requestFailed')
}
