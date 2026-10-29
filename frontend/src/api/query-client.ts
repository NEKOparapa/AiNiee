import { QueryClient } from '@tanstack/react-query'
import { ApiError } from './client'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (count, error) => !(error instanceof ApiError && [401, 403, 422].includes(error.status)) && count < 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
    mutations: { retry: false },
  },
})

// Revision isolates connection lifetimes without putting the token in cache keys.
export const queryKeys = {
  connection: (revision: number) => ['connection', revision] as const,
  config: (revision: number) => ['connection', revision, 'config'] as const,
  task: (revision: number) => ['connection', revision, 'task'] as const,
  version: (revision: number) => ['connection', revision, 'version'] as const,
}
